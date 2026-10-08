import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from common.canonical import compute_action_hash, sign_payload
from common.clock import clock
from common.schemas import (
    ActionRequest,
    ActionType,
    DecisionOutcome,
    EvaluationResponse,
    MatchedPolicy,
)
from guard.approvals import ApprovalManager
from guard.ledger import CumulativeLedger
from guard.policy_version import get_policy_version
from guard.registries import AgentRegistry, ResourceRegistry
from guard.risk import RiskEngine
from guard.rules import HardRulesEngine


class GuardPipeline:
    def __init__(
        self,
        service_key: str = "default_service_key",
        agent_registry: Optional[AgentRegistry] = None,
        resource_registry: Optional[ResourceRegistry] = None,
        rules_engine: Optional[HardRulesEngine] = None,
        risk_engine: Optional[RiskEngine] = None,
        ledger: Optional[CumulativeLedger] = None,
        approval_manager: Optional[ApprovalManager] = None,
    ):
        self.service_key = service_key
        self.agent_registry = agent_registry or AgentRegistry()
        self.resource_registry = resource_registry or ResourceRegistry()
        self.rules_engine = rules_engine or HardRulesEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.ledger = ledger or CumulativeLedger()
        self.approval_manager = approval_manager or ApprovalManager()

    def evaluate(
        self,
        request: ActionRequest,
        analyzer_output: Optional[Dict[str, Any]] = None,
        rag_citations: Optional[List[str]] = None,
    ) -> EvaluationResponse:
        """
        Executes the Guard decision pipeline in fixed order (Section 8).
        """
        # Step 1: Hash and decision_id
        action_hash = compute_action_hash(
            request.agent_id, request.action.value, request.target, request.params
        )
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        policy_ver = get_policy_version()

        # Step 2: Identity & Step 3: Context resolution
        agent = self.agent_registry.get(request.agent_id)
        resource = self.resource_registry.get(request.target)
        is_known_target = self.resource_registry.is_known(request.target)

        # Step 4: Hard policy rules (Evaluate ALL rules)
        matched_policies = self.rules_engine.evaluate_all(
            request, agent, resource, is_known_target
        )
        hard_block = any(p.severity == DecisionOutcome.BLOCK for p in matched_policies)

        # Step 5: Risk score and deterministic thresholds
        deterministic_score, risk_level, factors, threshold_decision = self.risk_engine.evaluate(
            request, agent, resource, is_known_target
        )

        # Step 6: Cumulative gate
        amount = int(request.params.get("amount", 0))
        cum_decision = DecisionOutcome.ALLOW
        cum_reason = "within_limits"
        if amount > 0:
            # Evaluate cumulative gate (check only, reservation created upon final ALLOW/authorized)
            cum_decision, cum_reason, _, _ = self.ledger.check_and_reserve(
                reservation_id=decision_id,
                agent_id=request.agent_id,
                action=request.action.value,
                target=request.target,
                amount=amount,
                only_check=True,
            )

        # Step 7: Analyzer
        # Invariant I4: The LLM analyzer can never lower a score, never output ALLOW,
        # never override a BLOCK, and can never by itself cause a BLOCK.
        # min(score + delta, 69) when deterministic score < 70, else unchanged.
        analyzer_status = "not_run"
        consequences: List[str] = []
        adjusted_score = deterministic_score

        if deterministic_score < 25 and not hard_block and cum_decision == DecisionOutcome.ALLOW:
            analyzer_status = "skipped_low_risk"
        elif analyzer_output is not None:
            analyzer_status = analyzer_output.get("status", "success")
            consequences = analyzer_output.get("consequences", [])[:5]
            raw_delta = int(analyzer_output.get("recommended_risk_delta", 0))
            # Clamp delta to [0, 15] in code
            clamped_delta = max(0, min(15, raw_delta))
            if deterministic_score < 70:
                adjusted_score = min(deterministic_score + clamped_delta, 69)
            else:
                adjusted_score = deterministic_score
        else:
            analyzer_status = "skipped"

        # Determine threshold decision after score adjustment
        if adjusted_score < self.risk_engine.review_min:
            final_thresh_decision = DecisionOutcome.ALLOW
        elif adjusted_score < self.risk_engine.block_min:
            final_thresh_decision = DecisionOutcome.REVIEW
        else:
            final_thresh_decision = DecisionOutcome.BLOCK

        # Step 8: Final decision = most severe of:
        # hard_policy, thresholds on adjusted score, cumulative gate, unknown_target_floor
        # Invariant I4: final decision is most severe of all deterministic checks (ALLOW < REVIEW < BLOCK).
        # Tie order: hard_policy, cumulative_gate, threshold, analyzer, unknown_target_floor.
        severity_rank = {
            DecisionOutcome.ALLOW: 1,
            DecisionOutcome.REVIEW: 2,
            DecisionOutcome.BLOCK: 3,
        }

        # Candidate severities
        candidates = []
        if hard_block:
            candidates.append((3, "hard_policy", DecisionOutcome.BLOCK))
        if severity_rank[cum_decision] == 3:
            candidates.append((3, "cumulative_gate", DecisionOutcome.BLOCK))
        if severity_rank[final_thresh_decision] == 3:
            candidates.append((3, "threshold", DecisionOutcome.BLOCK))

        if not candidates:
            # Check review candidates
            if severity_rank[cum_decision] == 2:
                candidates.append((2, "cumulative_gate", DecisionOutcome.REVIEW))
            if severity_rank[final_thresh_decision] == 2:
                # Was this elevated by analyzer?
                if final_thresh_decision == DecisionOutcome.REVIEW and threshold_decision == DecisionOutcome.ALLOW:
                    candidates.append((2, "analyzer", DecisionOutcome.REVIEW))
                elif not is_known_target and "unknown_target_floor: floored to 40" in factors:
                    candidates.append((2, "unknown_target_floor", DecisionOutcome.REVIEW))
                else:
                    candidates.append((2, "threshold", DecisionOutcome.REVIEW))

        if not candidates:
            candidates.append((1, "threshold", DecisionOutcome.ALLOW))

        # Sort by severity descending, then preserve specified tie order
        tie_order = {
            "hard_policy": 1,
            "cumulative_gate": 2,
            "threshold": 3,
            "analyzer": 4,
            "unknown_target_floor": 5,
        }
        candidates.sort(key=lambda c: (-c[0], tie_order.get(c[1], 99)))

        winning_severity_rank, decision_source, final_decision = candidates[0]

        # Step 9: Handle outcomes (Approvals / Reservations)
        approval_id: Optional[str] = None
        if final_decision == DecisionOutcome.REVIEW:
            # Check for approval flood or duplicate
            appr_id, signal = self.approval_manager.create_approval(
                decision_id=decision_id,
                agent_id=request.agent_id,
                action_hash=action_hash,
                canonical_action={
                    "agent_id": request.agent_id,
                    "action": request.action.value,
                    "target": request.target,
                    "params": request.params,
                },
                risk_score=adjusted_score,
                factors=factors,
                consequences=consequences,
                rag_citations=rag_citations or [],
                policy_version=policy_ver,
            )
            if signal == "approval_flood":
                final_decision = DecisionOutcome.BLOCK
                decision_source = "hard_policy"
                factors.append("approval_flood: pending approvals exceeded 20 limit")
            else:
                approval_id = appr_id

        elif final_decision == DecisionOutcome.ALLOW:
            # Create active reservation for ALLOW outcome if amount > 0
            if amount > 0:
                self.ledger.check_and_reserve(
                    reservation_id=decision_id,
                    agent_id=request.agent_id,
                    action=request.action.value,
                    target=request.target,
                    amount=amount,
                    only_check=False,
                )

        # Risk level string
        if adjusted_score < 40:
            final_risk_level = "LOW"
        elif adjusted_score < 70:
            final_risk_level = "MEDIUM"
        else:
            final_risk_level = "HIGH"

        resp = EvaluationResponse(
            decision_id=decision_id,
            decision=final_decision,
            risk_score=adjusted_score,
            risk_level=final_risk_level,
            factors=factors,
            matched_policies=matched_policies,
            consequences=consequences,
            rag_citations=rag_citations or [],
            action_hash=action_hash,
            decision_source=decision_source,
            analyzer_status=analyzer_status,
            rag_status="success" if rag_citations else "skipped",
            policy_version=policy_ver,
            approval_id=approval_id,
        )

        # Sign the response
        sig = sign_payload(self.service_key, resp.model_dump())
        resp.sig = sig
        return resp

    def authorize(
        self, request: ActionRequest, approval_id: str
    ) -> Tuple[DecisionOutcome, str, Optional[Dict[str, Any]], Optional[str]]:
        """
        Executes atomic approval consumption & authorization (Section 11).
        Runs in ONE BEGIN IMMEDIATE transaction:
          a) loads approval; verifies action_hash (voids on mismatch);
          b) checks status (CONSUMED -> replay_attempt; others -> BLOCK);
          c) re-runs identity, permissions, hard rules, cumulative hard cap;
          d) atomic conditional consume UPDATE;
          e) reserves cumulative amount;
          f) returns signed authorization.
        Returns: (decision, reason_or_signal, authorization_dict, sig)
        """
        action_hash = compute_action_hash(
            request.agent_id, request.action.value, request.target, request.params
        )
        conn = self.approval_manager._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")

            cursor = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return DecisionOutcome.BLOCK, "approval_not_found", None, None

            # Lazy expiry check
            appr = self.approval_manager._evaluate_expiry(row, conn)

            # a) Hash mismatch check (checked first)
            if appr["action_hash"] != action_hash:
                now_iso = clock.now_iso()
                conn.execute(
                    "UPDATE approvals SET status = 'VOIDED', reason = 'hash_mismatch', updated_at = ? WHERE id = ?",
                    (now_iso, approval_id),
                )
                conn.commit()
                return DecisionOutcome.BLOCK, "hash_mismatch", None, None

            # b) Status checks
            if appr["status"] == "CONSUMED":
                conn.rollback()
                return DecisionOutcome.BLOCK, "replay_attempt", None, None
            if appr["status"] != "APPROVED":
                conn.rollback()
                return DecisionOutcome.BLOCK, f"approval_status_{appr['status'].lower()}", None, None

            # c) Re-check identity, permissions, hard policy rules, and cumulative hard cap
            agent = self.agent_registry.get(request.agent_id)
            resource = self.resource_registry.get(request.target)
            is_known = self.resource_registry.is_known(request.target)
            recheck_matches = self.rules_engine.evaluate_all(request, agent, resource, is_known)
            if any(m.severity == DecisionOutcome.BLOCK for m in recheck_matches):
                now_iso = clock.now_iso()
                conn.execute(
                    "UPDATE approvals SET status = 'VOIDED', reason = 'recheck_blocked', updated_at = ? WHERE id = ?",
                    (now_iso, approval_id),
                )
                conn.commit()
                return DecisionOutcome.BLOCK, "recheck_blocked", None, None

            amount = int(request.params.get("amount", 0))
            if amount > 0:
                # Cumulative hard cap check within this transaction
                cum_dec, cum_reason, _, _ = self.ledger.check_and_reserve(
                    reservation_id=f"auth_{approval_id}",
                    agent_id=request.agent_id,
                    action=request.action.value,
                    target=request.target,
                    amount=amount,
                    only_check=True,
                    conn=conn,
                )
                if cum_dec == DecisionOutcome.BLOCK:
                    now_iso = clock.now_iso()
                    conn.execute(
                        "UPDATE approvals SET status = 'VOIDED', reason = 'hard_cap_exceeded', updated_at = ? WHERE id = ?",
                        (now_iso, approval_id),
                    )
                    conn.commit()
                    return DecisionOutcome.BLOCK, "hard_cap_exceeded", None, None

            # d) Atomic consume conditional update
            now_utc = clock.now_utc()
            now_iso = now_utc.isoformat()
            cursor = conn.execute(
                """
                UPDATE approvals
                SET status = 'CONSUMED', updated_at = ?
                WHERE id = ? AND status = 'APPROVED' AND action_hash = ? AND expires_at > ?
                """,
                (now_iso, approval_id, action_hash, now_iso),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return DecisionOutcome.BLOCK, "consume_failed_or_expired", None, None

            # e) Reserve cumulative amount in ledger within this transaction
            if amount > 0:
                self.ledger.check_and_reserve(
                    reservation_id=appr["decision_id"],
                    agent_id=request.agent_id,
                    action=request.action.value,
                    target=request.target,
                    amount=amount,
                    only_check=False,
                    conn=conn,
                    bypass_soft_limit=True,
                )

            # Commit the entire atomic authorize transaction
            conn.commit()

            # f) Return signed authorization
            auth_payload = {
                "decision_id": appr["decision_id"],
                "approval_id": approval_id,
                "action_hash": action_hash,
                "agent_id": request.agent_id,
                "action": request.action.value,
                "target": request.target,
                "status": "authorized",
                "issued_at": now_iso,
            }
            sig = sign_payload(self.service_key, auth_payload)
            auth_payload["sig"] = sig
            return DecisionOutcome.ALLOW, "authorized", auth_payload, sig

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
