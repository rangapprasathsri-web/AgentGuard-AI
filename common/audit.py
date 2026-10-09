import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from common.canonical import canonical_json
from common.clock import clock


class AuditLogger:
    def __init__(self, db_path: str = "audit.db", hmac_key: Optional[str] = None):
        self.db_path = db_path
        self.hmac_key = hmac_key or os.getenv("AUDIT_HMAC_KEY")
        if not self.hmac_key:
            raise RuntimeError("Audit HMAC key is missing")
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
                CREATE TABLE IF NOT EXISTS audit_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL,
                    decision_id TEXT,
                    event_type TEXT NOT NULL, -- decision_made | approval_decided | executed | security_signal
                    timestamp TEXT NOT NULL,  -- real UTC ISO-8601
                    payload TEXT NOT NULL,    -- exact canonical JSON string
                    prev_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events_backup (
                    backup_id TEXT PRIMARY KEY,
                    seq INTEGER NOT NULL,
                    id TEXT NOT NULL,
                    decision_id TEXT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    backed_up_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _compute_record_hash(self, prev_hash: str, payload_str: str) -> str:
        message = (prev_hash + payload_str).encode("utf-8")
        return hmac.new(
            self.hmac_key.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

    def append_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        decision_id: Optional[str] = None,
        max_retries: int = 5,
    ) -> Dict[str, Any]:
        """
        Append an audit event in ONE BEGIN IMMEDIATE transaction.
        prev_hash of first event is 'GENESIS'.
        A seq collision retries; the chain never forks.
        """
        # Ensure effective_time from Guard clock is present in payload
        if "effective_time" not in payload:
            payload["effective_time"] = clock.now_iso()

        payload_str = canonical_json(payload)
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        real_utc_timestamp = datetime.now(timezone.utc).isoformat()

        for attempt in range(max_retries):
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")

                # Get last record
                cursor = conn.execute(
                    "SELECT seq, record_hash FROM audit_events ORDER BY seq DESC LIMIT 1"
                )
                last_row = cursor.fetchone()
                if last_row:
                    prev_hash = last_row["record_hash"]
                else:
                    prev_hash = "GENESIS"

                record_hash = self._compute_record_hash(prev_hash, payload_str)

                conn.execute(
                    """
                    INSERT INTO audit_events 
                    (id, decision_id, event_type, timestamp, payload, prev_hash, record_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        decision_id,
                        event_type,
                        real_utc_timestamp,
                        payload_str,
                        prev_hash,
                        record_hash,
                    ),
                )
                conn.commit()

                return {
                    "id": event_id,
                    "decision_id": decision_id,
                    "event_type": event_type,
                    "timestamp": real_utc_timestamp,
                    "payload": payload,
                    "prev_hash": prev_hash,
                    "record_hash": record_hash,
                }
            except sqlite3.OperationalError as e:
                conn.rollback()
                if attempt == max_retries - 1:
                    raise e
            finally:
                conn.close()

        raise RuntimeError("Failed to append audit event after retries")

    def verify_chain(self) -> Dict[str, Any]:
        """
        Verify the entire HMAC hash chain.
        Returns: {valid, records_checked, head_hash, first_broken_id, reason}
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM audit_events ORDER BY seq ASC")
            rows = cursor.fetchall()

            if not rows:
                return {
                    "valid": True,
                    "records_checked": 0,
                    "head_hash": "GENESIS",
                    "first_broken_id": None,
                    "reason": "Empty audit log",
                }

            expected_prev_hash = "GENESIS"
            for idx, r in enumerate(rows, start=1):
                # 1. Verify prev_hash link
                if r["prev_hash"] != expected_prev_hash:
                    return {
                        "valid": False,
                        "records_checked": idx - 1,
                        "head_hash": expected_prev_hash,
                        "first_broken_id": r["id"],
                        "reason": f"Chain link mismatch at seq {r['seq']}: expected prev_hash {expected_prev_hash}, found {r['prev_hash']}",
                    }

                # 2. Verify record_hash HMAC computation
                computed_hash = self._compute_record_hash(r["prev_hash"], r["payload"])
                if not hmac.compare_digest(computed_hash, r["record_hash"]):
                    return {
                        "valid": False,
                        "records_checked": idx - 1,
                        "head_hash": expected_prev_hash,
                        "first_broken_id": r["id"],
                        "reason": f"HMAC signature tampering detected at seq {r['seq']}",
                    }

                expected_prev_hash = r["record_hash"]

            return {
                "valid": True,
                "records_checked": len(rows),
                "head_hash": expected_prev_hash,
                "first_broken_id": None,
                "reason": "Chain intact",
            }

    def list_events(
        self,
        agent_id: Optional[str] = None,
        decision: Optional[str] = None,
        action: Optional[str] = None,
        environment: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        decision_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit log with filters."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: List[Any] = []

        if decision_id:
            query += " AND decision_id = ?"
            params.append(decision_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if date_from:
            query += " AND timestamp >= ?"
            params.append(date_from)
        if date_to:
            query += " AND timestamp <= ?"
            params.append(date_to)

        query += " ORDER BY seq DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                p = json.loads(r["payload"])
                # In-memory filter on parsed payload fields
                if agent_id and p.get("agent_id") != agent_id:
                    continue
                if decision and p.get("decision") != decision:
                    continue
                if action and p.get("action") != action:
                    continue
                if environment and p.get("environment") != environment:
                    continue

                item = dict(r)
                item["payload"] = p
                results.append(item)
            return results

    def demo_tamper(self) -> Dict[str, Any]:
        """
        DEMO_MODE only: Edits one row via raw SQL after saving the original in demo backup table.
        """
        if os.getenv("DEMO_MODE", "false").lower() != "true":
            raise PermissionError("Tamper demo can only be executed when DEMO_MODE is true")

        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute("SELECT * FROM audit_events ORDER BY seq DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                raise ValueError("No audit events to tamper with")

            # 1. Backup original record
            backup_id = f"bak_{uuid.uuid4().hex[:8]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO audit_events_backup
                (backup_id, seq, id, decision_id, event_type, timestamp, payload, prev_hash, record_hash, backed_up_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backup_id,
                    row["seq"],
                    row["id"],
                    row["decision_id"],
                    row["event_type"],
                    row["timestamp"],
                    row["payload"],
                    row["prev_hash"],
                    row["record_hash"],
                    now_iso,
                ),
            )

            # 2. Tamper row payload via raw SQL
            tampered_payload = json.dumps({"tampered": True, "note": "Attacker modified record"})
            conn.execute(
                "UPDATE audit_events SET payload = ? WHERE seq = ?",
                (tampered_payload, row["seq"]),
            )
            conn.commit()

            return {
                "tampered_seq": row["seq"],
                "tampered_id": row["id"],
                "backup_id": backup_id,
            }

    def demo_restore_tamper(self) -> bool:
        """
        Restores tampered row from backup table.
        """
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute("SELECT * FROM audit_events_backup ORDER BY backed_up_at DESC LIMIT 1")
            backup_row = cursor.fetchone()
            if not backup_row:
                conn.rollback()
                return False

            conn.execute(
                """
                UPDATE audit_events
                SET payload = ?, prev_hash = ?, record_hash = ?
                WHERE seq = ?
                """,
                (
                    backup_row["payload"],
                    backup_row["prev_hash"],
                    backup_row["record_hash"],
                    backup_row["seq"],
                ),
            )
            conn.execute("DELETE FROM audit_events_backup WHERE backup_id = ?", (backup_row["backup_id"],))
            conn.commit()
            return True
