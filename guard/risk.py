import os
import yaml
from typing import Any, Dict, List, Optional, Tuple
from common.clock import clock
from common.schemas import ActionRequest, ActionType, DecisionOutcome, SourceType
from guard.registries import AgentRecord, ResourceRecord


class RiskEngine:
    def __init__(self, thresholds_path: str = "policies/thresholds.yaml"):
        self.thresholds_path = thresholds_path
        self.allow_max = 39
        self.review_min = 40
        self.review_max = 69
        self.block_min = 70
        self.load()

    def load(self) -> None:
        if os.path.exists(self.thresholds_path):
            with open(self.thresholds_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                thresh = data.get("thresholds", {})
                self.allow_max = int(thresh.get("allow_max", 39))
                self.review_min = int(thresh.get("review_min", 40))
                self.review_max = int(thresh.get("review_max", 69))
                self.block_min = int(thresh.get("block_min", 70))

    def evaluate(
        self,
        request: ActionRequest,
        agent: Optional[AgentRecord],
        resource: Optional[ResourceRecord],
        is_known_target: bool,
    ) -> Tuple[int, str, List[str], DecisionOutcome]:
        """
        Calculates additive risk score (0-100), risk level (LOW/MEDIUM/HIGH),
        factor descriptions, and initial threshold decision.
        """
        score = 0
        factors: List[str] = []

        # 1. Base score by action
        action_base_map = {
            ActionType.READ: 5,
            ActionType.CREATE: 15,
            ActionType.UPDATE: 25,
            ActionType.TRANSFER: 35,
            ActionType.DEPLOY: 40,
            ActionType.DELETE: 50,
            ActionType.CHANGE_PERMISSION: 60,
        }
        base_score = action_base_map.get(request.action, 5)
        score += base_score
        factors.append(f"base_action_{request.action.value.lower()}: +{base_score}")

        # 2. Context resolution (worst-case defaults if unknown)
        if resource:
            env = resource.environment
            data_class = resource.data_class
            registry_record_count = resource.record_count
            is_reversible = resource.reversible
        else:
            # Unknown target: worst-case defaults (production, confidential, irreversible)
            env = "production"
            data_class = "confidential"
            registry_record_count = 1
            is_reversible = False

        # Environment
        env_map = {"dev": 0, "staging": 5, "production": 10}
        env_score = env_map.get(env, 10)
        if env_score > 0:
            score += env_score
            factors.append(f"environment_{env}: +{env_score}")

        # Data class
        data_class_map = {
            "public": 0,
            "internal": 5,
            "confidential": 10,
            "financial": 10,
            "PII": 20,
            "secrets": 25,
        }
        dc_score = data_class_map.get(data_class, 10)
        if dc_score > 0:
            score += dc_score
            factors.append(f"data_class_{data_class.lower()}: +{dc_score}")

        # Amount (highest tier only)
        amount = request.params.get("amount")
        if amount is not None and isinstance(amount, (int, float)):
            if amount > 50000:
                score += 10
                factors.append("amount_gt_50000: +10")
            elif amount > 10000:
                score += 5
                factors.append("amount_gt_10000: +5")

        # Affected records (highest tier only): record_count capped by registry record_count
        req_rec_count = request.params.get("record_count", 1)
        affected_records = min(req_rec_count, registry_record_count)
        if affected_records > 1000:
            score += 15
            factors.append("affected_records_gt_1000: +15")
        elif affected_records > 100:
            score += 8
            factors.append("affected_records_gt_100: +8")

        # Irreversible (only if action is mutating / destructive)
        if not is_reversible and request.action != ActionType.READ:
            score += 15
            factors.append("irreversible_resource_mutation: +15")

        # Off-hours
        if clock.is_off_hours():
            score += 10
            factors.append("off_hours: +10")

        # Baseline deviation
        baseline_dev = False
        if agent and agent.baseline:
            if request.action.value not in agent.baseline.typical_actions:
                baseline_dev = True
            elif (
                amount is not None
                and agent.baseline.max_normal_amount is not None
                and amount > agent.baseline.max_normal_amount
            ):
                baseline_dev = True
        elif agent is None:
            # Unknown agent baseline
            baseline_dev = True

        if baseline_dev:
            score += 10
            factors.append("baseline_deviation: +10")

        # External content source
        if request.source.type == SourceType.EXTERNAL_CONTENT:
            score += 15
            factors.append("external_content_source: +15")

        # Cap score at 100
        score = min(score, 100)

        # Unknown target floor at REVIEW (effective score floor at 40)
        if not is_known_target:
            if score < self.review_min:
                score = self.review_min
                factors.append("unknown_target_floor: floored to 40")

        # Determine decision outcome from thresholds
        if score < self.review_min:
            decision = DecisionOutcome.ALLOW
            risk_level = "LOW"
        elif score < self.block_min:
            decision = DecisionOutcome.REVIEW
            risk_level = "MEDIUM"
        else:
            decision = DecisionOutcome.BLOCK
            risk_level = "HIGH"

        return score, risk_level, factors, decision
