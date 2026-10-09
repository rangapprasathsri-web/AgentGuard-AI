import sys
import pytest
from fastapi.testclient import TestClient

def test_s3_registration():
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    
    from guard.main import app
    client = TestClient(app)

    response = client.post("/guard/tenants/register", json={
        "company": "Test Corp",
        "owner_email": "test@corp.com"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "tenant_id" in data
    assert "api_key" in data
    assert data["api_key"].startswith("ag_live_")
    
    # Test that the tenant_id starts with ten_
    assert data["tenant_id"].startswith("ten_")
    
    # Ensure api_key is at least 32 bytes hex encoded (64 chars) + prefix (8 chars)
    # The random token is 32 bytes = 64 hex chars
    assert len(data["api_key"]) >= 72

    # Clean up so we don't break test_defects.py which asserts import raises
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]
