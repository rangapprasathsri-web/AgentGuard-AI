import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from common.audit import AuditLogger
from gateway.enforcement import GatewayEnforcer
from gateway.guard_client import GuardClient

# Fail closed if secrets missing
TOOL_CREDENTIAL = os.getenv("TOOL_CREDENTIAL")
SERVICE_KEY = os.getenv("SERVICE_KEY")
AUDIT_HMAC_KEY = os.getenv("AUDIT_HMAC_KEY")
if not TOOL_CREDENTIAL or not SERVICE_KEY or not AUDIT_HMAC_KEY:
    if os.getenv("ALLOW_INSECURE_DEV", "false").lower() != "true" and not os.path.exists(".env.gateway"):
        raise RuntimeError("Startup failed: required gateway secrets missing (fail closed)")

audit_logger = AuditLogger(db_path="audit.db", hmac_key=AUDIT_HMAC_KEY or "default_key")
guard_client = GuardClient(service_key=SERVICE_KEY or "default_service_key")
enforcer = GatewayEnforcer(
    guard_client=guard_client,
    audit_logger=audit_logger,
    tool_credential=TOOL_CREDENTIAL or "default_tool_cred",
)

app = FastAPI(title="AgentGuard AI - Execution Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/gateway/execute")
async def execute_action(
    request: Request,
    x_actor: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None),
):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    status_code, resp = await enforcer.execute_action(
        raw_body=body,
        actor=x_actor,
        role=x_role,
    )

    if status_code != 200 and status_code != 202:
        raise HTTPException(status_code=status_code, detail=resp)

    return resp


@app.get("/gateway/status/{approval_id}")
async def get_approval_status(
    approval_id: str,
    x_actor: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None),
):
    # Only agent role can check own status (Section 7)
    if x_role != "agent" or not x_actor:
        raise HTTPException(status_code=403, detail="Forbidden")

    appr = await guard_client.get_approval_status(approval_id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")

    # Own approvals only
    if appr.get("agent_id") != x_actor:
        raise HTTPException(status_code=403, detail="Access denied: own approvals only")

    return {"status": appr.get("status")}
