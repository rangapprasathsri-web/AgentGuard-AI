from typing import Any, Callable, Dict, Optional, Tuple
from tools import cloud_tool, db_tool, deploy_tool, refund_tool, sales_tool


def get_tool_handler(action: str, target: str) -> Optional[Callable[..., Any]]:
    """
    Look up the tool function for (action, target).
    Returns None if no mapping exists.
    """
    if action == "READ":
        if target == "sales_db":
            return lambda cred, params, idemp: sales_tool.forecast(credential=cred)
        elif target in ["customer_orders_db", "customers_prod", "staging_db"]:
            return lambda cred, params, idemp: db_tool.select(
                credential=cred, target=target, record_count=params.get("record_count", 1)
            )

    elif action == "UPDATE":
        if target == "staging_db":
            return lambda cred, params, idemp: db_tool.update_records(
                credential=cred, target=target, record_count=params.get("record_count", 1)
            )

    elif action == "DELETE":
        if target in ["customers_prod", "staging_db"]:
            return lambda cred, params, idemp: db_tool.delete_records(
                credential=cred, target=target, record_count=params.get("record_count", 1)
            )
        elif target == "prod_database":
            return lambda cred, params, idemp: cloud_tool.delete_database(
                credential=cred, target=target
            )

    elif action == "CREATE":
        if target == "payments_api":
            return lambda cred, params, idemp: refund_tool.create_refund(
                credential=cred,
                idempotency_key=idemp,
                customer_id=str(params.get("customer_id", "")),
                amount=int(params.get("amount", 0)),
            )

    elif action == "DEPLOY":
        if target in ["staging_cluster", "prod_cluster"]:
            return lambda cred, params, idemp: deploy_tool.deploy(
                credential=cred, target=target, version=params.get("version", "v1.0.0")
            )

    return None
