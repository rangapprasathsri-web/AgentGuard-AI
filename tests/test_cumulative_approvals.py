import concurrent.futures
from datetime import datetime
import os
from zoneinfo import ZoneInfo
import pytest
from common.clock import clock
from common.schemas import ActionRequest, ActionType, DecisionOutcome, Source, SourceType
from guard.approvals import ApprovalManager
from guard.ledger import CumulativeLedger
from guard.pipeline import GuardPipeline
from guard.registries import AgentRegistry, ResourceRegistry
from guard.risk import RiskEngine
from guard.rules import HardRulesEngine


@pytest.fixture
def clean_guard(tmp_path):
    db_file = str(tmp_path / "test_guard.db")
    ledger = CumulativeLedger(db_path=db_file)
    approvals = ApprovalManager(db_path=db_file)
    pipeline = GuardPipeline(
        service_key="test_service_key_1234567890",
        ledger=ledger,
        approval_manager=approvals,
    )
    return pipeline, ledger, approvals


def test_scenario_2_finance_review_approve_and_consume(clean_guard):
    pipeline, ledger, approvals = clean_guard
    tz = ZoneInfo("Asia/Kolkata")
    # 02:30 local time (off-hours)
    clock.set_time(datetime(2026, 10, 9, 2, 30, 0, tzinfo=tz))

    req = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 85000, "customer_id": "cust_999"},
        source=Source(type=SourceType.USER),
    )

    eval_resp = pipeline.evaluate(req)
    assert eval_resp.risk_score == 65
    assert eval_resp.decision == DecisionOutcome.REVIEW
    assert eval_resp.approval_id is not None
    appr_id = eval_resp.approval_id

    # Approver approves
    ok, err = approvals.decide(appr_id, "APPROVE", approver="human_approver_1", reason="Authorized by CFO")
    assert ok is True

    # Resubmit with approval_id
    dec, reason, auth_payload, sig = pipeline.authorize(req, appr_id)
    assert dec == DecisionOutcome.ALLOW
    assert reason == "authorized"
    assert auth_payload["status"] == "authorized"

    # Confirm reservation as executed using decision_id
    ledger.confirm_reservation(auth_payload["decision_id"], "executed")

    # Check cumulative total in ledger
    with ledger._get_connection() as conn:
        row = conn.execute("SELECT SUM(amount) as s FROM cumulative_ledger WHERE status = 'EXECUTED'").fetchone()
        assert int(row["s"]) == 85000


def test_scenario_6_split_refund_rapid_velocity(clean_guard):
    pipeline, ledger, _ = clean_guard
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 11, 0, 0, tzinfo=tz))

    # Five refunds of 9500 within one minute
    for i in range(5):
        req = ActionRequest(
            agent_id="finance-agent-01",
            action=ActionType.CREATE,
            target="payments_api",
            params={"amount": 9500, "customer_id": f"cust_{i}"},
            source=Source(type=SourceType.USER),
        )
        resp = pipeline.evaluate(req)
        assert resp.risk_score == 35
        assert resp.decision == DecisionOutcome.ALLOW
        # Confirm reservation as executed immediately
        ledger.confirm_reservation(resp.decision_id, "executed")

    # Check total executed
    with ledger._get_connection() as conn:
        row = conn.execute("SELECT SUM(amount) as s FROM cumulative_ledger WHERE status = 'EXECUTED'").fetchone()
        assert int(row["s"]) == 47500

    # Sixth refund of 9500 within rapid window (10 min)
    req6 = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 9500, "customer_id": "cust_6"},
        source=Source(type=SourceType.USER),
    )
    resp6 = pipeline.evaluate(req6)
    assert resp6.decision == DecisionOutcome.BLOCK
    assert resp6.decision_source == "cumulative_gate"


def test_scenario_7_tampered_approval_action_hash(clean_guard):
    pipeline, _, approvals = clean_guard
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 2, 30, 0, tzinfo=tz))

    req = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 85000, "customer_id": "cust_999"},
        source=Source(type=SourceType.USER),
    )
    resp = pipeline.evaluate(req)
    appr_id = resp.approval_id

    # Approver approves 85000
    approvals.decide(appr_id, "APPROVE", approver="human_approver_1")

    # Tampered request: amount changed to 850000 with same approval_id
    tampered_req = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 850000, "customer_id": "cust_999"},
        source=Source(type=SourceType.USER),
    )
    dec, reason, _, _ = pipeline.authorize(tampered_req, appr_id)
    assert dec == DecisionOutcome.BLOCK
    assert reason == "hash_mismatch"

    # Approval must be VOIDED (Invariant I6)
    appr = approvals.get_approval(appr_id)
    assert appr["status"] == "VOIDED"


def test_scenario_8_replay_consumed_approval(clean_guard):
    pipeline, ledger, approvals = clean_guard
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 2, 30, 0, tzinfo=tz))

    req = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 85000, "customer_id": "cust_999"},
        source=Source(type=SourceType.USER),
    )
    resp = pipeline.evaluate(req)
    appr_id = resp.approval_id
    approvals.decide(appr_id, "APPROVE", approver="human_approver_1")

    # First authorization consumes it
    dec1, reason1, _, _ = pipeline.authorize(req, appr_id)
    assert dec1 == DecisionOutcome.ALLOW
    assert reason1 == "authorized"

    # Replay attempt: try to reuse the consumed approval
    dec2, reason2, _, _ = pipeline.authorize(req, appr_id)
    assert dec2 == DecisionOutcome.BLOCK
    assert reason2 == "replay_attempt"


def test_concurrency_parallel_approval_consumptions(clean_guard):
    pipeline, _, approvals = clean_guard
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 2, 30, 0, tzinfo=tz))

    req = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 85000, "customer_id": "cust_concurrent"},
        source=Source(type=SourceType.USER),
    )
    resp = pipeline.evaluate(req)
    appr_id = resp.approval_id
    approvals.decide(appr_id, "APPROVE", approver="human_approver_1")

    # 20 concurrent attempts to consume the EXACT SAME approval
    successes = 0
    failures = 0

    def attempt_consume():
        dec, reason, _, _ = pipeline.authorize(req, appr_id)
        return dec, reason

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_consume) for _ in range(20)]
        for f in concurrent.futures.as_completed(futures):
            dec, reason = f.result()
            if dec == DecisionOutcome.ALLOW and reason == "authorized":
                successes += 1
            else:
                failures += 1

    # Exactly ONE must succeed, and nineteen must fail! Single-use invariant I5!
    assert successes == 1
    assert failures == 19
