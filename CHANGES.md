# Change Log

## Test Modifications
- **A2 / Invariant I10**: Updated `tests/test_invariants.py::test_invariant_i10_cumulative_limits_atomic_and_no_inflation`.
  - **Reason**: The test was demonstrably stale and contradicted Invariant I4. It expected a `REVIEW` for a 250,000 amount, but the hard cap is 200,000. Per I4, the most severe check (hard cap -> BLOCK) wins.
  - **Old Assertion**: `assert resp.decision == DecisionOutcome.REVIEW`
  - **New Assertion**: `assert resp.decision == DecisionOutcome.BLOCK`

## Authentication & Identity Integration (Firebase Auth)
- **Frontend Auth (F1)**: Integrated Firebase Web SDK in `landing/` and `dashboard/` with Google popup (with redirect fallback), email/password sign-up with verification notice, plain-English error mapping, `AuthProvider`, and `ProtectedRoute`.
- **Backend Verification (F2)**: Implemented `auth/firebase_auth.py` with injectable `current_owner` and `sensitive_owner` dependencies. Added `owners` table and `owner_uid` tenant migration.
- **Tenant Isolation & Key Management (F3)**: Tied tenant registration to owners (`POST /tenants/register`), added `GET /tenants/mine`, `POST /tenants/{id}/rotate-key` and `/revoke-key` enforcing owner isolation and emitting audit signals on unauthorized attempts. Added single-use 60s connect code exchange. Gateway strictly rejects Firebase ID tokens and enforces `X-API-Key`.
- **Dashboard Flow (F4)**: Updated `/app` dashboard with website connect onboarding, tenant selector, live key rotation display, separate human approver token authentication, and INR (₹) limits.
- **Safety and Hardening (F5)**: Added rate limiting per IP and per UID, sanitized logs to never expose tokens or credential paths, updated `.env.example`, `DECISIONS.md`, and test suites.

