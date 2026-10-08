import os
import yaml
from typing import Any, Dict, List, Optional
from common.schemas import ActionRequest, DecisionOutcome, MatchedPolicy, SourceType, ActionType
from guard.registries import AgentRecord, ResourceRecord


class HardRulesEngine:
    def __init__(self, rules_path: str = "policies/rules.yaml"):
        self.rules_path = rules_path
        self._rules_meta: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if os.path.exists(self.rules_path):
            with open(self.rules_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for r in data.get("rules", []):
                    self._rules_meta[r["id"]] = r

    def evaluate_all(
        self,
        request: ActionRequest,
        agent: Optional[AgentRecord],
        resource: Optional[ResourceRecord],
        is_known_target: bool,
    ) -> List[MatchedPolicy]:
        """
        Evaluate ALL hard policy rules and report every match.
        """
        matches: List[MatchedPolicy] = []

        # AGT-001: agent unknown or inactive
        if agent is None or agent.status != "active":
            meta = self._rules_meta.get("AGT-001", {})
            matches.append(
                MatchedPolicy(
                    policy_id="AGT-001",
                    rule_name=meta.get("name", "Agent Active Verification"),
                    policy_ref=meta.get("policy_ref", "sec_policy_agent_identity"),
                    severity=DecisionOutcome.BLOCK,
                    description=meta.get(
                        "description", "Agent must exist in registry and have active status"
                    ),
                )
            )

        # PERM-001: no matching permission
        # Note: if agent is unknown, PERM-001 also fails, but AGT-001 already caught it.
        # Still evaluate PERM-001 if agent has no permission
        if agent is not None and not agent.has_permission(request.action.value, request.target):
            meta = self._rules_meta.get("PERM-001", {})
            matches.append(
                MatchedPolicy(
                    policy_id="PERM-001",
                    rule_name=meta.get("name", "Action Permission Verification"),
                    policy_ref=meta.get("policy_ref", "sec_policy_least_privilege"),
                    severity=DecisionOutcome.BLOCK,
                    description=meta.get(
                        "description",
                        "Agent must hold explicit permission for the requested action and target",
                    ),
                )
            )

        # DATA-004: DELETE + production + PII
        # Checks if action is DELETE and resource is production + PII
        env = resource.environment if resource else "production"
        data_class = resource.data_class if resource else "confidential"
        if (
            request.action == ActionType.DELETE
            and env == "production"
            and data_class == "PII"
        ):
            meta = self._rules_meta.get("DATA-004", {})
            matches.append(
                MatchedPolicy(
                    policy_id="DATA-004",
                    rule_name=meta.get("name", "PII Production Deletion Guard"),
                    policy_ref=meta.get("policy_ref", "data_policy_pii_retention"),
                    severity=DecisionOutcome.BLOCK,
                    description=meta.get(
                        "description", "Deletion of production PII resources is strictly prohibited"
                    ),
                )
            )

        # INJ-002: source external_content AND action in {DELETE, DEPLOY, CHANGE_PERMISSION, TRANSFER}
        if request.source.type == SourceType.EXTERNAL_CONTENT and request.action in [
            ActionType.DELETE,
            ActionType.DEPLOY,
            ActionType.CHANGE_PERMISSION,
            ActionType.TRANSFER,
        ]:
            meta = self._rules_meta.get("INJ-002", {})
            matches.append(
                MatchedPolicy(
                    policy_id="INJ-002",
                    rule_name=meta.get("name", "External Content Untrusted Mutation Guard"),
                    policy_ref=meta.get("policy_ref", "sec_policy_prompt_injection"),
                    severity=DecisionOutcome.BLOCK,
                    description=meta.get(
                        "description",
                        "External content cannot directly trigger destructive, deploy, transfer, or permission changes",
                    ),
                )
            )

        # REG-003: unknown target AND action in {DELETE, DEPLOY, CHANGE_PERMISSION}
        if not is_known_target and request.action in [
            ActionType.DELETE,
            ActionType.DEPLOY,
            ActionType.CHANGE_PERMISSION,
        ]:
            meta = self._rules_meta.get("REG-003", {})
            matches.append(
                MatchedPolicy(
                    policy_id="REG-003",
                    rule_name=meta.get("name", "Unknown Target Guard"),
                    policy_ref=meta.get("policy_ref", "sec_policy_target_governance"),
                    severity=DecisionOutcome.BLOCK,
                    description=meta.get(
                        "description",
                        "Unknown targets cannot be subjected to destructive, deploy, or permission change operations",
                    ),
                )
            )

        return matches
