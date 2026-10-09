import os
import sys
import sqlite3
import pytest
from fastapi.testclient import TestClient
from auth.firebase_auth import set_token_verifier, reset_token_verifier
from guard.tenants import TenantStore

OWNER_A_UID = "owner_a_test_uid"
OWNER_A_EMAIL = "ownera@company.com"

OWNER_B_UID = "owner_b_test_uid"
OWNER_B_EMAIL = "ownerb@competitor.com"


@pytest.fixture(autouse=True)
def setup_env_and_cleanup():
    os.environ["SERVICE_KEY"] = "secret_service_key_123"
    os.environ["AUDIT_HMAC_KEY"] = "secret_hmac_key_123"
    os.environ["TOOL_CREDENTIAL"] = "secret_tool_cred_123"
    reset_token_verifier()
    yield
    reset_token_verifier()
    if "guard.main" in sys.modules:
        del sys.modules["guard.main"]
    if "gateway.main" in sys.modules:
        del sys.modules["gateway.main"]


@pytest.fixture
def guard_client():
    from guard.main import app as guard_app
    return TestClient(guard_app)


@pytest.fixture
def gateway_client():
    from gateway.main import app as gateway_app
    return TestClient(gateway_app)


def set_active_owner(uid: str, email: str, verified: bool = True, provider: str = "password"):
    def fake_verifier(token: str, check_revoked: bool = False):
        if token == "invalid_token":
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="invalid_token")
        if token == "expired_token":
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="expired_token")
        return {
            "uid": uid,
            "email": email,
            "email_verified": verified,
            "firebase": {"sign_in_provider": provider}
        }
    set_token_verifier(fake_verifier)


def test_owner_endpoints_missing_token_returns_401(guard_client):
    # Register
    r = guard_client.post("/tenants/register", json={"company": "No Token Corp"})
    assert r.status_code == 401

    # Mine
    r = guard_client.get("/tenants/mine")
    assert r.status_code == 401

    # Rotate
    r = guard_client.post("/tenants/ten_123/rotate-key")
    assert r.status_code == 401

    # Revoke
    r = guard_client.post("/tenants/ten_123/revoke-key")
    assert r.status_code == 401


def test_sensitive_endpoints_unverified_email_returns_403(guard_client):
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=False)
    auth_header = {"Authorization": "Bearer some_token"}

    # Register requires verified email
    r = guard_client.post("/tenants/register", json={"company": "Unverified Corp"}, headers=auth_header)
    assert r.status_code == 403
    assert r.json()["detail"] == "email_not_verified"

    # Rotate requires verified email
    r = guard_client.post("/tenants/ten_any/rotate-key", headers=auth_header)
    assert r.status_code == 403
    assert r.json()["detail"] == "email_not_verified"

    # Revoke requires verified email
    r = guard_client.post("/tenants/ten_any/revoke-key", headers=auth_header)
    assert r.status_code == 403
    assert r.json()["detail"] == "email_not_verified"


