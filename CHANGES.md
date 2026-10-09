# Change Log

## Test Modifications
- **A2 / Invariant I10**: Updated `tests/test_invariants.py::test_invariant_i10_cumulative_limits_atomic_and_no_inflation`.
  - **Reason**: The test was demonstrably stale and contradicted Invariant I4. It expected a `REVIEW` for a 250,000 amount, but the hard cap is 200,000. Per I4, the most severe check (hard cap -> BLOCK) wins.
  - **Old Assertion**: `assert resp.decision == DecisionOutcome.REVIEW`
  - **New Assertion**: `assert resp.decision == DecisionOutcome.BLOCK`
