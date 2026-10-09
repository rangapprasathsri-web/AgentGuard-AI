import os
import pytest
from fastapi.testclient import TestClient

def test_s6_approver_auth():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    
    from guard.main import app as guard_app
    from gateway.main import app as gateway_app
    
    guard_client = TestClient(guard_app)
    gateway_client = TestClient(gateway_app)
    
    # 1. Register Tenant A
    reg_a = guard_client.post("/guard/tenants/register", json={
        "company": "Company A S6",
        "owner_email": "a6@corp.com"
    })
    tenant_a = reg_a.json()["tenant_id"]
    api_key_a = reg_a.json()["api_key"]
    token_a = reg_a.json()["approver_token"]
    
    # Register Tenant B
    reg_b = guard_client.post("/guard/tenants/register", json={
        "company": "Company B S6",
        "owner_email": "b6@corp.com"
    })
    tenant_b = reg_b.json()["tenant_id"]
    token_b = reg_b.json()["approver_token"]
    
    # 2. Trigger a REVIEW decision for Tenant A via Guard
    from common.canonical import sign_payload, compute_action_hash
    hash_a = compute_action_hash("finance-agent-01", "CREATE", "payments_api", {"amount": 15000, "customer_id": "cust_s6"})
    payload_a = {
        "agent_id": "finance-agent-01",
        "action": "CREATE",
        "target": "payments_api",
        "params": {"amount": 15000, "customer_id": "cust_s6"},
        "source": {"type": "agent_internal", "id": "sys1"},
        "tenant_id": tenant_a,
        "request_hash": hash_a
    }
    
    gw_res = guard_client.post(
        "/guard/evaluate",
        headers={"X-Service-Key": "secret_service_key_123"},
        json=payload_a
    )
    assert gw_res.status_code == 200
    assert gw_res.json()["decision"] == "REVIEW"
    approval_id = gw_res.json()["approval_id"]
    
    # 3. Forged role header (x-role="approver") without token should fail
    res_forge = guard_client.post(
        f"/approvals/{approval_id}/decide",
        headers={"X-Role": "approver"},
        json={"decision": "APPROVE"}
    )
    assert res_forge.status_code == 401
    assert "token" in res_forge.json()["detail"]
    
    # 4. Cross-tenant approval (Tenant B tries to approve Tenant A's request)
    res_cross = guard_client.post(
        f"/approvals/{approval_id}/decide",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"decision": "APPROVE"}
    )
    assert res_cross.status_code == 403
    
    # 5. Successful approval by Tenant A
    res_ok = guard_client.post(
        f"/approvals/{approval_id}/decide",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"decision": "APPROVE"}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "decided"
    
    # Cleanup sys.modules
    import sys
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]
