import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from common.canonical import canonical_json
from common.clock import clock
from common.schemas import ApprovalStatus, DecisionOutcome


class ApprovalManager:
    def __init__(
        self,
        db_path: str = "guard.db",
        decision_window_minutes: int = 10,
        execution_window_minutes: int = 10,
    ):
        self.db_path = db_path
        self.decision_window = timedelta(minutes=decision_window_minutes)
        self.execution_window = timedelta(minutes=execution_window_minutes)
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
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'demo',
                    decision_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    action_hash TEXT NOT NULL,
                    canonical_action TEXT NOT NULL,
                    status TEXT NOT NULL, -- PENDING, APPROVED, REJECTED, EXPIRED, CONSUMED, VOIDED
                    risk_score INTEGER NOT NULL,
                    factors TEXT NOT NULL,
                    consequences TEXT NOT NULL,
                    rag_citations TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approved_at TEXT,
                    approver TEXT,
                    reason TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approvals_agent_hash 
                ON approvals(agent_id, action_hash, status)
                """
            )
            
            # Migration: add tenant_id if missing
            try:
                conn.execute("ALTER TABLE approvals ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'demo'")
            except sqlite3.OperationalError:
                pass # Column already exists
                
            conn.commit()

    def _evaluate_expiry(self, row: sqlite3.Row, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Lazy expiry evaluation based on current Guard clock."""
        data = dict(row)
        current_status = data["status"]
        if current_status in [ApprovalStatus.PENDING.value, ApprovalStatus.APPROVED.value]:
            expires_at = datetime.fromisoformat(data["expires_at"])
            if clock.now_utc() > expires_at:
                now_iso = clock.now_iso()
                conn.execute(
                    "UPDATE approvals SET status = 'EXPIRED', updated_at = ? WHERE id = ?",
                    (now_iso, data["id"]),
                )
                conn.commit()
                data["status"] = ApprovalStatus.EXPIRED.value
                data["updated_at"] = now_iso
        return data

    def find_pending_identical(self, tenant_id: str, agent_id: str, action_hash: str) -> Optional[Dict[str, Any]]:
        """Resubmitting an identical pending action returns existing approval rather than creating another."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM approvals
                WHERE tenant_id = ? AND agent_id = ? AND action_hash = ? AND status = 'PENDING'
                ORDER BY created_at DESC LIMIT 1
                """,
                (tenant_id, agent_id, action_hash),
            )
            row = cursor.fetchone()
            if row:
                return self._evaluate_expiry(row, conn)
        return None

    def count_pending(self, tenant_id: str, agent_id: str) -> int:
        """Counts active pending approvals for an agent."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM approvals WHERE tenant_id = ? AND agent_id = ? AND status = 'PENDING'",
                (tenant_id, agent_id),
            )
            rows = cursor.fetchall()
            count = 0
            for r in rows:
                updated = self._evaluate_expiry(r, conn)
                if updated["status"] == ApprovalStatus.PENDING.value:
                    count += 1
            return count

    def create_approval(
        self,
        decision_id: str,
        agent_id: str,
        action_hash: str,
        canonical_action: Dict[str, Any],
        risk_score: int,
        factors: List[str],
        consequences: List[str],
        rag_citations: List[str],
        policy_version: str,
        tenant_id: str = "demo",
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Creates a pending approval.
        Enforces maximum of 20 pending approvals per agent.
        Returns: (approval_id, error_signal)
        """
        # 1. Check if identical pending exists
        existing = self.find_pending_identical(tenant_id, agent_id, action_hash)
        if existing and existing["status"] == ApprovalStatus.PENDING.value:
            return existing["id"], None

        # 2. Check flood limit (max 20 pending)
        pending_cnt = self.count_pending(tenant_id, agent_id)
        if pending_cnt >= 20:
            return None, "approval_flood"

        now_utc = clock.now_utc()
        now_iso = now_utc.isoformat()
        expires_at_iso = (now_utc + self.decision_window).isoformat()
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO approvals
                (id, tenant_id, decision_id, agent_id, action_hash, canonical_action, status,
                 risk_score, factors, consequences, rag_citations, policy_version,
                 created_at, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    tenant_id,
                    decision_id,
                    agent_id,
                    action_hash,
                    canonical_json(canonical_action),
                    risk_score,
                    json.dumps(factors),
                    json.dumps(consequences),
                    json.dumps(rag_citations),
                    policy_version,
                    now_iso,
                    expires_at_iso,
                    now_iso,
                ),
            )
            conn.commit()

        return approval_id, None

    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            row = cursor.fetchone()
            if row:
                data = self._evaluate_expiry(row, conn)
                data["canonical_action"] = json.loads(data["canonical_action"])
                data["factors"] = json.loads(data["factors"])
                data["consequences"] = json.loads(data["consequences"])
                data["rag_citations"] = json.loads(data["rag_citations"])
                return data
        return None

    def list_approvals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM approvals ORDER BY risk_score DESC, created_at DESC")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                data = self._evaluate_expiry(r, conn)
                if status is None or data["status"] == status:
                    data["canonical_action"] = json.loads(data["canonical_action"])
                    data["factors"] = json.loads(data["factors"])
                    data["consequences"] = json.loads(data["consequences"])
                    data["rag_citations"] = json.loads(data["rag_citations"])
                    results.append(data)
            return results

    def decide(
        self, approval_id: str, decision: str, approver: str, reason: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Decides an approval (APPROVE | REJECT).
        Returns: (success, error_reason)
        """
        now_utc = clock.now_utc()
        now_iso = now_utc.isoformat()
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False, "not_found"

            data = self._evaluate_expiry(row, conn)
            if data["status"] != ApprovalStatus.PENDING.value:
                conn.rollback()
                return False, f"cannot decide approval in status {data['status']}"

            if decision == "APPROVE":
                # Execution window starts from approval time
                expires_at_iso = (now_utc + self.execution_window).isoformat()
                conn.execute(
                    """
                    UPDATE approvals
                    SET status = 'APPROVED', approved_at = ?, approver = ?,
                        reason = ?, expires_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (now_iso, approver, reason, expires_at_iso, now_iso, approval_id),
                )
            elif decision == "REJECT":
                conn.execute(
                    """
                    UPDATE approvals
                    SET status = 'REJECTED', approver = ?, reason = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (approver, reason, now_iso, approval_id),
                )
            else:
                conn.rollback()
                return False, f"unknown decision {decision}"

            conn.commit()
            return True, None

    def void_approval(self, approval_id: str, reason: str) -> None:
        now_iso = clock.now_iso()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE approvals SET status = 'VOIDED', reason = ?, updated_at = ? WHERE id = ?",
                (reason, now_iso, approval_id),
            )
            conn.commit()

    def reset_approvals(self) -> None:
        """Clear approvals table for demo/test reset."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM approvals")
            conn.commit()
