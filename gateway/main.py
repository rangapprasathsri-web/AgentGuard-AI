import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from common.audit import AuditLogger
from gateway.enforcement import GatewayEnforcer
from gateway.guard_client import GuardClient
from guard.tenants import TenantStore

from common.secrets import get_validated_secret

# Fail closed if secrets missing
TOOL_CREDENTIAL = get_validated_secret("TOOL_CREDENTIAL")
SERVICE_KEY = get_validated_secret("SERVICE_KEY")
AUDIT_HMAC_KEY = get_validated_secret("AUDIT_HMAC_KEY")

audit_logger = AuditLogger(db_path="audit.db", hmac_key=AUDIT_HMAC_KEY)
guard_client = GuardClient(service_key=SERVICE_KEY)
enforcer = GatewayEnforcer(
    guard_client=guard_client,
    audit_logger=audit_logger,
    tool_credential=TOOL_CREDENTIAL,
)
tenant_store = TenantStore()

app = FastAPI(title="AgentGuard AI - Execution Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/gateway/execute")
async def execute_action(
    request: Request,
    x_actor: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None),
    x_agentguard_tenant: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    api_key = authorization.replace("Bearer ", "")
    tenant_id = tenant_store.verify_api_key(api_key)
    
    if not tenant_id or tenant_id != x_agentguard_tenant:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Inject tenant_id
    body["tenant_id"] = tenant_id

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
    x_agentguard_tenant: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    api_key = authorization.replace("Bearer ", "")
    tenant_id = tenant_store.verify_api_key(api_key)
    
    if not tenant_id or tenant_id != x_agentguard_tenant:
        raise HTTPException(status_code=401, detail="Unauthorized")

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
