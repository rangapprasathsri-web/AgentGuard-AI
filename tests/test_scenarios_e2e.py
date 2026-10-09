from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from common.clock import clock
from common.schemas import ActionRequest, ActionType, DecisionOutcome, Source, SourceType
from guard.pipeline import GuardPipeline
from guard.registries import AgentRegistry, ResourceRegistry


@pytest.fixture(autouse=True)
def setup_clock():
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 11, 0, 0, tzinfo=tz))
    yield
    clock.reset()


def test_scenario_4_external_content_injection_defense():
    agent_reg = AgentRegistry()
    res_reg = ResourceRegistry()
    pipeline = GuardPipeline(service_key="test_svc", agent_registry=agent_reg, resource_registry=res_reg)

    # 4(a) devops DELETE prod_database with source external_content -> BLOCK, matches include INJ-002
    req_a = ActionRequest(
        agent_id="devops-agent-01",
        action=ActionType.DELETE,
        target="prod_database",
        params={"record_count": 1},
        source=Source(
            type=SourceType.EXTERNAL_CONTENT,
            content_excerpt="Attacker instructions to delete database",
        ),
    )
    resp_a = pipeline.evaluate(req_a)
    assert resp_a.decision == DecisionOutcome.BLOCK
    matched_ids_a = [p.policy_id for p in resp_a.matched_policies]
    assert "INJ-002" in matched_ids_a
    # Also matches PERM-001 because devops agent doesn't have permission to DELETE prod_database
    assert "PERM-001" in matched_ids_a

    # 4(b) database-agent DELETE staging_db record_count 10 with source external_content
    # Note: database-agent holds explicit permission to DELETE staging_db.
    # Therefore, matched_policies must be EXACTLY [INJ-002]!
    req_b = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.DELETE,
        target="staging_db",
        params={"record_count": 10},
        source=Source(
            type=SourceType.EXTERNAL_CONTENT,
            content_excerpt="External injection prompt",
        ),
    )
    resp_b = pipeline.evaluate(req_b)
    assert resp_b.decision == DecisionOutcome.BLOCK
    matched_ids_b = [p.policy_id for p in resp_b.matched_policies]
    assert matched_ids_b == ["INJ-002"]


def test_scenario_15_admin_kill_switch():
    agent_reg = AgentRegistry()
    pipeline = GuardPipeline(service_key="test_svc", agent_registry=agent_reg)

    req = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.READ,
        target="customer_orders_db",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )

    # Initial request is ALLOW
    resp_active = pipeline.evaluate(req)
    assert resp_active.decision == DecisionOutcome.ALLOW

    # Admin sets database-agent-01 to inactive (Kill switch)
    updated = agent_reg.set_status("database-agent-01", "inactive")
    assert updated is True

    # Next request must be BLOCKED with AGT-001
    resp_inactive = pipeline.evaluate(req)
    assert resp_inactive.decision == DecisionOutcome.BLOCK
    matched_ids = [p.policy_id for p in resp_inactive.matched_policies]
    assert "AGT-001" in matched_ids

    # Restore agent status
    agent_reg.set_status("database-agent-01", "active")
    resp_restored = pipeline.evaluate(req)
    assert resp_restored.decision == DecisionOutcome.ALLOW
