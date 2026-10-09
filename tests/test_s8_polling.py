import os
import pytest
from fastapi.testclient import TestClient

def test_s8_agent_polling():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    os.environ["LLM_MODE"] = "mock"
    
    from guard.main import app as guard_app
    from gateway.main import app as gateway_app
    
    guard_client = TestClient(guard_app)
    gateway_client = TestClient(gateway_app)
    
    # 1. Register Tenant
    reg = guard_client.post("/guard/tenants/register", json={
        "company": "Company A S8",
        "owner_email": "a8@corp.com"
    })
    tenant_id = reg.json()["tenant_id"]
    api_key = reg.json()["api_key"]
    approver_token = reg.json()["approver_token"]
    
    # 2. Trigger REVIEW decision
    from common.canonical import compute_action_hash
    hash_a = compute_action_hash("finance-agent-01", "CREATE", "payments_api", {"amount": 15000, "customer_id": "cust", "record_count": 1})
    
    req_payload = {
        "agent_id": "finance-agent-01",
        "action": "CREATE",
        "target": "payments_api",
        "params": {"amount": 15000, "customer_id": "cust"},
        "source": {"type": "agent_internal", "id": "sys1"},
        "tenant_id": tenant_id,
        "request_hash": hash_a
    }
    
    eval_res = guard_client.post(
        "/guard/evaluate",
        headers={"X-Service-Key": "secret_service_key_123"},
        json=req_payload
    )
    assert eval_res.status_code == 200, eval_res.json()
    assert eval_res.json()["decision"] == "REVIEW", eval_res.json()
    approval_id = eval_res.json()["approval_id"]
    
    # 3. Agent polls Gateway for status -> PENDING
    from unittest.mock import patch
    
    async def mock_get_status_pending(*args, **kwargs):
        return {"status": "PENDING", "agent_id": "finance-agent-01"}
        
    with patch("gateway.main.guard_client.get_approval_status", side_effect=mock_get_status_pending):
        status_res = gateway_client.get(
            f"/gateway/status/{approval_id}",
            headers={
                "X-AgentGuard-Tenant": tenant_id,
                "Authorization": f"Bearer {api_key}",
                "X-Actor": "finance-agent-01",
                "X-Role": "agent"
            }
        )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "PENDING"
    
    # 4. Approver approves
    decide_res = guard_client.post(
        f"/approvals/{approval_id}/decide",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"decision": "APPROVE"}
    )
    assert decide_res.status_code == 200
    
    # 5. Agent polls Gateway -> APPROVED
    async def mock_get_status_approved(*args, **kwargs):
        return {"status": "APPROVED", "agent_id": "finance-agent-01"}
        
    with patch("gateway.main.guard_client.get_approval_status", side_effect=mock_get_status_approved):
        status_res2 = gateway_client.get(
            f"/gateway/status/{approval_id}",
            headers={
                "X-AgentGuard-Tenant": tenant_id,
                "Authorization": f"Bearer {api_key}",
                "X-Actor": "finance-agent-01",
                "X-Role": "agent"
            }
        )
    assert status_res2.status_code == 200
    assert status_res2.json()["status"] == "APPROVED"
    
    # 6. Agent resumes execution via Gateway with approval_id
    # We patch httpx post for tenant execution
    from unittest.mock import patch
    import sqlite3
    from common.vault import encrypt_credential
    with sqlite3.connect("tenants.db") as conn:
        cred = encrypt_credential("tenant_secret_abc")
        conn.execute("UPDATE tenant_endpoint SET base_url = 'http://localhost:9999/execute', credential_ciphertext = ? WHERE tenant_id = ?", (cred, tenant_id))
        conn.commit()

    async def mock_post(*args, **kwargs):
        class MockResp:
            status_code = 200
            content = b"{\"success\": true}"
            def raise_for_status(self): pass
            def json(self): return {"success": True}
        return MockResp()

    req_payload_gateway = req_payload.copy()
    del req_payload_gateway["tenant_id"]
    del req_payload_gateway["request_hash"]
    req_payload_gateway["approval_id"] = approval_id

    # Wait, we need to mock the Guard Client in Gateway, BUT for authorize it will hit Guard.
    # Since we have the TestClient, it won't work to hit localhost:8001!
    # So we MUST mock `enforcer.guard_client.authorize` to return ALLOW.
    with patch("gateway.main.enforcer.guard_client.authorize") as mock_auth, \
         patch("httpx.AsyncClient.post", side_effect=mock_post):
        mock_auth.return_value = (True, {
            "status": "authorized",
            "decision_id": "auth_dec_1",
            "action_hash": hash_a
        }, None)
        
        exec_res = gateway_client.post(
            "/gateway/execute",
            headers={
                "X-AgentGuard-Tenant": tenant_id,
                "Authorization": f"Bearer {api_key}",
                "X-Actor": "finance-agent-01",
                "X-Role": "agent"
            },
            json=req_payload_gateway
        )
    
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "executed"
    
    # Cleanup sys.modules
    import sys
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]
