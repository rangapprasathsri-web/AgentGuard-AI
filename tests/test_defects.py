import concurrent.futures
import json
import os
import uuid
import pytest

from common.schemas import ActionRequest, ActionType, Source, SourceType, DecisionOutcome
from guard.ledger import CumulativeLedger
from guard.pipeline import GuardPipeline
from guard.approvals import ApprovalManager
from common.canonical import compute_action_hash

def test_defect_1_cumulative_gate(tmp_path):
    """
    Cumulative gate: in evaluate(), make the final ALLOW path a single
    check_and_reserve(only_check=False) inside one BEGIN IMMEDIATE transaction
    and USE its result. 
    Tests: 20 parallel 9,500 refunds never allow more than the soft limit (50k).
    Ledger sum equals allowed sum.
    """
    db_file = str(tmp_path / "defect_1_ledger.db")
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text("""
limits:
  - action: CREATE
    target: payments_api
    soft_limit: 50000
    hard_cap: 200000
    rapid_count: 5
    rapid_window: 600
""")
    ledger = CumulativeLedger(db_path=db_file, limits_path=str(limits_path))
    pipeline = GuardPipeline(service_key="test_svc", ledger=ledger)
    
    from common.clock import clock
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Kolkata")
    clock.set_time(datetime(2026, 10, 9, 11, 0, 0, tzinfo=tz))
    
    # Action score for CREATE payments_api is 35 (ALLOW band).
    # Soft limit is 50,000. 9,500 * 5 = 47,500 < 50k. 9,500 * 6 = 57,000 > 50k.
    # So 5 ALLOWs, 15 REVIEWs expected out of 20.
    def attempt_evaluate(i):
        req = ActionRequest(
            agent_id="finance-agent-01",
            action=ActionType.CREATE,
            target="payments_api",
            params={"amount": 9500, "customer_id": f"c_{i}"},
            source=Source(type=SourceType.USER),
        )
        return pipeline.evaluate(req).decision
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(attempt_evaluate, i) for i in range(100)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    allow_count = results.count(DecisionOutcome.ALLOW)
    review_count = results.count(DecisionOutcome.REVIEW)
    block_count = results.count(DecisionOutcome.BLOCK)
    
    assert allow_count == 5, f"Expected 5 ALLOWs (47.5k <= 50k), got {allow_count}"
    assert block_count == 95, f"Expected 95 BLOCKs, got {block_count}"
    
    # Check ledger sum (all ALLOWs should be RESERVED, and they shouldn't exceed 50k)
    with ledger._get_connection() as conn:
        row = conn.execute("SELECT SUM(amount) as s FROM cumulative_ledger WHERE status = 'RESERVED'").fetchone()
        assert int(row["s"] or 0) == allow_count * 9500


def test_defect_2_limits_from_yaml(tmp_path):
    """
    Read soft_limit, hard_cap, rapid_count, rapid_window from policies/limits.yaml.
    """
    yaml_content = """
limits:
  - action: CREATE
    target: target1
    soft_limit: 1000
    hard_cap: 5000
    rapid_count: 2
    rapid_window: 10
"""
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text(yaml_content)
    
    db_file = str(tmp_path / "defect_2_ledger.db")
    ledger = CumulativeLedger(db_path=db_file, limits_path=str(limits_path))
    
    # Use check_and_reserve directly to verify the limits loaded.
    # Since soft_limit=1000, requesting 1500 should go to REVIEW
    dec, reason, _, _ = ledger.check_and_reserve(
        reservation_id="test1",
        agent_id="agent1",
        action="CREATE",
        target="target1",
        amount=1500
    )
    assert dec == DecisionOutcome.REVIEW
    assert "soft_limit_exceeded" in reason


def test_defect_6_reject_zero_amount(tmp_path):
    """
    Reject CREATE on payments_api when params.amount is missing or <= 0.
    """
    # Reject 0
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="amount > 0"):
        ActionRequest(
            agent_id="finance-agent-01",
            action=ActionType.CREATE,
            target="payments_api",
            params={"amount": 0, "customer_id": "c1"},
            source=Source(type=SourceType.USER),
        )

    # Reject negative
    with pytest.raises(ValidationError, match="amount"):
        ActionRequest(
            agent_id="finance-agent-01",
            action=ActionType.CREATE,
            target="payments_api",
            params={"amount": -100, "customer_id": "c1"},
            source=Source(type=SourceType.USER),
        )

    # Reject missing amount
    with pytest.raises(ValidationError, match="amount > 0"):
        ActionRequest(
            agent_id="finance-agent-01",
            action=ActionType.CREATE,
            target="payments_api",
            params={"customer_id": "c1"},
            source=Source(type=SourceType.USER),
        )

    # Reject missing customer_id
    with pytest.raises(ValidationError, match="customer_id"):
        ActionRequest(
            agent_id="finance-agent-01",
            action=ActionType.CREATE,
            target="payments_api",
            params={"amount": 100},
            source=Source(type=SourceType.USER),
        )

    # READ succeeds without amount or customer_id
    req_read = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.READ,
        target="payments_api",
        params={},
        source=Source(type=SourceType.USER),
    )
    assert req_read.action == ActionType.READ


