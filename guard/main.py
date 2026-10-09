import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from common.audit import AuditLogger
from common.clock import clock
from common.schemas import (
    ActionRequest,
    AgentStatusUpdate,
    ApprovalDecisionRequest,
    DecisionOutcome,
    EvaluationResponse,
)
from guard.approvals import ApprovalManager
from guard.ledger import CumulativeLedger
from guard.pipeline import GuardPipeline
from guard.policy_version import get_policy_version
from guard.registries import AgentRegistry, ResourceRegistry
from guard.risk import RiskEngine
from guard.rules import HardRulesEngine

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


# -------------------------------------------------------------
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
    x_role: Optional[str] = Header(None),
    x_actor: Optional[str] = Header(None),
):
    # Role check: Approver ONLY. Admin and agent get 403 (Section 11, 13)
    if x_role != "approver":
        audit_logger.append_event(
            event_type="security_signal",
            payload={
                "signal": "unauthorized_approve_attempt",
                "attempted_role": x_role,
                "actor": x_actor,
                "approval_id": id,
            },
        )
        raise HTTPException(status_code=403, detail="Decisions require approver role")

    ok, err = approvals_mgr.decide(
        approval_id=id,
        decision=body.decision,
        approver=x_actor or "unknown_approver",
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
            "approver": x_actor,
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
