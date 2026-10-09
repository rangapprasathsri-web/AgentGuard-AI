import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from auth.firebase_auth import (
    current_owner,
    sensitive_owner,
    set_token_verifier,
    reset_token_verifier,
)
from guard.tenants import TenantStore

# Sample FastAPI app to verify dependencies
sample_app = FastAPI()

@sample_app.get("/test/owner")
async def sample_owner_route(owner=Depends(current_owner)):
    return owner

@sample_app.post("/test/sensitive")
async def sample_sensitive_route(owner=Depends(sensitive_owner)):
    return owner



@pytest.fixture(autouse=True)
def clean_verifier():
    yield
    reset_token_verifier()


def test_missing_auth_header_returns_401():
    client = TestClient(sample_app)
    resp = client.get("/test/owner")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_authorization_header"


def test_malformed_auth_header_returns_401():
    client = TestClient(sample_app)
    # Not Bearer
    resp = client.get("/test/owner", headers={"Authorization": "Basic 12345"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_authorization_header_format"

    # Bearer with empty token
    resp = client.get("/test/owner", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_expired_or_invalid_token_returns_401():
    def fake_verifier(token, check_revoked=False):
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")

    set_token_verifier(fake_verifier)
    client = TestClient(sample_app)
    resp = client.get("/test/owner", headers={"Authorization": "Bearer bad_token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_or_expired_token"


def test_verifier_service_unavailable_returns_503():
    def fake_verifier(token, check_revoked=False):
        raise HTTPException(status_code=503, detail="auth_service_unavailable")

    set_token_verifier(fake_verifier)
    client = TestClient(sample_app)
    resp = client.get("/test/owner", headers={"Authorization": "Bearer any_token"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "auth_service_unavailable"


def test_valid_token_returns_owner_and_upserts():
    def fake_verifier(token, check_revoked=False):
        return {
            "uid": "owner_user_123",
            "email": "testowner@example.com",
            "email_verified": True,
            "firebase": {"sign_in_provider": "password"}
        }

    set_token_verifier(fake_verifier)
    client = TestClient(sample_app)
    resp = client.get("/test/owner", headers={"Authorization": "Bearer valid_token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["uid"] == "owner_user_123"
    assert data["email"] == "testowner@example.com"
    assert data["email_verified"] is True
    assert data["provider"] == "password"

    # Verify upsert into owners table
    store = TenantStore()
    owner = store.get_owner("owner_user_123")
    assert owner is not None
    assert owner["email"] == "testowner@example.com"


def test_google_provider_is_auto_verified():
    def fake_verifier(token, check_revoked=False):
        return {
            "uid": "google_user_456",
            "email": "googleowner@gmail.com",
            "email_verified": False, # Google accounts should be treated as verified by default
            "firebase": {"sign_in_provider": "google.com"}
        }

    set_token_verifier(fake_verifier)
    client = TestClient(sample_app)
    resp = client.get("/test/owner", headers={"Authorization": "Bearer google_token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["uid"] == "google_user_456"
    assert data["email_verified"] is True
    assert data["provider"] == "google"


def test_sensitive_action_requires_verified_email():
    # 1. Unverified email -> 403
    def unverified_verifier(token, check_revoked=False):
        assert check_revoked is True
        return {
            "uid": "unverified_user_789",
            "email": "unverified@example.com",
            "email_verified": False,
            "firebase": {"sign_in_provider": "password"}
        }

    set_token_verifier(unverified_verifier)
    client = TestClient(sample_app)
    resp = client.post("/test/sensitive", headers={"Authorization": "Bearer token_unverified"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "email_not_verified"

    # 2. Verified email -> 200
    def verified_verifier(token, check_revoked=False):
        assert check_revoked is True
        return {
            "uid": "verified_user_789",
            "email": "verified@example.com",
            "email_verified": True,
            "firebase": {"sign_in_provider": "password"}
        }

    set_token_verifier(verified_verifier)
    resp = client.post("/test/sensitive", headers={"Authorization": "Bearer token_verified"})
    assert resp.status_code == 200
    assert resp.json()["uid"] == "verified_user_789"