def test_register_tenant_stores_owner_uid_and_hashes_key(guard_client):
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    auth_header = {"Authorization": "Bearer token_owner_a"}

    resp = guard_client.post("/tenants/register", json={"company": "Alpha Corp"}, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()

    tenant_id = data["tenant_id"]
    api_key = data["api_key"]
    approver_token = data["approver_token"]

    assert tenant_id.startswith("ten_")
    assert api_key.startswith("ag_live_")
    assert approver_token is not None

    # Verify owner_uid in database
    store = TenantStore()
    tenant = store.get_tenant(tenant_id)
    assert tenant is not None
    assert tenant["owner_uid"] == OWNER_A_UID
    assert tenant["company"] == "Alpha Corp"

    # Verify key is stored hashed, never plain text in tenant_api_keys
    with sqlite3.connect("tenants.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT key_hash FROM tenant_api_keys WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        assert row is not None
        # key_hash should be a 64-char sha256 hex string, NOT the raw api_key
        assert row["key_hash"] != api_key
        assert len(row["key_hash"]) == 64


def test_owner_tenant_isolation_cannot_read_rotate_revoke_other_owner(guard_client):
    # 1. Register tenant for Owner A
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    resp_a = guard_client.post(
        "/tenants/register",
        json={"company": "Tenant of A"},
        headers={"Authorization": "Bearer token_a"}
    )
    assert resp_a.status_code == 200
    tenant_a_id = resp_a.json()["tenant_id"]

    # 2. Switch to Owner B
    set_active_owner(OWNER_B_UID, OWNER_B_EMAIL, verified=True)
    auth_b = {"Authorization": "Bearer token_b"}

    # Owner B lists their tenants -> tenant_a_id must NOT be in the list
    list_b = guard_client.get("/tenants/mine", headers=auth_b)
    assert list_b.status_code == 200
    b_tenant_ids = [t["tenant_id"] for t in list_b.json()]
    assert tenant_a_id not in b_tenant_ids

    # Owner B tries to rotate Owner A's key -> 403 forbidden
    rotate_res = guard_client.post(f"/tenants/{tenant_a_id}/rotate-key", headers=auth_b)
    assert rotate_res.status_code == 403
    assert rotate_res.json()["detail"] == "forbidden_tenant_owner_mismatch"

    # Owner B tries to revoke Owner A's key -> 403 forbidden
    revoke_res = guard_client.post(f"/tenants/{tenant_a_id}/revoke-key", headers=auth_b)
    assert revoke_res.status_code == 403
    assert revoke_res.json()["detail"] == "forbidden_tenant_owner_mismatch"

    # Verify audit entry recorded the unauthorized attempt
    with sqlite3.connect("audit.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT payload FROM audit_events WHERE event_type = 'security_signal' ORDER BY seq DESC LIMIT 5")
        rows = cur.fetchall()
        signals = [r["payload"] for r in rows]
        assert any(OWNER_B_UID in str(s) and tenant_a_id in str(s) for s in signals)

    # 3. Switch back to Owner A -> rotation and revocation succeed
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    auth_a = {"Authorization": "Bearer token_a"}

    rot_a = guard_client.post(f"/tenants/{tenant_a_id}/rotate-key", headers=auth_a)
    assert rot_a.status_code == 200
    new_key = rot_a.json()["api_key"]
    assert new_key.startswith("ag_live_")

    rev_a = guard_client.post(f"/tenants/{tenant_a_id}/revoke-key", headers=auth_a)
    assert rev_a.status_code == 200
    assert rev_a.json()["status"] == "revoked"


def test_connect_flow_code_exchange(guard_client):
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    auth_a = {"Authorization": "Bearer token_a"}

    # Issue connect code
    code_resp = guard_client.post(
        "/connect/code",
        json={
            "company": "Connect Client Corp",
            "state": "state_xyz_123",
            "return_url": "https://myapp.com/callback",
        },
        headers=auth_a,
    )
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]
    redirect_url = code_resp.json()["redirect_url"]
    assert f"code={code}" in redirect_url
    assert "state=state_xyz_123" in redirect_url

    # Exchange with wrong state -> 400
    err_res = guard_client.post(
        "/connect/exchange",
        json={
            "code": code,
            "state": "wrong_state",
            "return_url": "https://myapp.com/callback",
        }
    )
    assert err_res.status_code == 400

    # Exchange with valid params -> 200
    ex_res = guard_client.post(
        "/connect/exchange",
        json={
            "code": code,
            "state": "state_xyz_123",
            "return_url": "https://myapp.com/callback",
        }
    )
    assert ex_res.status_code == 200
    data = ex_res.json()
    assert data["api_key"].startswith("ag_live_")
    assert "tenant_id" in data

    # Single-use: Re-exchange same code -> 400
    reuse_res = guard_client.post(
        "/connect/exchange",
        json={
            "code": code,
            "state": "state_xyz_123",
            "return_url": "https://myapp.com/callback",
        }
    )
    assert reuse_res.status_code == 400


def test_gateway_rejects_firebase_id_tokens(guard_client, gateway_client):
    # Firebase ID tokens are JWTs (typically three base64 segments starting with eyJ)
    fake_firebase_jwt = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMyJ9.eyJzdWIiOiJzb21lX3VpZCIsImVtYWlsIjoidXNlckBleGFtcGxlLmNvbSJ9.signature_part"

    # Register a valid tenant
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    resp = guard_client.post(
        "/tenants/register",
        json={"company": "Gateway Test Corp"},
        headers={"Authorization": "Bearer token_a"}
    )
    tenant_id = resp.json()["tenant_id"]

    # 1. Sending Firebase ID token via Authorization header to Gateway returns 401
    gw_resp = gateway_client.post(
        "/gateway/execute",
        headers={
            "X-AgentGuard-Tenant": tenant_id,
            "Authorization": f"Bearer {fake_firebase_jwt}",
        },
        json={
            "agent_id": "test_agent",
            "action": "CREATE",
            "target": "payments_api",
            "params": {}
        }
    )
    assert gw_resp.status_code == 401

    # 2. Sending Firebase ID token via X-API-Key returns 401
    gw_resp2 = gateway_client.post(
        "/gateway/execute",
        headers={
            "X-AgentGuard-Tenant": tenant_id,
            "X-API-Key": fake_firebase_jwt,
        },
        json={
            "agent_id": "test_agent",
            "action": "CREATE",
            "target": "payments_api",
            "params": {}
        }
    )
    assert gw_resp2.status_code == 401


def test_gateway_accepts_valid_api_key_via_x_api_key_header(guard_client, gateway_client):
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    resp = guard_client.post(
        "/tenants/register",
        json={"company": "X-API-Key Corp"},
        headers={"Authorization": "Bearer token_a"}
    )
    tenant_id = resp.json()["tenant_id"]
    api_key = resp.json()["api_key"]

    # Call with X-API-Key header; auth passes (reaches enforcer and returns 403 role/actor mismatch as expected)
    gw_resp = gateway_client.post(
        "/gateway/execute",
        headers={
            "X-AgentGuard-Tenant": tenant_id,
            "X-API-Key": api_key,
        },
        json={
            "agent_id": "test_agent",
            "action": "CREATE",
            "target": "payments_api",
            "params": {}
        }
    )
    # Auth passed, role check rejected
    assert gw_resp.status_code == 403
    assert gw_resp.json()["detail"]["error"] == "forbidden_role_or_actor_mismatch"


def test_owner_can_get_tenant_limits(guard_client):
    set_active_owner(OWNER_A_UID, OWNER_A_EMAIL, verified=True)
    resp = guard_client.post(
        "/tenants/register",
        json={"company": "Limits Corp"},
        headers={"Authorization": "Bearer token_a"}
    )
    tenant_id = resp.json()["tenant_id"]

    # Owner A gets limits -> 200
    lim_resp = guard_client.get(f"/tenants/{tenant_id}/limits", headers={"Authorization": "Bearer token_a"})
    assert lim_resp.status_code == 200
    data = lim_resp.json()
    assert data["currency"] == "INR"
    assert data["max_single_refund"] > 0

    # Owner B gets Owner A's limits -> 403
    set_active_owner(OWNER_B_UID, OWNER_B_EMAIL, verified=True)
    bad_resp = guard_client.get(f"/tenants/{tenant_id}/limits", headers={"Authorization": "Bearer token_b"})
    assert bad_resp.status_code == 403

