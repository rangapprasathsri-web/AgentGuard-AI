import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from common.clock import clock
from common.schemas import DecisionOutcome


class CumulativeLedger:
    def __init__(self, db_path: str = "guard.db", limits_path: str = "policies/limits.yaml"):
        self.db_path = db_path
        self.limits_path = limits_path
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
                CREATE TABLE IF NOT EXISTS cumulative_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reservation_id TEXT UNIQUE NOT NULL,
                    agent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT NOT NULL, -- RESERVED | EXECUTED | RELEASED
                    tenant_id TEXT NOT NULL DEFAULT 'demo',
                    request_hash TEXT, -- Made nullable for backward compatibility on migrations if needed, but we will pass it
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ledger_key 
                ON cumulative_ledger(tenant_id, agent_id, action, target, status, created_at)
                """
            )
            
            # Migration: add tenant_id if missing
            try:
                conn.execute("ALTER TABLE cumulative_ledger ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'demo'")
            except sqlite3.OperationalError:
                pass # Column already exists
                
            conn.commit()

    def check_and_reserve(
        self,
        reservation_id: str,
        agent_id: str,
        action: str,
        target: str,
        amount: int,
        tenant_id: str = "demo",
        request_hash: str = "",
        only_check: bool = False,
        conn: Optional[sqlite3.Connection] = None,
        bypass_soft_limit: bool = False,
    ) -> Tuple[DecisionOutcome, str, int, int]:
        import yaml
        if amount <= 0:
            return DecisionOutcome.BLOCK, "amount_must_be_positive", 0, 0

        # Lowest (safest) defaults
        soft_limit = 0
        hard_cap = 0
        rapid_count = 0
        rapid_window_seconds = 600
        window_hours = 24
        
        try:
            if not os.path.exists(self.limits_path):
                return DecisionOutcome.BLOCK, "limits_config_missing", amount, 0
            with open(self.limits_path, "r") as f:
                limits_data = yaml.safe_load(f)
                if not limits_data or "limits" not in limits_data:
                    return DecisionOutcome.BLOCK, "limits_config_invalid", amount, 0
                limits_list = limits_data["limits"]
                matched_limit = next((l for l in limits_list if l.get("action") == action and l.get("target") == target), None)
                
                if matched_limit:
                    soft_limit = matched_limit.get("soft_limit", soft_limit)
                    hard_cap = matched_limit.get("hard_cap", hard_cap)
                    rapid_count = matched_limit.get("rapid_count", rapid_count)
                    rapid_window_seconds = matched_limit.get("rapid_window_seconds", rapid_window_seconds)
                    window_hours = matched_limit.get("window_hours", window_hours)
                else:
                    return DecisionOutcome.BLOCK, "no_limit_defined", amount, 0
        except Exception:
            return DecisionOutcome.BLOCK, "limits_config_unparsable", amount, 0

        now_utc = clock.now_utc()
        now_iso = now_utc.isoformat()
        window_start_iso = (now_utc - timedelta(hours=window_hours)).isoformat()
        rapid_start_iso = (now_utc - timedelta(seconds=rapid_window_seconds)).isoformat()
        reservation_expiry_iso = (now_utc + timedelta(seconds=60)).isoformat()

        should_close = False
        if conn is None:
            conn = self._get_connection()
            should_close = True
            conn.execute("BEGIN IMMEDIATE")

        try:
            # 1. Calculate active total within 24h window
            # Active = EXECUTED or (RESERVED and expires_at > now)
            cursor = conn.execute(
                """
                SELECT SUM(amount) as total_amount
                FROM cumulative_ledger
                WHERE tenant_id = ? AND agent_id = ? AND action = ? AND target = ?
                  AND created_at >= ?
                  AND (status = 'EXECUTED' OR (status = 'RESERVED' AND expires_at > ?))
                """,
                (tenant_id, agent_id, action, target, window_start_iso, now_iso),
            )
            row = cursor.fetchone()
            current_active_total = int(row["total_amount"]) if row and row["total_amount"] is not None else 0
            new_total = current_active_total + amount

            # 2. Count prior same-key actions in the rapid window
            cursor = conn.execute(
                """
                SELECT COUNT(*) as rapid_cnt
                FROM cumulative_ledger
                WHERE tenant_id = ? AND agent_id = ? AND action = ? AND target = ?
                  AND created_at >= ?
                  AND (status = 'EXECUTED' OR (status = 'RESERVED' AND expires_at > ?))
                """,
                (tenant_id, agent_id, action, target, rapid_start_iso, now_iso),
            )
            row = cursor.fetchone()
            prior_rapid_count = int(row["rapid_cnt"]) if row and row["rapid_cnt"] is not None else 0

            # 3. Evaluate limits
            if new_total > hard_cap:
                if should_close:
                    conn.rollback()
                return (
                    DecisionOutcome.BLOCK,
                    f"hard_cap_exceeded: total {new_total} > {hard_cap}",
                    new_total,
                    prior_rapid_count,
                )

            if not bypass_soft_limit:
                if rapid_count > 0 and new_total > soft_limit and prior_rapid_count >= rapid_count:
                    if should_close:
                        conn.rollback()
                    return (
                        DecisionOutcome.BLOCK,
                        f"rapid_velocity_exceeded: rapid_count {prior_rapid_count} >= {rapid_count} and total {new_total} > {soft_limit}",
                        new_total,
                        prior_rapid_count,
                    )

                if new_total > soft_limit:
                    if not only_check:
                        # For REVIEW, the approval queue keeps it alive for 10m.
                        # So the reservation must match the 10m expiry.
                        review_expiry_iso = (now_utc + timedelta(seconds=600)).isoformat()
                        conn.execute(
                            """
                            INSERT INTO cumulative_ledger 
                            (reservation_id, tenant_id, agent_id, action, target, amount, status, request_hash, created_at, expires_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, 'RESERVED', ?, ?, ?, ?)
                            """,
                            (
                                reservation_id,
                                tenant_id,
                                agent_id,
                                action,
                                target,
                                amount,
                                request_hash,
                                now_iso,
                                review_expiry_iso,
                                now_iso,
                            ),
                        )
                        if should_close:
                            conn.commit()
                    elif should_close:
                        conn.rollback()
                        
                    return (
                        DecisionOutcome.REVIEW,
                        f"soft_limit_exceeded: total {new_total} > {soft_limit}",
                        new_total,
                        prior_rapid_count,
                    )

            # 4. If ALLOW and not only_check, create active reservation
            if not only_check:
                conn.execute(
                    """
                    INSERT INTO cumulative_ledger 
                    (reservation_id, tenant_id, agent_id, action, target, amount, status, request_hash, created_at, expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'RESERVED', ?, ?, ?, ?)
                    """,
                    (
                        reservation_id,
                        tenant_id,
                        agent_id,
                        action,
                        target,
                        amount,
                        request_hash,
                        now_iso,
                        reservation_expiry_iso,
                        now_iso,
                    ),
                )
                if should_close:
                    conn.commit()
            else:
                if should_close:
                    conn.rollback()

            return DecisionOutcome.ALLOW, "within_limits", new_total, prior_rapid_count

        except Exception as e:
            if should_close:
                conn.rollback()
            raise e
        finally:
            if should_close:
                conn.close()

    def confirm_reservation(self, reservation_id: str, outcome: str) -> bool:
        """
        Transition reservation to EXECUTED if successful, or RELEASED if failed.
        """
        now_iso = clock.now_iso()
        target_status = "EXECUTED" if outcome == "executed" else "RELEASED"

        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE cumulative_ledger
                SET status = ?, updated_at = ?
                WHERE reservation_id = ? AND status = 'RESERVED'
                """,
                (target_status, now_iso, reservation_id),
            )
            affected = cursor.rowcount
            conn.commit()
            return affected > 0

    def reset_ledger(self) -> None:
        """Clear ledger table for demo/test reset."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cumulative_ledger")
            conn.commit()
