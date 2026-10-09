import os
from typing import Any, Dict, Optional, Tuple
from common.audit import AuditLogger
from common.canonical import compute_action_hash, compute_sha256
from common.schemas import ActionRequest, DecisionOutcome
from gateway.guard_client import GuardClient
from gateway.tool_map import get_tool_handler


class GatewayEnforcer:
    def __init__(
        self,
        guard_client: Optional[GuardClient] = None,
        audit_logger: Optional[AuditLogger] = None,
        tool_credential: Optional[str] = None,
    ):
        self.guard_client = guard_client or GuardClient()
        self.audit_logger = audit_logger or AuditLogger()
        self.tool_credential = tool_credential or os.getenv("TOOL_CREDENTIAL")
        if not self.tool_credential:
            raise RuntimeError("TOOL_CREDENTIAL missing")

    async def execute_action(
        self,
        raw_body: Dict[str, Any],
        actor: Optional[str],
        role: Optional[str],
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Executes Gateway authorization flow (Section 7).
        Returns: (http_status_code, response_body)
        """
        # 1. Verify Role and Actor headers (Section 6, 13)
        agent_id = raw_body.get("agent_id")
        if role != "agent" or actor != agent_id:
            self.audit_logger.append_event(
                event_type="security_signal",
                payload={
                    "signal": "role_actor_mismatch",
                    "actor_header": actor,
                    "role_header": role,
                    "agent_id_body": agent_id,
                },
            )
            return 403, {"error": "forbidden_role_or_actor_mismatch"}

        # 2. Strict Pydantic validation (Section 6)
        try:
            req = ActionRequest.model_validate(raw_body)
        except Exception as e:
            body_hash = compute_sha256(str(raw_body))
            self.audit_logger.append_event(
                event_type="security_signal",
                payload={"signal": "invalid_request", "body_hash": body_hash, "error": str(e)},
            )
            return 400, {"error": "invalid_request", "detail": str(e)}

        # 3. Compute action hash independently at Gateway
        computed_hash = compute_action_hash(
            req.agent_id, req.action.value, req.target, req.params
        )

        # 4. Check whether this is initial evaluation or resuming with approval_id
        if req.approval_id:
            # Resuming approved action -> Guard /guard/authorize
            success, guard_resp, err_type = await self.guard_client.authorize(
                req.model_dump(), req.approval_id
            )
        else:
            # Initial action -> Guard /guard/evaluate
            success, guard_resp, err_type = await self.guard_client.evaluate(req.model_dump())

        # Fail closed check (Invariant I2)
        if not success or not guard_resp:
            self.audit_logger.append_event(
                event_type="security_signal",
                payload={"signal": err_type or "guard_unreachable", "action_hash": computed_hash},
            )
            return 503, {"status": "denied_fail_closed", "reason": err_type or "guard_unreachable"}

        # Verify action_hash in Guard response equals Gateway's computed hash
        resp_hash = guard_resp.get("action_hash")
        if resp_hash != computed_hash:
            self.audit_logger.append_event(
                event_type="security_signal",
                payload={"signal": "bad_signature", "reason": "action_hash_mismatch"},
            )
            return 503, {"status": "denied_fail_closed", "reason": "action_hash_mismatch"}

        # 5. Handle outcomes
        decision = guard_resp.get("decision")
        auth_status = guard_resp.get("status")

        # Case A: ALLOW / authorized -> Execute tool
        if decision == "ALLOW" or auth_status == "authorized":
            decision_id = guard_resp.get("decision_id")
            tool_handler = get_tool_handler(req.action.value, req.target)
            if not tool_handler:
                self.audit_logger.append_event(
                    event_type="security_signal",
                    payload={"signal": "no_tool_mapping", "decision_id": decision_id},
                    decision_id=decision_id,
                )
                await self.guard_client.confirm(decision_id, "failed")
                return 400, {
                    "status": "blocked",
                    "decision_id": decision_id,
                    "reasons": ["no_tool_mapping"],
                }

            try:
                # Call mock tool with TOOL_CREDENTIAL and idempotency_key = decision_id
                result = tool_handler(
                    cred=self.tool_credential,
                    params=req.params,
                    idemp=decision_id,
                )
                # Confirm success to Guard
                await self.guard_client.confirm(decision_id, "executed")
                # Append executed audit event
                self.audit_logger.append_event(
                    event_type="executed",
                    payload={
                        "decision_id": decision_id,
                        "agent_id": req.agent_id,
                        "action": req.action.value,
                        "target": req.target,
                        "action_hash": computed_hash,
                        "status": "executed",
                    },
                    decision_id=decision_id,
                )
                return 200, {
                    "status": "executed",
                    "decision_id": decision_id,
                    "result": result,
                    "action_hash": computed_hash,
                }
            except Exception as e:
                await self.guard_client.confirm(decision_id, "failed")
                return 500, {"status": "execution_failed", "error": str(e)}

        # Case B: REVIEW -> pending approval
        elif decision == "REVIEW":
            approval_id = guard_resp.get("approval_id")
            decision_id = guard_resp.get("decision_id")
            return 202, {
                "status": "pending_approval",
                "approval_id": approval_id,
                "decision_id": decision_id,
            }

        # Case C: BLOCK
        else:
            decision_id = guard_resp.get("decision_id")
            decision_source = guard_resp.get("decision_source", "guard")
            reasons = guard_resp.get("factors", [])
            return 403, {
                "status": "blocked",
                "decision_id": decision_id,
                "decision_source": decision_source,
                "reasons": reasons,
            }
