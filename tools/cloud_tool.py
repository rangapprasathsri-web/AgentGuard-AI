import sqlite3
from typing import Any, Dict


def verify_credential(credential: Any) -> None:
    if not credential or not isinstance(credential, str):
        raise PermissionError("Missing or invalid tool credential")


def delete_database(
    credential: str, target: str, db_path: str = "tools.db"
) -> Dict[str, Any]:
    verify_credential(credential)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("DROP TABLE IF EXISTS prod_database")
        conn.commit()
        return {"status": "database_deleted", "target": target}
    finally:
        conn.close()
