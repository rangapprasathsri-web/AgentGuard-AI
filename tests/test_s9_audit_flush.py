import os
import pytest
from fastapi.testclient import TestClient

def test_s9_audit_flush():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    
    from gateway.main import app, audit_logger
    gateway_client = TestClient(app)
    
    # 1. Ensure there is at least one log
    audit_logger.append_event(
        tenant_id="demo",
        decision_id="dec_flush_1",
        event_type="security_signal",
        payload={"signal": "test_flush"}
    )
    
    # 2. Unauthorized request fails
    res_401 = gateway_client.post("/gateway/admin/flush_audit")
    assert res_401.status_code == 401
    
    # 3. Wrong key fails
    res_403 = gateway_client.post(
        "/gateway/admin/flush_audit",
        headers={"Authorization": "Bearer wrong_key"}
    )
    assert res_403.status_code == 403
    
    # 4. Correct key succeeds
    res_ok = gateway_client.post(
        "/gateway/admin/flush_audit",
        headers={"Authorization": "Bearer secret_service_key_123"}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "flushed"
    assert res_ok.json()["bytes"] > 0
    
    # 5. DB is now empty, so verify_chain returns GENESIS
    verify = audit_logger.verify_chain()
    assert verify["valid"] is True
    assert verify["head_hash"] == "GENESIS"
    assert verify["records_checked"] == 0
