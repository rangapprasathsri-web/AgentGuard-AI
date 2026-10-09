import sqlite3
import uuid
import hashlib
import os
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

class TenantStore:
    def __init__(self, db_path: str = "tenants.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    owner_email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    owner_uid TEXT DEFAULT NULL
                )
                """
            )
            # Run migration if owner_uid column does not exist
            cursor = conn.execute("PRAGMA table_info(tenants)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "owner_uid" not in columns:
                conn.execute("ALTER TABLE tenants ADD COLUMN owner_uid TEXT DEFAULT NULL")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS owners (
                    uid TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_api_keys (
                    tenant_id TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    PRIMARY KEY (tenant_id, key_hash)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_limits (
                    tenant_id TEXT PRIMARY KEY,
                    max_single_refund INTEGER NOT NULL,
                    daily_cumulative_cap INTEGER NOT NULL,
                    payment_review_threshold INTEGER NOT NULL,
                    payment_hard_block INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'INR'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_actions (
                    tenant_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    param_schema_json TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    PRIMARY KEY (tenant_id, action)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_endpoint (
                    tenant_id TEXT PRIMARY KEY,
                    base_url TEXT NOT NULL,
                    credential_ciphertext TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvers (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connect_codes (
                    code TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    approver_token TEXT NOT NULL,
                    state TEXT NOT NULL,
                    return_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            
            # Seed the default demo tenant if it doesn't exist
            cursor = conn.execute("SELECT id FROM tenants WHERE id = 'demo'")
            if not cursor.fetchone():
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO tenants (id, company, owner_email, status, created_at, owner_uid) VALUES ('demo', 'Demo Company', 'demo@agentguard.ai', 'ACTIVE', ?, NULL)",
                    (now,)
                )
                conn.execute(
                    "INSERT INTO tenant_limits (tenant_id, max_single_refund, daily_cumulative_cap, payment_review_threshold, payment_hard_block, currency) VALUES ('demo', 100000, 500000, 10000, 50000, 'INR')"
                )
            
            conn.commit()

    def upsert_owner(self, uid: str, email: str) -> None:
        """Upsert owner into owners table on authenticated call."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO owners (uid, email, created_at, last_login_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    email = excluded.email,
                    last_login_at = excluded.last_login_at
                """,
                (uid, email, now, now)
            )
            conn.commit()

    def get_owner(self, uid: str) -> Optional[Dict[str, Any]]:
        """Fetch owner by uid."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM owners WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    @staticmethod
    def generate_api_key() -> Tuple[str, str, str]:
        """Generates a secure API key. Returns (raw_key, key_hash, key_prefix)."""
        random_bytes = secrets.token_hex(32)
        raw_key = f"ag_live_{random_bytes}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12] # "ag_live_xxxx"
        return raw_key, key_hash, key_prefix

    def create_api_key(self, tenant_id: str) -> str:
        raw_key, key_hash, key_prefix = self.generate_api_key()
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO tenant_api_keys (tenant_id, key_hash, key_prefix, created_at) VALUES (?, ?, ?, ?)",
                (tenant_id, key_hash, key_prefix, now)
            )
            conn.commit()
        return raw_key

    def register_tenant(self, company: str, owner_email: str, owner_uid: Optional[str] = None) -> Tuple[str, str]:
        """
        Registers a new tenant.
        Returns (tenant_id, api_key)
        """
        tenant_id = f"ten_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        raw_key, key_hash, key_prefix = self.generate_api_key()
        
        from common.vault import encrypt_credential
        empty_cred = encrypt_credential("")
        
        with self._get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO tenants (id, company, owner_email, status, created_at, owner_uid) VALUES (?, ?, ?, 'ACTIVE', ?, ?)",
                    (tenant_id, company, owner_email, now, owner_uid)
                )
                conn.execute(
                    "INSERT INTO tenant_api_keys (tenant_id, key_hash, key_prefix, created_at) VALUES (?, ?, ?, ?)",
                    (tenant_id, key_hash, key_prefix, now)
                )
                conn.execute(
                    "INSERT INTO tenant_limits (tenant_id, max_single_refund, daily_cumulative_cap, payment_review_threshold, payment_hard_block, currency) VALUES (?, 50000, 200000, 10000, 50000, 'INR')",
                    (tenant_id,)
                )
                conn.execute(
                    "INSERT INTO tenant_endpoint (tenant_id, base_url, credential_ciphertext) VALUES (?, '', ?)",
                    (tenant_id, empty_cred)
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            
        return tenant_id, raw_key

    def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tenant record by id."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_tenants_by_owner(self, owner_uid: str) -> list:
        """Fetch all tenants belonging to a specific owner uid."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, company, owner_email, status, created_at, owner_uid FROM tenants WHERE owner_uid = ?",
                (owner_uid,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def rotate_api_key(self, tenant_id: str) -> str:
        """Revokes all active API keys for tenant and generates a new one. Returns raw_key."""
        raw_key, key_hash, key_prefix = self.generate_api_key()
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tenant_api_keys SET revoked_at = ? WHERE tenant_id = ? AND revoked_at IS NULL",
                (now, tenant_id)
            )
            conn.execute(
                "INSERT INTO tenant_api_keys (tenant_id, key_hash, key_prefix, created_at) VALUES (?, ?, ?, ?)",
                (tenant_id, key_hash, key_prefix, now)
            )
            conn.commit()
        return raw_key

    def revoke_api_key(self, tenant_id: str) -> None:
        """Revokes all active API keys for tenant."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tenant_api_keys SET revoked_at = ? WHERE tenant_id = ? AND revoked_at IS NULL",
                (now, tenant_id)
            )
            conn.commit()


    def verify_api_key(self, raw_key: str) -> Optional[str]:
        """Returns tenant_id if valid, None otherwise. Uses constant time compare implicitly via hash."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT tenant_id FROM tenant_api_keys WHERE key_hash = ? AND revoked_at IS NULL",
                (key_hash,)
            )
            row = cursor.fetchone()
            if row:
                return row["tenant_id"]
        return None

    def get_tenant_limits(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tenant_limits WHERE tenant_id = ?",
                (tenant_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def register_approver(self, tenant_id: str, name: str, role: str) -> str:
        """Registers an approver and returns a plain-text token (OTP)."""
        import uuid
        approver_id = f"appr_user_{uuid.uuid4().hex[:8]}"
        token = secrets.token_hex(16)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO approvers (id, tenant_id, name, role, token_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (approver_id, tenant_id, name, role, token_hash, now)
            )
            conn.commit()
        return token

    def get_tenant_endpoint(self, tenant_id: str) -> Optional[Dict[str, str]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT base_url, credential_ciphertext FROM tenant_endpoint WHERE tenant_id = ?",
                (tenant_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def verify_approver_token(self, tenant_id: str, token: str) -> Optional[Dict[str, str]]:
        """Verifies the token and returns approver info dict if valid."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, role FROM approvers WHERE tenant_id = ? AND token_hash = ?",
                (tenant_id, token_hash)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def create_connect_code(
        self,
        tenant_id: str,
        api_key: str,
        approver_token: str,
        state: str,
        return_url: str,
    ) -> str:
        """Issues a single-use connect code valid for 60 seconds, bound to state and return_url."""
        import time
        code = secrets.token_urlsafe(32)
        now_iso = datetime.now(timezone.utc).isoformat()
        expires_at = time.time() + 60.0
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO connect_codes (code, tenant_id, api_key, approver_token, state, return_url, created_at, expires_at, used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (code, tenant_id, api_key, approver_token, state, return_url, now_iso, expires_at),
            )
            conn.commit()
        return code

    def exchange_connect_code(
        self,
        code: str,
        state: str,
        return_url: str,
    ) -> Optional[Dict[str, str]]:
        """Exchanges a single-use connect code within 60s, checking state and return_url."""
        import time
        now = time.time()
        with self._get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    "SELECT tenant_id, api_key, approver_token, state, return_url, expires_at, used FROM connect_codes WHERE code = ?",
                    (code,)
                )
                row = cursor.fetchone()
                if not row:
                    conn.rollback()
                    return None
                if row["used"] != 0:
                    conn.rollback()
                    return None
                if row["expires_at"] < now:
                    conn.rollback()
                    return None
                if row["state"] != state or row["return_url"] != return_url:
                    conn.rollback()
                    return None
                
                conn.execute(
                    "UPDATE connect_codes SET used = 1 WHERE code = ?",
                    (code,)
                )
                conn.commit()
                return {
                    "tenant_id": row["tenant_id"],
                    "api_key": row["api_key"],
                    "approver_token": row["approver_token"],
                }
            except Exception:
                conn.rollback()
                raise

