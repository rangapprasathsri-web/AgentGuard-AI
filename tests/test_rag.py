import pytest
from common.schemas import ActionRequest, ActionType, Source, SourceType
from guard.pipeline import GuardPipeline
from guard.rag import PolicyRAGEngine


def test_rag_chunking_and_retrieval():
    engine = PolicyRAGEngine(policy_dir="policy-data")
    assert len(engine.chunks) > 0
    assert len(engine.corpus_hash) == 64

    # Retrieve for finance payments action
    chunks, citations, status = engine.retrieve(
        action="CREATE", target="payments_api", department="finance", top_k=3
    )
    assert status == "success"
    assert len(chunks) > 0
    assert len(citations) > 0
    # Should cite finance_policy
    assert any("finance_policy.md" in c for c in citations)


def test_rag_advisory_failure_resilience():
    # Force an invalid policy directory
    broken_engine = PolicyRAGEngine(policy_dir="non_existent_dir")
    chunks, citations, status = broken_engine.retrieve("READ", "sales_db")
    assert status == "skipped"
    assert len(chunks) == 0

    # Ensure GuardPipeline functions smoothly even if RAG is broken
    pipeline = GuardPipeline(service_key="test_svc", rag_engine=broken_engine)
    req = ActionRequest(
        agent_id="analytics-agent-01",
        action=ActionType.READ,
        target="sales_db",
        params={"record_count": 1},
        source=Source(type=SourceType.USER),
    )
    resp = pipeline.evaluate(req)
    assert resp.decision.value == "ALLOW"
    assert resp.rag_status == "skipped"
