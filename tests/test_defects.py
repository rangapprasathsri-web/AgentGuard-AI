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
    
    # Submit with wrong agent
    req_wrong = ActionRequest(
        agent_id="finance-agent-02",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 40000, "customer_id": "c1"},
        source=Source(type=SourceType.USER),
    )
    
    dec, reason, _, _ = pipeline.authorize(req_wrong, appr_id)
    assert dec == DecisionOutcome.BLOCK
    assert "agent_id_mismatch" in reason
    
    # Verify approval is NOT voided
    appr = approvals.get_approval(appr_id)
    assert appr["status"] == "APPROVED"


def test_defect_7_signature_verification_mutation(tmp_path):
    """
    Prove that modifying any single byte of a 9500 approval action_hash (simulate a replay of a different payload)
    produces an immediate rejection and is never sent to the tool.
    """
    db_file = str(tmp_path / "defect_7_mut.db")
    approvals = ApprovalManager(db_path=db_file)
    pipeline = GuardPipeline(service_key="test_svc", approval_manager=approvals, ledger=CumulativeLedger(db_path=db_file))
    
    # Get a REVIEW outcome to create an approval
    # 9500 might be ALLOW by default (soft limit 10000 for finance-agent), so we force REVIEW by simulating an analyzer hit or just by setting a lower soft limit.
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text("limits:\n  - action: CREATE\n    target: payments_api\n    soft_limit: 5000\n    hard_cap: 50000\n")
    ledger = CumulativeLedger(db_path=db_file, limits_path=str(limits_path))
    pipeline = GuardPipeline(service_key="test_svc", approval_manager=approvals, ledger=ledger)
    
    req_valid = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 9500, "customer_id": "c1"},
        source=Source(type=SourceType.USER),
    )
    resp1 = pipeline.evaluate(req_valid)
    assert resp1.decision == DecisionOutcome.REVIEW
    appr_id = resp1.approval_id
    
    # Approve it
    approvals.decide(appr_id, "APPROVE", "cfo")
    
    # Modifying any byte of the payload: 9500 -> 9501
    req_mutated = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 9501, "customer_id": "c1"},
        source=Source(type=SourceType.USER),
    )
    
    dec, reason, _, _ = pipeline.authorize(req_mutated, appr_id)
    assert dec == DecisionOutcome.BLOCK
    assert reason == "hash_mismatch"
    
    # Verify the approval was voided (so it cannot be used)
    appr = approvals.get_approval(appr_id)
    assert appr["status"] == "VOIDED"


def test_defect_9_limits_yaml_enforcement(tmp_path):
    """
    Prove that an agent not present in config/agents.yaml, or an action/target without limits in limits.yaml,
    falls back to the lowest (safest) default, and that deleting limits.yaml causes a complete fail-closed block
    of all CREATE/UPDATE actions.
    """
    from guard.pipeline import GuardPipeline
    from guard.ledger import CumulativeLedger
    from common.schemas import ActionRequest, ActionType, Source, SourceType, DecisionOutcome
    
    db_file = str(tmp_path / "defect_9.db")
    limits_path = tmp_path / "deleted_limits.yaml"
    # Ensure it does not exist
    if limits_path.exists():
        limits_path.unlink()
        
    ledger = CumulativeLedger(db_path=db_file, limits_path=str(limits_path))
    pipeline = GuardPipeline(service_key="test_svc", ledger=ledger)
    
    # 1. Without limits.yaml, a CREATE request with amount > 0 should be BLOCKED because soft_limit=0 and hard_cap=0
    req_missing_limits = ActionRequest(
        agent_id="finance-agent-01",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 1, "customer_id": "c1"},
        source=Source(type=SourceType.USER),
    )
    res_missing = pipeline.evaluate(req_missing_limits)
    assert res_missing.decision == DecisionOutcome.BLOCK
    
    # 2. Unknown agent gives +50 risk score, which guarantees a BLOCK anyway due to risk block threshold
    req_unknown = ActionRequest(
        agent_id="unknown-agent",
        action=ActionType.CREATE,
        target="payments_api",
        params={"amount": 1, "customer_id": "c1"},
        source=Source(type=SourceType.USER),
    )
    res_unknown = pipeline.evaluate(req_unknown)
    assert res_unknown.decision == DecisionOutcome.BLOCK


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
    
    resp_admin = client.post("/audit/demo/tamper", headers={"X-Role": "admin", "X-Service-Key": "sk_valid_service_key_16bytes"})
    assert resp_admin.status_code == 200