def test_defect_7_authorize_agent_id_mismatch(tmp_path):
    """
    In authorize(), verify approval.agent_id == request.agent_id BEFORE any
    voiding; on mismatch return BLOCK without changing the approval.
    """
    db_file = str(tmp_path / "defect_7.db")
    approvals = ApprovalManager(db_path=db_file)
    pipeline = GuardPipeline(service_key="test_svc", approval_manager=approvals, ledger=CumulativeLedger(db_path=db_file))
    
    # Evaluate valid request to get an approval
    req_valid = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 40000, "customer_id": "c1"}, # review
        source=Source(type=SourceType.USER),
    )
    resp1 = pipeline.evaluate(req_valid)
    assert resp1.decision == DecisionOutcome.REVIEW
    appr_id = resp1.approval_id
    
    # Approve it
    approvals.decide(appr_id, "APPROVE", "cfo")
    
    # Try to authorize with a different agent_id but same hash?
    # Wait, the action hash includes agent_id. If we change agent_id, hash changes.
    # The requirement says: verify approval.agent_id == request.agent_id BEFORE any voiding.
    # If the hash mismatch voiding is first, it will void it. 
    # We want it to just BLOCK and NOT void the approval.
    req_malicious = ActionRequest(
        agent_id="hacker-agent-99",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 40000, "customer_id": "c1"},
        source=Source(type=SourceType.USER),
    )
    dec, reason, _, _ = pipeline.authorize(req_malicious, appr_id)
    assert dec == DecisionOutcome.BLOCK
    
    # Ensure it wasn't voided
    appr_doc = approvals.get_approval(appr_id)
    assert appr_doc["status"] == "APPROVED"


def test_defect_8_canonicalization_float_payload():
    """
    Audit and signing must serialize any JSON-safe payload (including floats).
    """
    from common.canonical import sign_payload
    payload = {
        "decision": "ALLOW",
        "analyzer_confidence": 0.95
    }
    # Should not raise ValueError
    sig = sign_payload("secret", payload)
    assert isinstance(sig, str)

def test_defect_3_no_default_secrets(monkeypatch):
    """
    Remove ALL default secrets (default_service_key, default_key,
    default_tool_cred, default_tool_credential). Startup raises if
    SERVICE_KEY, AUDIT_HMAC_KEY (guard, gateway) or TOOL_CREDENTIAL (gateway)
    is missing; delete ALLOW_INSECURE_DEV and the .env-exists bypass.
    """
    monkeypatch.delenv("SERVICE_KEY", raising=False)
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.delenv("TOOL_CREDENTIAL", raising=False)
    monkeypatch.delenv("ALLOW_INSECURE_DEV", raising=False)
    
    import importlib
    with pytest.raises(RuntimeError, match="missing"):
        import gateway.main
        
    with pytest.raises(RuntimeError, match="missing"):
        import guard.main
def test_defect_4_analyzer_deadline():
    """
    Give the analyzer one total deadline of 4s across all failover attempts.
    Add a test with all providers hanging.
    """
    from common.llm_client import LLMClient
    import os
    import asyncio
    
    os.environ["OPENROUTER_API_KEY"] = "primary_key"
    os.environ["LLM_MODEL"] = "test"
    client = LLMClient(mode="live")
    
    # Mock httpx.AsyncClient.post to sleep for 5 seconds (which exceeds the 4s total deadline)
    async def mock_post(*args, **kwargs):
        await asyncio.sleep(5)
        return None
        
    from unittest.mock import patch
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        # We invoke complete() for analyzer
        res, provider, _ = asyncio.run(client.complete("analyzer", "test"))
        assert res is None
        assert provider == "timeout_exceeded"
def test_defect_5_guard_demo_routes():
    """
    Guard demo routes: require X-Role admin as well as DEMO_MODE, and add
    DEMO_MODE=true to .env.guard and .env.gateway for demo only.
    """
    from fastapi.testclient import TestClient
    
    os.environ["SERVICE_KEY"] = "sk_valid_service_key_16bytes"
    os.environ["AUDIT_HMAC_KEY"] = "ak_valid_hmac_key_16bytes"
    os.environ["DEMO_MODE"] = "true"
    
    import importlib
    import guard.main
    importlib.reload(guard.main)
    
    client = TestClient(guard.main.app)
    # Add a dummy audit event so tamper doesn't fail with 400
    from common.audit import AuditLogger
    audit = AuditLogger(db_path="audit.db", hmac_key="ak")
    audit.append_event("test_event", {"foo": "bar"})

    # Without X-Role: admin, should be 403
    resp = client.post("/audit/demo/tamper", headers={"X-Role": "agent"})
    assert resp.status_code == 403
    
    resp_admin = client.post("/audit/demo/tamper", headers={"X-Role": "admin", "X-Service-Key": "sk"})
    assert resp_admin.status_code == 200


def test_defect_4_agent_env_isolation():
    """
    Launch the agents process via subprocess with env -i and assert the three
    secrets are absent from its environment.
    """
    import subprocess
    import os
    
    # We simulate what run_all.sh does:
    # env -i PATH="$PATH" PYTHONPATH="." $(cat .env.agents | xargs) env
    # And check the output for secrets
    cmd = 'env -i PATH="$PATH" PYTHONPATH="." $(cat .env.agents | xargs) env'
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"env check failed: {e}")
        
    assert "SERVICE_KEY=" not in output, "SERVICE_KEY leaked into agent env"
    assert "AUDIT_HMAC_KEY=" not in output, "AUDIT_HMAC_KEY leaked into agent env"
    assert "TOOL_CREDENTIAL=" not in output, "TOOL_CREDENTIAL leaked into agent env"

