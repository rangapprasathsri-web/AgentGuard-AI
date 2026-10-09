import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from auth.firebase_auth import current_owner, sensitive_owner
from common.audit import AuditLogger
from common.clock import clock
from common.schemas import (
    ActionRequest,
    AgentStatusUpdate,
    ApprovalDecisionRequest,
    DecisionOutcome,
    EvaluationResponse,
    TenantRegisterRequest,
    TenantRegisterResponse,
)
from guard.approvals import ApprovalManager
from guard.ledger import CumulativeLedger
from guard.pipeline import GuardPipeline
from guard.policy_version import get_policy_version
from guard.registries import AgentRegistry, ResourceRegistry
from guard.risk import RiskEngine
from guard.rules import HardRulesEngine
from guard.tenants import TenantStore

from common.secrets import get_validated_secret

# Verify required secrets at startup (Fail closed)
SERVICE_KEY = get_validated_secret("SERVICE_KEY")
AUDIT_HMAC_KEY = get_validated_secret("AUDIT_HMAC_KEY")

# Load components
agent_reg = AgentRegistry()
res_reg = ResourceRegistry()
rules_engine = HardRulesEngine()
risk_engine = RiskEngine()
ledger = CumulativeLedger(db_path="guard.db")
approvals_mgr = ApprovalManager(db_path="guard.db")
audit_logger = AuditLogger(db_path="audit.db", hmac_key=AUDIT_HMAC_KEY)
pipeline = GuardPipeline(
    service_key=SERVICE_KEY,
    agent_registry=agent_reg,
    resource_registry=res_reg,
    rules_engine=rules_engine,
    risk_engine=risk_engine,
    ledger=ledger,
    approval_manager=approvals_mgr,
)

tenant_store = TenantStore(db_path="tenants.db")

# Initialize decisions table
with sqlite3.connect("guard.db") as conn:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            decision TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            action_hash TEXT NOT NULL,
            decision_source TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

app = FastAPI(title="AgentGuard AI - Guard Service")

cors_origins_env = os.getenv("AGENTGUARD_CORS_ORIGINS", "")
if cors_origins_env:
    allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip() and orig.strip() != "*"]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_service_key(x_service_key: Optional[str] = Header(None)) -> None:
    if not x_service_key or x_service_key != SERVICE_KEY:
        raise HTTPException(status_code=403, detail="unauthorized_service_key")


def require_role(allowed_roles: List[str], x_role: Optional[str] = Header(None)) -> str:
    if not x_role or x_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"forbidden_role_requires_{allowed_roles}")
    return x_role


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/guard/tenants/register", response_model=TenantRegisterResponse)
async def register_tenant(req: TenantRegisterRequest):
    tenant_id, api_key = tenant_store.register_tenant(req.company, req.owner_email)
    approver_token = tenant_store.register_approver(tenant_id, "Default Approver", "approver")
    gateway_url = "http://localhost:8002"
    return TenantRegisterResponse(
        tenant_id=tenant_id,
        api_key=api_key,
        approver_token=approver_token,
        gateway_url=gateway_url
    )


class OwnerTenantRegisterRequest(BaseModel):
    company: str
    owner_email: Optional[str] = None


class ConnectCodeRequest(BaseModel):
    company: str
    state: str
    return_url: str
    tenant_id: Optional[str] = None


class ConnectExchangeRequest(BaseModel):
    code: str
    state: str
    return_url: str


@app.post("/tenants/register", response_model=TenantRegisterResponse)
async def register_owner_tenant(
    req: OwnerTenantRegisterRequest,
    owner: Dict[str, Any] = Depends(sensitive_owner),
):
    owner_email = req.owner_email or owner["email"]
    tenant_id, api_key = tenant_store.register_tenant(
        company=req.company,
        owner_email=owner_email,
        owner_uid=owner["uid"],
    )
    approver_token = tenant_store.register_approver(tenant_id, "Default Approver", "approver")
    gateway_url = "http://localhost:8002"
    audit_logger.append_event(
        event_type="tenant_registered",
        payload={"tenant_id": tenant_id, "owner_uid": owner["uid"], "company": req.company},
    )
    return TenantRegisterResponse(
        tenant_id=tenant_id,
        api_key=api_key,
        approver_token=approver_token,
        gateway_url=gateway_url,
    )


