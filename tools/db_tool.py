import sqlite3
from typing import Any, Dict, List


def verify_credential(credential: Any) -> None:
    if not credential or not isinstance(credential, str):
        raise PermissionError("Missing or invalid tool credential")


def select(
    credential: str, target: str, record_count: int = 1, db_path: str = "tools.db"
) -> Dict[str, Any]:
    verify_credential(credential)
    # Hard bound: touch at most record_count rows
    bounded_count = max(1, record_count)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(f"SELECT * FROM {target} LIMIT ?", (bounded_count,))
        rows = [dict(r) for r in cursor.fetchall()]
        return {"target": target, "rows_read": len(rows), "records": rows}
    finally:
        conn.close()


def update_records(
    credential: str, target: str, record_count: int, db_path: str = "tools.db"
) -> Dict[str, Any]:
    verify_credential(credential)
    bounded_count = max(1, record_count)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        # Update at most record_count rows
        cursor = conn.execute(
            f"UPDATE {target} SET updated_at = datetime('now') WHERE id IN (SELECT id FROM {target} LIMIT ?)",
            (bounded_count,),
        )
        affected = cursor.rowcount
        conn.commit()
        return {"target": target, "rows_updated": affected}
    finally:
        conn.close()


def delete_records(
    credential: str, target: str, record_count: int, db_path: str = "tools.db"
) -> Dict[str, Any]:
    verify_credential(credential)
    bounded_count = max(1, record_count)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cursor = conn.execute(
            f"DELETE FROM {target} WHERE id IN (SELECT id FROM {target} LIMIT ?)",
            (bounded_count,),
        )
        affected = cursor.rowcount
        conn.commit()
        return {"target": target, "rows_deleted": affected}
    finally:
        conn.close()