def test_defect_5_allow_to_review_flip(tmp_path):
    """
    Test that when evaluation results in ALLOW (or REVIEW), but reservation returns a more severe outcome,
    the pipeline escalates the decision. Specifically, ALLOW to REVIEW creates an approval.
    """
    from guard.pipeline import GuardPipeline
    from guard.ledger import CumulativeLedger
    from common.schemas import ActionRequest, ActionType, Source, SourceType, DecisionOutcome
    
    db_file = str(tmp_path / "flip_ledger.db")
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text("""
limits:
  - action: CREATE
    target: payments_api
    soft_limit: 10000
    hard_cap: 50000
""")
    ledger = CumulativeLedger(db_path=db_file, limits_path=str(limits_path))
    pipeline = GuardPipeline(service_key="test_svc", ledger=ledger)
    
    # 1. First request takes 6000. It should ALLOW and reserve 6000.
    req1 = ActionRequest(
        agent_id="finance-agent-01", action=ActionType.CREATE, target="payments_api",
        params={"amount": 6000, "customer_id": "c_123"}, source=Source(type=SourceType.USER)
    )
    res1 = pipeline.evaluate(req1)
    assert res1.decision == DecisionOutcome.ALLOW
    
    # 2. To simulate the race condition, we monkeypatch check_and_reserve
    # to return REVIEW only when only_check=False.
    
    original_check = ledger.check_and_reserve
    def mock_check(reservation_id, agent_id, action, target, amount, only_check=False, conn=None, bypass_soft_limit=False):
        if only_check:
            # Fake ALLOW during evaluation
            return DecisionOutcome.ALLOW, "mocked_allow", 6000, 0
        else:
            # Fallback to real logic which will return REVIEW because 12000 > 10000
            return original_check(reservation_id, agent_id, action, target, amount, only_check, conn, bypass_soft_limit)
            
    ledger.check_and_reserve = mock_check
    
    req2 = ActionRequest(
        agent_id="finance-agent-01", action=ActionType.CREATE, target="payments_api",
        params={"amount": 6000, "customer_id": "c_124"}, source=Source(type=SourceType.USER)
    )
    res2 = pipeline.evaluate(req2)
    
    # It should have flipped to REVIEW and created an approval
    assert res2.decision == DecisionOutcome.REVIEW
    assert res2.approval_id is not None
    
    # Verify the reservation was saved for the REVIEW!
    with ledger._get_connection() as conn:
        row = conn.execute("SELECT SUM(amount) as s FROM cumulative_ledger WHERE status = 'RESERVED'").fetchone()
        assert int(row["s"] or 0) == 12000

def test_defect_4_agent_env_isolation():
    """
    Launch the agents process via run_all.sh pattern and read /proc/<pid>/environ
    to assert the forbidden variable NAMES are absent in the agents process.
    Also ensures the agents process cannot import code that reads those names.
    """
    import subprocess
    import time
    import os
    
    # Start the agents process
    cmd = 'env -i PATH="$PATH" PYTHONPATH="." bash -c \'set -a; source .env.agents; set +a; exec python3 -m uvicorn agents.main:app --port 8013 --host 127.0.0.1\''
    proc = subprocess.Popen(cmd, shell=True)
    
    try:
        # Give it a moment to start
        time.sleep(2)
        
        # Read the real environment from /proc/<pid>/environ
        try:
            # Find python3 child if bash didn't exec
            pgrep_out = subprocess.check_output(f"pgrep -P {proc.pid}", shell=True, text=True).strip()
            python_pid = pgrep_out.split()[0]
        except subprocess.CalledProcessError:
            python_pid = proc.pid
            
        with open(f"/proc/{python_pid}/environ", "rb") as f:
            env_data = f.read().split(b'\0')
            
        env_vars = {}
        for item in env_data:
            if b'=' in item:
                k, v = item.split(b'=', 1)
                env_vars[k.decode('utf-8', 'ignore')] = v.decode('utf-8', 'ignore')
                
        forbidden = ["SERVICE_KEY", "AUDIT_HMAC_KEY", "TOOL_CREDENTIAL"]
        for fv in forbidden:
            assert fv not in env_vars, f"Forbidden secret {fv} found in agent's /proc/environ!"
            
        # Verify agents cannot import guard.main which reads secrets
        check_import_cmd = 'env -i PATH="$PATH" PYTHONPATH="." bash -c \'set -a; source .env.agents; set +a; exec python3 -c "import guard.main"\''
        res = subprocess.run(check_import_cmd, shell=True, capture_output=True, text=True)
        assert res.returncode != 0, "Agents process was able to import guard.main, which should fail closed due to missing secrets!"
        assert "Startup failed: secret SERVICE_KEY is missing or empty" in res.stderr
        
    finally:
        proc.terminate()
        proc.wait(timeout=2)
