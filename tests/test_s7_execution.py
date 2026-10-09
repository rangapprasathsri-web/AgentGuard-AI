import os
import pytest
from fastapi.testclient import TestClient

def test_s7_tenant_execution():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    
    from guard.main import app as guard_app
    from gateway.main import app as gateway_app
    
    guard_client = TestClient(guard_app)
    gateway_client = TestClient(gateway_app)
    
    # Register Tenant A
    reg_a = guard_client.post("/guard/tenants/register", json={
        "company": "Company A S7",
        "owner_email": "a7@corp.com"
    })
    tenant_a = reg_a.json()["tenant_id"]
    api_key_a = reg_a.json()["api_key"]
    
    # We need to manually set the tenant's base_url and credential since we don't have a full S3 yet
    # Or actually, the problem says "Gateway executes against a fake tenant endpoint... tenant endpoint down -> 502"
    # Let's set it to an unreachable endpoint to get 502!
    
    import sqlite3
    from common.vault import encrypt_credential
    with sqlite3.connect("tenants.db") as conn:
        cred = encrypt_credential("tenant_secret_abc")
        conn.execute("UPDATE tenant_endpoint SET base_url = 'http://localhost:9999/execute', credential_ciphertext = ? WHERE tenant_id = ?", (cred, tenant_a))
        conn.commit()
    
    # Make a request that evaluates to ALLOW (e.g. 5000 INR)
    # We patch GuardClient to mock the evaluation so we don't need a real Guard server running on 8001
    from unittest.mock import patch
    import common.canonical
    hash_a = common.canonical.compute_action_hash("finance-agent-01", "CREATE", "payments_api", {"amount": 5000, "customer_id": "cust_s7", "record_count": 1})
    
    with patch("gateway.main.enforcer.guard_client.evaluate") as mock_eval, \
         patch("gateway.main.enforcer.guard_client.confirm") as mock_confirm:
        mock_eval.return_value = (True, {
            "decision": "ALLOW",
            "decision_id": "mock_dec_1",
            "action_hash": hash_a,
            "status": "authorized"
        }, None)
        
        gw_res = gateway_client.post(
            "/gateway/execute",
            headers={
                "X-AgentGuard-Tenant": tenant_a,
                "Authorization": f"Bearer {api_key_a}",
                "X-Actor": "finance-agent-01",
                "X-Role": "agent"
            },
            json={
                "agent_id": "finance-agent-01",
                "action": "CREATE",
                "target": "payments_api",
                "params": {"amount": 5000, "customer_id": "cust_s7"},
                "source": {"type": "agent_internal", "id": "sys1"}
            }
        )
    
    # Should attempt to execute, but hit localhost:9999 and fail -> 502
    assert gw_res.status_code == 502
    assert gw_res.json()["detail"]["error"] == "Tenant endpoint down"
    
    # Cleanup sys.modules
    import sys
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]
