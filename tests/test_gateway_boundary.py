import os
import re
from unittest.mock import AsyncMock, patch
import pytest
from common.audit import AuditLogger
from gateway.enforcement import GatewayEnforcer
from gateway.guard_client import GuardClient
from tools import db_tool, refund_tool


@pytest.fixture
def test_enforcer(tmp_path):
    audit_file = str(tmp_path / "gateway_test_audit.db")
    audit_logger = AuditLogger(db_path=audit_file, hmac_key="test_hmac_gateway_key")
    guard_client = GuardClient(guard_url="http://localhost:9999", service_key="test_svc_key")
    enforcer = GatewayEnforcer(
        guard_client=guard_client,
        audit_logger=audit_logger,
        tool_credential="test_tool_cred_123",
    )
    return enforcer, audit_logger


def test_scenario_10_fail_closed_guard_unreachable(test_enforcer):
    import asyncio
    enforcer, audit_logger = test_enforcer

    async def run_test():
        body = {
            "agent_id": "database-agent-01",
            "action": "READ",
            "target": "customer_orders_db",
            "params": {"record_count": 1},
            "source": {"type": "user"},
        }

        status_code, resp = await enforcer.execute_action(
            raw_body=body,
            actor="database-agent-01",
            role="agent",
        )

        # Invariant I2: Must fail closed with 503 denied_fail_closed
        assert status_code == 503
        assert resp["status"] == "denied_fail_closed"
        assert resp["reason"] == "guard_unreachable"

        # Gateway must log guard_unreachable event
        events = audit_logger.list_events(event_type="security_signal")
        assert any(e["payload"].get("signal") == "guard_unreachable" for e in events)

        # Audit chain must remain 100% valid
        verify = audit_logger.verify_chain()
        assert verify["valid"] is True

    asyncio.run(run_test())


def test_scenario_12_direct_tool_access_permission_error():
    # Calling tool without valid credential raises PermissionError (Invariant I1)
    with pytest.raises(PermissionError):
        db_tool.select(credential=None, target="customers_prod", record_count=1)

    with pytest.raises(PermissionError):
        db_tool.select(credential="", target="customers_prod", record_count=1)

    with pytest.raises(PermissionError):
        refund_tool.create_refund(
            credential=None, idempotency_key="idemp_1", customer_id="c1", amount=100
        )


def test_scenario_12_static_boundary_test():
    """
    Boundary test (I1, I8): a static test fails if any file under agents/
    imports guard, gateway, tools, demo, or common.audit, or references
    TOOL_CREDENTIAL, SERVICE_KEY, or AUDIT_HMAC_KEY.
    """
    agents_dir = "agents"
    forbidden_imports = ["guard", "gateway", "tools", "demo", "common.audit"]
    forbidden_tokens = ["TOOL_CREDENTIAL", "SERVICE_KEY", "AUDIT_HMAC_KEY"]

    for root, _, files in os.walk(agents_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as file:
                    content = file.read()
                    for imp in forbidden_imports:
                        # Check import statements
                        assert not re.search(
                            rf"(?:from|import)\s+{re.escape(imp)}", content
                        ), f"Boundary violation in {fpath}: imports '{imp}'"
                    for tok in forbidden_tokens:
                        assert (
                            tok not in content
                        ), f"Boundary violation in {fpath}: references token '{tok}'"


def test_scenario_14_role_abuse_actor_mismatch(test_enforcer):
    import asyncio
    enforcer, audit_logger = test_enforcer

    async def run_test():
        body = {
            "agent_id": "database-agent-01",
            "action": "READ",
            "target": "customer_orders_db",
            "params": {"record_count": 1},
            "source": {"type": "user"},
        }

        # 1. Actor mismatch: actor does not match body agent_id
        code, resp = await enforcer.execute_action(
            raw_body=body,
            actor="different-agent-99",
            role="agent",
        )
        assert code == 403
        assert resp["error"] == "forbidden_role_or_actor_mismatch"

        # 2. Role mismatch: role is approver instead of agent on gateway execute
        code2, resp2 = await enforcer.execute_action(
            raw_body=body,
            actor="database-agent-01",
            role="approver",
        )
        assert code2 == 403
        assert resp2["error"] == "forbidden_role_or_actor_mismatch"

        # Audit events logged
        signals = audit_logger.list_events(event_type="security_signal")
        assert any(s["payload"].get("signal") == "role_actor_mismatch" for s in signals)

    asyncio.run(run_test())
