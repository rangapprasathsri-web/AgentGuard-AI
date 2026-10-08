import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict


def verify_credential(credential: Any) -> None:
    if not credential or not isinstance(credential, str):
        raise PermissionError("Missing or invalid tool credential")


def create_refund(
    credential: str,
    idempotency_key: str,
    customer_id: str,
    amount: int,
    db_path: str = "tools.db",
) -> Dict[str, Any]:
    verify_credential(credential)
    if not idempotency_key:
        raise ValueError("Missing idempotency_key")

    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cursor = conn.execute(
            "SELECT id FROM refunds WHERE idempotency_key = ?", (idempotency_key,)
        )
        if cursor.fetchone() is not None:
            raise ValueError(f"Duplicate refund rejected: idempotency_key '{idempotency_key}' already processed")

        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO refunds (idempotency_key, customer_id, amount, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (idempotency_key, customer_id, amount, now_iso),
        )
        conn.commit()
        return {
            "status": "refund_created",
            "customer_id": customer_id,
            "amount": amount,
            "idempotency_key": idempotency_key,
        }
    finally:
        conn.close()


def read_payments(credential: str, db_path: str = "tools.db") -> Dict[str, Any]:
    verify_credential(credential)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM refunds ORDER BY id DESC LIMIT 50")
        rows = [dict(r) for r in cursor.fetchall()]
        return {"refunds_count": len(rows), "records": rows}
    finally:
        conn.close()
