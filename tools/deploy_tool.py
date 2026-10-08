import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict


def verify_credential(credential: Any) -> None:
    if not credential or not isinstance(credential, str):
        raise PermissionError("Missing or invalid tool credential")


def deploy(
    credential: str,
    target: str,
    version: str = "v1.0.0",
    db_path: str = "tools.db",
) -> Dict[str, Any]:
    verify_credential(credential)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO deployments (cluster_name, version, deployed_at) VALUES (?, ?, ?)",
            (target, version, now_iso),
        )
        conn.commit()
        return {"status": "deployed", "cluster": target, "version": version}
    finally:
        conn.close()
