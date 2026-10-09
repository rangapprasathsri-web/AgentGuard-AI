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
                    created_at TEXT NOT NULL
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
            
            # Seed the default demo tenant if it doesn't exist
            cursor = conn.execute("SELECT id FROM tenants WHERE id = 'demo'")
            if not cursor.fetchone():
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO tenants (id, company, owner_email, status, created_at) VALUES ('demo', 'Demo Company', 'demo@agentguard.ai', 'ACTIVE', ?)",
                    (now,)
                )
                conn.execute(
                    "INSERT INTO tenant_limits (tenant_id, max_single_refund, daily_cumulative_cap, payment_review_threshold, payment_hard_block, currency) VALUES ('demo', 100000, 500000, 10000, 50000, 'INR')"
                )
            
            conn.commit()

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
