# BASELINE REPORT (PHASE 0)

## 1. Test Suite Results
- **Command Run**: `LLM_MODE=mock python3 -m pytest -v tests/`
- **Total Tests Run**: 53 (Note: The `README.md` states 38 tests, but the actual executed count is 53).
- **Pass Count**: 53 passed
- **Fail Count**: 0 failed
- **Runtime**: 6.71s
- **What runs**: The entire existing test suite completes successfully with `LLM_MODE=mock`.
- **What fails**: No tests failed.
- **What could not be run**: Nothing; the tests executed completely.

## 2. Uncommitted Changes (`git status`)
The working tree currently contains uncommitted modifications to the following files:
- `DECISIONS.md`
- `DEVIATIONS.md`
- `agents/main.py`
- `common/audit.py`
- `common/llm_client.py`
- `common/schemas.py`
- `dashboard/src/App.jsx`
- `gateway/enforcement.py`
- `gateway/guard_client.py`
- `gateway/main.py`
- `guard/ledger.py`
- `guard/main.py`
- `guard/pipeline.py`
- `policies/thresholds.yaml`
- `scripts/run_all.sh`
- `tests/test_calibration.py`
- `tests/test_invariants.py`
- `tests/test_llm_analyzer.py`
- `tests/test_rag.py`
- `tests/test_scenarios_e2e.py`

*Untracked Files:*
- `.~lock.strict.docx#`
- `Policy 1.zip`
- `dashboard/public/`
- `generate_control_room.py`
- `generate_html.py`
- `generate_simple_control_room.py`
- `report.md`
- `report_v2.md`
- `run_acceptance.py`
- `scripts/smoke_test.py`
- `strict.docx`
- `tests/test_defects.py`
- `tests/test_new_requirements.py`

## 3. Findings & Notes
- The uncommitted changes show that partial progress toward fixing "Known Issues" (like removing default secrets in `common/audit.py` and `common/llm_client.py`) and fixing test definitions is already staged in the working tree.
- I will treat the current working state as the baseline moving forward to complete all defect fixes exactly as requested.
