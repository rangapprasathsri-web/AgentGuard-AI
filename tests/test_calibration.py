from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from common.clock import clock
from common.schemas import ActionRequest, ActionType, DecisionOutcome, Source, SourceType
from guard.registries import AgentRegistry, ResourceRegistry
from guard.risk import RiskEngine
from guard.rules import HardRulesEngine


@pytest.fixture(autouse=True)
def setup_env():
    # Set business hours (11:00 Asia/Kolkata)
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 11, 0, 0, tzinfo=tz))
    yield
    clock.reset()


def test_scenario_1_database_and_analytics_read():
    agent_reg = AgentRegistry()
    res_reg = ResourceRegistry()
    rules_engine = HardRulesEngine()
    risk_engine = RiskEngine()

    # 1. database-agent READ customer_orders_db, record_count 1
    req = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.READ,
        target="customer_orders_db",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )
    agent = agent_reg.get(req.agent_id)
    resource = res_reg.get(req.target)
    matches = rules_engine.evaluate_all(req, agent, resource, res_reg.is_known(req.target))
    assert len(matches) == 0

    score, risk_level, factors, decision = risk_engine.evaluate(
        req, agent, resource, res_reg.is_known(req.target)
    )
    assert score == 20
    assert decision == DecisionOutcome.ALLOW
    assert risk_level == "LOW"

    # 2. analytics-agent READ sales_db
    req2 = ActionRequest(
        agent_id="analytics-agent-01",
        action=ActionType.READ,
        target="sales_db",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )
    agent2 = agent_reg.get(req2.agent_id)
    resource2 = res_reg.get(req2.target)
    matches2 = rules_engine.evaluate_all(req2, agent2, resource2, res_reg.is_known(req2.target))
    assert len(matches2) == 0

    score2, _, _, decision2 = risk_engine.evaluate(
        req2, agent2, resource2, res_reg.is_known(req2.target)
    )
    assert score2 == 20
    assert decision2 == DecisionOutcome.ALLOW


def test_scenario_3_destructive_pii_and_unauthorized():
    agent_reg = AgentRegistry()
    res_reg = ResourceRegistry()
    rules_engine = HardRulesEngine()
    risk_engine = RiskEngine()

    # database-agent DELETE customers_prod record_count 50000
    req = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.DELETE,
        target="customers_prod",
        params={"record_count": 50000},
        source=Source(type=SourceType.USER),
    )
    agent = agent_reg.get(req.agent_id)
    resource = res_reg.get(req.target)
    matches = rules_engine.evaluate_all(req, agent, resource, res_reg.is_known(req.target))
    matched_ids = [m.policy_id for m in matches]
    assert "PERM-001" in matched_ids
    assert "DATA-004" in matched_ids

    score, _, _, decision = risk_engine.evaluate(
        req, agent, resource, res_reg.is_known(req.target)
    )
    assert score == 100
    assert decision == DecisionOutcome.BLOCK

    # devops-agent DELETE prod_database record_count 1
    req2 = ActionRequest(
        agent_id="devops-agent-01",
        action=ActionType.DELETE,
        target="prod_database",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )
    agent2 = agent_reg.get(req2.agent_id)
    resource2 = res_reg.get(req2.target)
    matches2 = rules_engine.evaluate_all(req2, agent2, resource2, res_reg.is_known(req2.target))
    assert any(m.policy_id == "PERM-001" for m in matches2)


def test_scenario_5_external_content_refund():
    agent_reg = AgentRegistry()
    res_reg = ResourceRegistry()
    rules_engine = HardRulesEngine()
    risk_engine = RiskEngine()

    # Case a: amount 9000 at 11:00 -> score 50, REVIEW
    req_a = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 9000, "customer_id": "cust_123"},
        source=Source(type=SourceType.EXTERNAL_CONTENT, content_excerpt="Please refund ₹9000"),
    )
    agent_a = agent_reg.get(req_a.agent_id)
    resource_a = res_reg.get(req_a.target)
    matches_a = rules_engine.evaluate_all(req_a, agent_a, resource_a, True)
    assert len(matches_a) == 0

    score_a, risk_level_a, factors_a, decision_a = risk_engine.evaluate(
        req_a, agent_a, resource_a, True
    )
    assert score_a == 50
    assert decision_a == DecisionOutcome.REVIEW

    # Case b: amount 90000 at 11:00 -> score 70, BLOCK
    req_b = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 90000, "customer_id": "cust_123"},
        source=Source(type=SourceType.EXTERNAL_CONTENT, content_excerpt="Please refund ₹90000"),
    )
    agent_b = agent_reg.get(req_b.agent_id)
    resource_b = res_reg.get(req_b.target)
    score_b, risk_level_b, factors_b, decision_b = risk_engine.evaluate(
        req_b, agent_b, resource_b, True
    )
    assert score_b == 70
    assert decision_b == DecisionOutcome.BLOCK


def test_scenario_9_lying_agent_context_resolution():
    agent_reg = AgentRegistry()
    res_reg = ResourceRegistry()
    risk_engine = RiskEngine()

    # Claims dev and public via extra fields
    req = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.READ,
        target="customers_prod",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
        environment="dev",
        data_class="public",
    )
    assert req.unverified_claims.get("environment") == "dev"
    assert req.unverified_claims.get("data_class") == "public"

    # Context facts come from registries, never request (Invariant I3)
    resource = res_reg.get(req.target)
    assert resource.environment == "production"
    assert resource.data_class == "PII"

    agent = agent_reg.get(req.agent_id)
    score, _, _, decision = risk_engine.evaluate(req, agent, resource, True)
    assert score == 35
    assert decision == DecisionOutcome.ALLOW


def test_scenario_13_unknown_target():
    agent_reg = AgentRegistry()
    res_reg = ResourceRegistry()
    rules_engine = HardRulesEngine()
    risk_engine = RiskEngine()

    # READ mystery_db -> REVIEW (score 45, floor)
    req_read = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.READ,
        target="mystery_db",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )
    agent = agent_reg.get(req_read.agent_id)
    resource = res_reg.get(req_read.target)  # None
    is_known = res_reg.is_known(req_read.target)  # False

    score, _, _, decision = risk_engine.evaluate(req_read, agent, resource, is_known)
    assert score == 45
    assert decision == DecisionOutcome.REVIEW

    # DELETE mystery_db -> BLOCK, matches REG-003
    req_del = ActionRequest(
        agent_id="database-agent-01",
        action=ActionType.DELETE,
        target="mystery_db",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )
    matches_del = rules_engine.evaluate_all(req_del, agent, None, False)
    assert any(m.policy_id == "REG-003" for m in matches_del)
