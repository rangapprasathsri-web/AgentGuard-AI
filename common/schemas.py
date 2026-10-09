import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class ActionType(str, Enum):
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    TRANSFER = "TRANSFER"
    DEPLOY = "DEPLOY"
    CHANGE_PERMISSION = "CHANGE_PERMISSION"
    REFUND = "REFUND"


class SourceType(str, Enum):
    USER = "user"
    EXTERNAL_CONTENT = "external_content"
    AGENT_INTERNAL = "agent_internal"


class DecisionOutcome(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"
    VOIDED = "VOIDED"


class Source(BaseModel):
    type: SourceType
    content_excerpt: Optional[str] = None

    @field_validator("content_excerpt")
    @classmethod
    def truncate_excerpt(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Truncate to 200 characters before storage
            return v[:200]
        return v


def validate_params_structure(params: Dict[str, Any]) -> None:
    """Validate flat or shallow depth <= 2, serialized size <= 4KB, string values <= 500 chars."""
    serialized = json.dumps(params)
    if len(serialized.encode("utf-8")) > 4096:
        raise ValueError("params serialized size exceeds 4 KB limit")

    def check_depth(d: Any, current_depth: int = 1) -> None:
        if current_depth > 2:
            raise ValueError("params nesting depth exceeds maximum of 2")
        if isinstance(d, dict):
            for k, v in d.items():
                if len(str(k)) > 100:
                    raise ValueError(f"param key '{k}' exceeds 100 characters")
                check_depth(v, current_depth + 1)
        elif isinstance(d, list):
            for item in d:
                check_depth(item, current_depth + 1)
        elif isinstance(d, str):
            if len(d) > 500:
                raise ValueError(f"param string value exceeds 500 characters")

    check_depth(params)


def validate_strict_int(val: Any, field_name: str) -> int:
    """amount and record_count must be non-negative INTEGERS (whole rupees; reject floats, NaN, negatives, booleans)."""
    if isinstance(val, bool):
        raise ValueError(f"{field_name} cannot be a boolean")
    if isinstance(val, float):
        raise ValueError(f"{field_name} must be a strict non-negative integer (floats rejected)")
    if not isinstance(val, int):
        try:
            # Reject if not an int-like representation
            if isinstance(val, str) and ("." in val or "e" in val.lower()):
                raise ValueError()
            int_val = int(val)
        except Exception:
            raise ValueError(f"{field_name} must be an integer")
    else:
        int_val = val

    if int_val < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return int_val


class ActionRequest(BaseModel):
    tenant_id: str = "demo"
    agent_id: str
    action: ActionType
    target: str = Field(..., max_length=100)
    params: Dict[str, Any] = Field(default_factory=dict)
    source: Source
    approval_id: Optional[str] = None
    unverified_claims: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9_.-]+$", v):
            raise ValueError("target must match pattern ^[A-Za-z0-9_.-]+$")
        return v

    @model_validator(mode="before")
    @classmethod
    def capture_unknown_and_validate(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        known_fields = {"tenant_id", "agent_id", "action", "target", "params", "source", "approval_id", "unverified_claims"}
        unknown = {k: v for k, v in data.items() if k not in known_fields}
        
        # Merge or capture unverified claims
        claims = dict(data.get("unverified_claims", {}))
        claims.update(unknown)
        data_clean = {k: v for k, v in data.items() if k in known_fields}
        data_clean["unverified_claims"] = claims

        params = data_clean.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("params must be a dictionary")
        
        validate_params_structure(params)

        action = data_clean.get("action")
        # Validate record_count and amount
        if "record_count" in params:
            params["record_count"] = validate_strict_int(params["record_count"], "record_count")
        else:
            if action in [ActionType.UPDATE, ActionType.DELETE, "UPDATE", "DELETE"]:
                raise ValueError(f"record_count is required for action {action}")
            elif action in [ActionType.READ, ActionType.CREATE, "READ", "CREATE"]:
                params["record_count"] = 1

        if "amount" in params:
            params["amount"] = validate_strict_int(params["amount"], "amount")

        # Refunds require params.customer_id and amount > 0
        target = data_clean.get("target")
        if target == "payments_api" and action in [ActionType.CREATE, "CREATE"]:
            if not params.get("customer_id"):
                raise ValueError("payments_api CREATE requests require params.customer_id")
            if "amount" not in params or params["amount"] <= 0:
                raise ValueError("payments_api CREATE requests require params.amount > 0")

        data_clean["params"] = params
        return data_clean


class MatchedPolicy(BaseModel):
    policy_id: str
    rule_name: str
    policy_ref: str
    severity: DecisionOutcome
    description: str


class EvaluationResponse(BaseModel):
    tenant_id: str = "demo"
    decision_id: str
    decision: DecisionOutcome
    risk_score: int
    risk_level: str
    factors: List[str]
    matched_policies: List[MatchedPolicy]
    consequences: List[str]
    rag_citations: List[str]
    action_hash: str
    decision_source: str
    analyzer_status: str
    rag_status: str
    policy_version: str
    approval_id: Optional[str] = None
    authorization: Optional[Dict[str, Any]] = None
    sig: Optional[str] = None


class AnalyzerOutput(BaseModel):
    consequences: List[str] = Field(default_factory=list, max_length=5)
    suspicion_flags: List[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recommended_risk_delta: int = Field(default=0)

    @field_validator("consequences", mode="after")
    @classmethod
    def cap_consequences_len(cls, v: List[str]) -> List[str]:
        return [s[:200] for s in v][:5]


class TenantRegisterRequest(BaseModel):
    company: str
    owner_email: str

class TenantRegisterResponse(BaseModel):
    tenant_id: str
    api_key: str


class ApprovalDecisionRequest(BaseModel):
    decision: str  # APPROVE | REJECT
    reason: Optional[str] = None


class AgentStatusUpdate(BaseModel):
    status: str  # active | inactive