@app.get("/tenants/mine")
async def list_owner_tenants(owner: Dict[str, Any] = Depends(current_owner)):
    tenants = tenant_store.get_tenants_by_owner(owner["uid"])
    return [
        {
            "tenant_id": t["id"],
            "id": t["id"],
            "company": t["company"],
            "owner_email": t["owner_email"],
            "status": t["status"],
            "created_at": t["created_at"],
        }
        for t in tenants
    ]


@app.post("/tenants/{id}/rotate-key")
async def rotate_tenant_key(
    id: str,
    owner: Dict[str, Any] = Depends(sensitive_owner),
):
    t = tenant_store.get_tenant(id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    if t.get("owner_uid") != owner["uid"]:
        audit_logger.append_event(
            event_type="security_signal",
            tenant_id=id,
            payload={
                "signal": "unauthorized_tenant_rotate",
                "target_tenant": id,
                "caller_uid": owner["uid"],
            },
        )
        raise HTTPException(status_code=403, detail="forbidden_tenant_owner_mismatch")

    new_key = tenant_store.rotate_api_key(id)
    audit_logger.append_event(
        event_type="tenant_key_rotated",
        tenant_id=id,
        payload={"tenant_id": id, "owner_uid": owner["uid"]},
    )
    return {"tenant_id": id, "api_key": new_key, "status": "rotated"}


@app.post("/tenants/{id}/revoke-key")
async def revoke_tenant_key(
    id: str,
    owner: Dict[str, Any] = Depends(sensitive_owner),
):
    t = tenant_store.get_tenant(id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    if t.get("owner_uid") != owner["uid"]:
        audit_logger.append_event(
            event_type="security_signal",
            tenant_id=id,
            payload={
                "signal": "unauthorized_tenant_revoke",
                "target_tenant": id,
                "caller_uid": owner["uid"],
            },
        )
        raise HTTPException(status_code=403, detail="forbidden_tenant_owner_mismatch")

    tenant_store.revoke_api_key(id)
    audit_logger.append_event(
        event_type="tenant_key_revoked",
        tenant_id=id,
        payload={"tenant_id": id, "owner_uid": owner["uid"]},
    )
    return {"tenant_id": id, "status": "revoked"}


@app.post("/connect/code")
async def create_connect_code(
    req: ConnectCodeRequest,
    owner: Dict[str, Any] = Depends(sensitive_owner),
):
    if req.tenant_id:
        t = tenant_store.get_tenant(req.tenant_id)
        if not t or t.get("owner_uid") != owner["uid"]:
            raise HTTPException(status_code=403, detail="forbidden_tenant_owner_mismatch")
        tenant_id = req.tenant_id
        api_key = tenant_store.create_api_key(tenant_id)
        approver_token = tenant_store.register_approver(tenant_id, "Connect Approver", "approver")
    else:
        owner_email = owner["email"]
        tenant_id, api_key = tenant_store.register_tenant(req.company, owner_email, owner_uid=owner["uid"])
        approver_token = tenant_store.register_approver(tenant_id, "Default Approver", "approver")

    code = tenant_store.create_connect_code(
        tenant_id=tenant_id,
        api_key=api_key,
        approver_token=approver_token,
        state=req.state,
        return_url=req.return_url,
    )
    sep = "&" if "?" in req.return_url else "?"
    redirect_url = f"{req.return_url}{sep}code={code}&state={req.state}"
    return {"code": code, "redirect_url": redirect_url}


@app.post("/connect/exchange")
async def exchange_connect_code(req: ConnectExchangeRequest):
    res = tenant_store.exchange_connect_code(req.code, req.state, req.return_url)
    if not res:
        raise HTTPException(status_code=400, detail="invalid_or_expired_connect_code")
    res["gateway_url"] = "http://localhost:8002"
    return res
# Service-Only Endpoints (Gateway -> Guard)
# -------------------------------------------------------------
@app.post("/guard/evaluate", response_model=EvaluationResponse)
async def evaluate_action(
    request: ActionRequest,
    x_service_key: Optional[str] = Header(None),
):
    verify_service_key(x_service_key)
    resp = pipeline.evaluate(request)

    # Persist in decisions query table
    with sqlite3.connect("guard.db") as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO decisions 
            (decision_id, decision, agent_id, action, target, risk_score, risk_level, action_hash, decision_source, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resp.decision_id,
                resp.decision.value,
                request.agent_id,
                request.action.value,
                request.target,
                resp.risk_score,
                resp.risk_level,
                resp.action_hash,
                resp.decision_source,
                resp.model_dump_json(),
                clock.now_iso(),
            ),
        )
        conn.commit()

    # Append decision_made audit event (including ALLOW)
    audit_logger.append_event(
        event_type="decision_made",
        payload={
            "decision_id": resp.decision_id,
            "decision": resp.decision.value,
            "agent_id": request.agent_id,
            "action": request.action.value,
            "target": request.target,
            "risk_score": resp.risk_score,
            "action_hash": resp.action_hash,
            "decision_source": resp.decision_source,
            "policy_version": resp.policy_version,
            "provider_used": "mock",
        },
        decision_id=resp.decision_id,
    )
    return resp


class AuthorizeBody(BaseModel):
    request: ActionRequest
    approval_id: str


@app.post("/guard/authorize")
async def authorize_action(
    body: AuthorizeBody,
    x_service_key: Optional[str] = Header(None),
):
    verify_service_key(x_service_key)
    dec, reason, auth_payload, sig = pipeline.authorize(body.request, body.approval_id)
    if dec == DecisionOutcome.BLOCK:
        # Audit failure signal
        audit_logger.append_event(
            event_type="security_signal",
            payload={"signal": reason, "approval_id": body.approval_id},
        )
        raise HTTPException(status_code=403, detail={"status": "blocked", "reason": reason})

    return auth_payload


class ConfirmBody(BaseModel):
    decision_id: str
    outcome: str


@app.post("/guard/confirm")
async def confirm_action(
    body: ConfirmBody,
    x_service_key: Optional[str] = Header(None),
):
    verify_service_key(x_service_key)
    success = ledger.confirm_reservation(body.decision_id, body.outcome)
    return {"status": "confirmed", "reservation_updated": success}


# -------------------------------------------------------------
# Operator Endpoints (Dashboard / Approver / Admin)
# -------------------------------------------------------------
@app.get("/decisions")
async def list_decisions(x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    with sqlite3.connect("guard.db") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 100")
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            r["response"] = json.loads(r["response_json"])
        return rows


@app.get("/decisions/{id}")
async def get_decision(id: str, x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    with sqlite3.connect("guard.db") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
        data = dict(row)
        data["response"] = json.loads(data["response_json"])
        return data


@app.get("/approvals")
async def list_approvals(x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    return approvals_mgr.list_approvals()


@app.get("/approvals/{id}")
async def get_approval(id: str, x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin", "agent"], x_role)
    appr = approvals_mgr.get_approval(id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")
    return appr


@app.post("/approvals/{id}/decide")
async def decide_approval(
    id: str,
    body: ApprovalDecisionRequest,
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        audit_logger.append_event(
            event_type="security_signal",
            payload={
                "signal": "unauthorized_approve_attempt",
                "approval_id": id,
            },
        )
        raise HTTPException(status_code=401, detail="Decisions require approver token")

    token = authorization[7:]

    appr = approvals_mgr.get_approval(id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")

    tenant_id = appr.get("tenant_id", "demo")
    approver_info = tenant_store.verify_approver_token(tenant_id, token)
    if not approver_info:
        audit_logger.append_event(
            event_type="security_signal",
            payload={"signal": "invalid_approver_token", "approval_id": id}
        )
        raise HTTPException(status_code=403, detail="Invalid approver token")

    actual_approver = approver_info["name"]

    ok, err = approvals_mgr.decide(
        approval_id=id,
        decision=body.decision,
        approver=actual_approver,
        reason=body.reason,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # Audit approval decision
    audit_logger.append_event(
        event_type="approval_decided",
        payload={
            "approval_id": id,
            "decision": body.decision,
            "approver": actual_approver,
            "reason": body.reason,
        },
    )
    return {"status": "decided", "approval_id": id, "decision": body.decision}


@app.get("/agents")
async def list_agents(x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    return agent_reg.all_agents()


@app.post("/admin/agents/{agent_id}/status")
async def set_agent_status(
    agent_id: str,
    update: AgentStatusUpdate,
    x_role: Optional[str] = Header(None),
    x_actor: Optional[str] = Header(None),
):
    # Admin only (Kill switch)
    if x_role != "admin":
        raise HTTPException(status_code=403, detail="Status updates require admin role")

    ok = agent_reg.set_status(agent_id, update.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")

    audit_logger.append_event(
        event_type="security_signal",
        payload={
            "signal": "agent_status_updated",
            "agent_id": agent_id,
            "new_status": update.status,
            "admin": x_actor,
        },
    )
    return {"agent_id": agent_id, "status": update.status}


@app.get("/resources")
async def list_resources(x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    return res_reg.all_resources()


@app.get("/policy/version")
async def policy_version(x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    return {"policy_version": get_policy_version()}


@app.get("/audit")
async def query_audit(
    agent: Optional[str] = None,
    decision: Optional[str] = None,
    action: Optional[str] = None,
    environment: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    decision_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    x_role: Optional[str] = Header(None),
):
    require_role(["approver", "admin"], x_role)
    return audit_logger.list_events(
        agent_id=agent,
        decision=decision,
        action=action,
        environment=environment,
        date_from=date_from,
        date_to=date_to,
        decision_id=decision_id,
        event_type=event_type,
        limit=limit,
    )


@app.get("/audit/verify")
async def verify_audit_chain(x_role: Optional[str] = Header(None)):
    require_role(["approver", "admin"], x_role)
    return audit_logger.verify_chain()


# -------------------------------------------------------------
# DEMO_MODE endpoints (Section 12, 13)
# -------------------------------------------------------------
@app.post("/audit/demo/tamper")
async def audit_demo_tamper(x_role: Optional[str] = Header(None)):
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Endpoint only available in DEMO_MODE")
    require_role(["admin"], x_role)
    try:
        res = audit_logger.demo_tamper()
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/demo/reset")
async def demo_reset(x_role: Optional[str] = Header(None)):
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Endpoint only available in DEMO_MODE")
    require_role(["admin"], x_role)
    # Restore any tampered row
    audit_logger.demo_restore_tamper()
    # Reset approvals, ledger, decisions
    approvals_mgr.reset_approvals()
    ledger.reset_ledger()
    with sqlite3.connect("guard.db") as conn:
        conn.execute("DELETE FROM decisions")
        conn.commit()
    # Reseed tools.db
    from tools.db import reseed_tools_db
    reseed_tools_db()
    # Reset clock
    clock.reset()
    return {"status": "demo_environment_reset_complete"}


@app.post("/demo/clock")
async def demo_clock_adjust(offset_seconds: float = Query(...), x_role: Optional[str] = Header(None)):
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Endpoint only available in DEMO_MODE")
    require_role(["admin"], x_role)
    clock.set_offset(offset_seconds)
    return {"status": "offset_applied", "current_time": clock.now_iso()}
