import os
import pytest
from unittest.mock import patch, mock_open
from datetime import datetime, timedelta, timezone
from common.schemas import ActionRequest, Source, SourceType, ActionType, DecisionOutcome
from guard.ledger import CumulativeLedger
from common.clock import clock

@pytest.fixture
def empty_ledger(tmp_path):
    db_path = str(tmp_path / "test_s1.db")
    ledger = CumulativeLedger(db_path=db_path, limits_path=str(tmp_path / "limits.yaml"))
    yield ledger
    if os.path.exists(db_path):
        os.remove(db_path)

def test_s1_reject_negative_amount(empty_ledger):
    decision, reason, _, _ = empty_ledger.check_and_reserve(
        reservation_id="res-1",
        agent_id="ag1",
        action="CREATE",
        target="payments_api",
        amount=-50,
        request_hash="hash1"
    )
    assert decision == DecisionOutcome.BLOCK
    assert "positive" in reason.lower()

    decision, reason, _, _ = empty_ledger.check_and_reserve(
        reservation_id="res-2",
        agent_id="ag1",
        action="CREATE",
        target="payments_api",
        amount=0,
        request_hash="hash2"
    )
    assert decision == DecisionOutcome.BLOCK
    assert "positive" in reason.lower()

def test_s1_fail_closed_on_missing_limits(tmp_path):
    ledger = CumulativeLedger(db_path=str(tmp_path / "test_s1.db"), limits_path="/does/not/exist.yaml")
    decision, reason, _, _ = ledger.check_and_reserve(
        reservation_id="res-3",
        agent_id="ag1",
        action="CREATE",
        target="payments_api",
        amount=100,
        request_hash="hash3"
    )
    assert decision == DecisionOutcome.BLOCK
    assert reason == "limits_config_missing"

def test_s1_fail_closed_on_unparsable_limits(tmp_path):
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text("unparsable: [")
    ledger = CumulativeLedger(db_path=str(tmp_path / "test_s1.db"), limits_path=str(limits_path))
    decision, reason, _, _ = ledger.check_and_reserve(
        reservation_id="res-4",
        agent_id="ag1",
        action="CREATE",
        target="payments_api",
        amount=100,
        request_hash="hash4"
    )
    assert decision == DecisionOutcome.BLOCK
    assert reason == "limits_config_unparsable"

def test_s1_rapid_window_honored(empty_ledger, tmp_path):
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text("""
limits:
  - action: CREATE
    target: payments_api
    soft_limit: 1000
    hard_cap: 10000
    rapid_count: 2
    rapid_window_seconds: 10
    window_hours: 24
    """)
    empty_ledger.limits_path = str(limits_path)
    
    # First request
    dec, _, _, _ = empty_ledger.check_and_reserve("r1", "ag1", "CREATE", "payments_api", 500, request_hash="h1")
    assert dec == DecisionOutcome.ALLOW
    
    # Second request in rapid window (rapid_count is 2, so this is allowed?)
    # Wait, the logic is: prior_rapid_count >= rapid_count
    # So 1st (prior=0), 2nd (prior=1) => ALLOW
    dec, _, _, _ = empty_ledger.check_and_reserve("r2", "ag1", "CREATE", "payments_api", 500, request_hash="h2")
    assert dec == DecisionOutcome.ALLOW
    
    # Third request in rapid window (prior=2 >= rapid_count=2, total=1500 > soft_limit=1000)
    dec, _, _, _ = empty_ledger.check_and_reserve("r3", "ag1", "CREATE", "payments_api", 500, request_hash="h3")
    assert dec == DecisionOutcome.BLOCK

def test_s1_window_hours_honored(empty_ledger, tmp_path):
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text("""
limits:
  - action: CREATE
    target: payments_api
    soft_limit: 1000
    hard_cap: 5000
    rapid_count: 10
    rapid_window_seconds: 10
    window_hours: 1
    """)
    empty_ledger.limits_path = str(limits_path)

    # Insert a fake executed transaction 2 hours ago
    now_utc = clock.now_utc()
    old_iso = (now_utc - timedelta(hours=2)).isoformat()
    with empty_ledger._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cumulative_ledger 
            (reservation_id, tenant_id, agent_id, action, target, amount, status, request_hash, created_at, expires_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'EXECUTED', ?, ?, ?, ?)
            """,
            ("old", "demo", "ag1", "CREATE", "payments_api", 4000, "h-old", old_iso, old_iso, old_iso)
        )
        conn.commit()
    
    # Current request of 2000. If 1-hour window is honored, the 4000 is ignored, so 2000 < hard_cap 5000.
    dec, _, total, _ = empty_ledger.check_and_reserve("new", "ag1", "CREATE", "payments_api", 2000, request_hash="h-new")
    assert dec == DecisionOutcome.REVIEW # 2000 > soft_limit 1000
    assert total == 2000
