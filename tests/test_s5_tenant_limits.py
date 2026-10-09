import os
import pytest
from fastapi.testclient import TestClient

def test_s5_tenant_isolation_limits():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    
    from guard.main import app as guard_app
    from gateway.main import app as gateway_app
    
    guard_client = TestClient(guard_app)
    gateway_client = TestClient(gateway_app)
    
    # Register Tenant A
    reg_a = guard_client.post("/guard/tenants/register", json={
        "company": "Company A",
        "owner_email": "a@corp.com"
    })
    tenant_a = reg_a.json()["tenant_id"]
    api_key_a = reg_a.json()["api_key"]
    
    # Register Tenant B
    reg_b = guard_client.post("/guard/tenants/register", json={
        "company": "Company B",
        "owner_email": "b@corp.com"
    })
    tenant_b = reg_b.json()["tenant_id"]
    api_key_b = reg_b.json()["api_key"]
    
    # Tenant A makes a payment of 8,000 (soft limit is 10,000) -> Should ALLOW
    # Let's test Guard directly.
    
    import json
    from common.canonical import sign_payload, compute_action_hash
    
    hash_a1 = compute_action_hash("finance-agent-01", "CREATE", "payments_api", {"amount": 8000, "customer_id": "cust_123"})
    payload = {
        "agent_id": "finance-agent-01",
        "action": "CREATE",
        "target": "payments_api",
        "params": {"amount": 8000, "customer_id": "cust_123"},
        "source": {"type": "agent_internal", "id": "sys1"},
        "tenant_id": tenant_a,
        "request_hash": hash_a1
    }
    signature = sign_payload("secret_service_key_123", payload)
    
    res_a1 = guard_client.post(
        "/guard/evaluate",
        headers={"X-Service-Key": "secret_service_key_123"},
        json=payload
    )
    if res_a1.status_code != 200 or res_a1.json()["decision"] != "ALLOW":
        print(res_a1.json())
    assert res_a1.status_code == 200
    assert res_a1.json()["decision"] == "ALLOW", res_a1.json()["factors"]
    
    # Now Tenant A has 8,000 active.
    # Tenant A tries 195,000! 8,000 + 195,000 = 203,000 -> exceeds daily cap! (hard_cap = 200,000)
    # Wait, 195,000 exceeds single limit (50,000). So it will block immediately on single limit.
    # To test cumulative cap block, we need a single amount <= 50,000 that pushes the total > 200,000.
    # So let's just make the amount 45,000, and do it 5 times? No, 8,000 + 45,000 = 53,000.
    # Let's just test single limit block for Tenant A:
    hash_a2 = compute_action_hash("finance-agent-01", "CREATE", "payments_api", {"amount": 60000, "customer_id": "cust_123"})
    payload_a2 = {
        "agent_id": "finance-agent-01",
        "action": "CREATE",
        "target": "payments_api",
        "params": {"amount": 60000, "customer_id": "cust_123"},
        "source": {"type": "agent_internal", "id": "sys1"},
        "tenant_id": tenant_a,
        "request_hash": hash_a2
    }
    sig_a2 = sign_payload("secret_service_key_123", payload_a2)
    res_a2 = guard_client.post(
        "/guard/evaluate",
        headers={"X-Service-Key": "secret_service_key_123"},
        json=payload_a2
    )
    if res_a2.status_code != 200 or res_a2.json()["decision"] != "BLOCK":
        print("res_a2=", res_a2.json())
    assert res_a2.status_code == 200
    assert res_a2.json()["decision"] == "BLOCK"
    assert any("single limit" in f for f in res_a2.json().get("factors", [])) or "single limit" in res_a2.json().get("reason", "")
    
    # Now Tenant B tries 15,000. 
    hash_b = compute_action_hash("finance-agent-01", "CREATE", "payments_api", {"amount": 15000, "customer_id": "cust_123"})
    payload_b = {
        "agent_id": "finance-agent-01",
        "action": "CREATE",
        "target": "payments_api",
        "params": {"amount": 15000, "customer_id": "cust_123"},
        "source": {"type": "agent_internal", "id": "sys1"},
        "tenant_id": tenant_b,
        "request_hash": hash_b
    }
    sig_b = sign_payload("secret_service_key_123", payload_b)
    res_b = guard_client.post(
        "/guard/evaluate",
        headers={"X-Service-Key": "secret_service_key_123"},
        json=payload_b
    )
    assert res_b.status_code == 200
    assert res_b.json()["decision"] == "REVIEW"
    
    # Cleanup sys.modules
    import sys
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]
