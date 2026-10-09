import os
import pytest
from fastapi.testclient import TestClient

def test_s4_gateway_auth_missing_headers():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    
    from gateway.main import app as gateway_app
    gateway_client = TestClient(gateway_app)
    
    response = gateway_client.post("/gateway/execute", json={
        "agent_id": "test_agent",
        "action": "CREATE",
        "target": "payments_api",
        "params": {}
    })
    # Should be 401 Unauthorized
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"

def test_s4_gateway_auth_valid_headers():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    from gateway.main import app as gateway_app
    from guard.main import app as guard_app
    gateway_client = TestClient(gateway_app)
    guard_client = TestClient(guard_app)
    
    # 1. Register a tenant to get a key
    reg_response = guard_client.post("/guard/tenants/register", json={
        "company": "Valid Corp",
        "owner_email": "valid@corp.com"
    })
    assert reg_response.status_code == 200
    data = reg_response.json()
    tenant_id = data["tenant_id"]
    api_key = data["api_key"]

    # 2. Try with valid headers
    # Note: GatewayEnforcer will try to call Guard on localhost:8001 which might fail 
    # (since we are testing Gateway directly), but the auth should pass.
    # It will hit the GuardClient which makes HTTP requests.
    # We just want to check it bypasses the 401 and returns 503 or 400 or 403 (due to role/actor)
    
    response = gateway_client.post(
        "/gateway/execute",
        headers={
            "X-AgentGuard-Tenant": tenant_id,
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "agent_id": "test_agent",
            "action": "CREATE",
            "target": "payments_api",
            "params": {}
        }
    )
    # Auth passed, so it should be role/actor mismatch (403)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "forbidden_role_or_actor_mismatch"

    import sys
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
