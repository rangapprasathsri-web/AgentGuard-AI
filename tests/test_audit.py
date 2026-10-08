import os
import pytest
from common.audit import AuditLogger


@pytest.fixture
def audit_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    db_file = str(tmp_path / "test_audit.db")
    logger = AuditLogger(db_path=db_file, hmac_key="test_hmac_secret_key_123")
    return logger


def test_audit_chain_append_and_verify(audit_env):
    logger = audit_env

    # 1. Initially empty
    status = logger.verify_chain()
    assert status["valid"] is True
    assert status["records_checked"] == 0

    # 2. Append first event
    evt1 = logger.append_event(
        event_type="decision_made",
        payload={"decision": "ALLOW", "agent_id": "analytics-agent-01", "action": "READ"},
        decision_id="dec_001",
    )
    assert evt1["prev_hash"] == "GENESIS"

    # 3. Append subsequent events
    evt2 = logger.append_event(
        event_type="approval_decided",
        payload={"decision": "APPROVE", "approver": "cfo"},
        decision_id="dec_002",
    )
    assert evt2["prev_hash"] == evt1["record_hash"]

    evt3 = logger.append_event(
        event_type="executed",
        payload={"status": "executed", "tool": "payments_api"},
        decision_id="dec_002",
    )
    assert evt3["prev_hash"] == evt2["record_hash"]

    # 4. Verify chain integrity
    status = logger.verify_chain()
    assert status["valid"] is True
    assert status["records_checked"] == 3
    assert status["head_hash"] == evt3["record_hash"]
    assert status["first_broken_id"] is None


def test_scenario_11_audit_tamper_and_restore(audit_env):
    logger = audit_env

    # Append 3 valid events
    for i in range(3):
        logger.append_event(
            event_type="decision_made",
            payload={"decision": "ALLOW", "step": i},
            decision_id=f"dec_{i}",
        )

    # Chain initially valid
    assert logger.verify_chain()["valid"] is True

    # Tamper demo: modifies row in audit table
    tamper_info = logger.demo_tamper()
    assert tamper_info["tampered_id"] is not None

    # Verification must fail and identify broken record
    verify_result = logger.verify_chain()
    assert verify_result["valid"] is False
    assert verify_result["first_broken_id"] == tamper_info["tampered_id"]
    assert "tampering detected" in verify_result["reason"]

    # Restore from backup
    restored = logger.demo_restore_tamper()
    assert restored is True

    # Verification must be valid again
    verify_restored = logger.verify_chain()
    assert verify_restored["valid"] is True
    assert verify_restored["first_broken_id"] is None


def test_audit_no_secrets_in_payload(audit_env):
    logger = audit_env
    # Ensure audit logger accepts safe payloads
    evt = logger.append_event(
        event_type="security_signal",
        payload={"signal": "invalid_request", "body_hash": "a1b2c3d4"},
    )
    # Check that no common key patterns are in the stored row
    events = logger.list_events()
    assert len(events) == 1
    raw_payload_str = str(events[0]["payload"])
    assert "sk-" not in raw_payload_str
    assert "SERVICE_KEY" not in raw_payload_str
    assert "AUDIT_HMAC_KEY" not in raw_payload_str
