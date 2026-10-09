# Architectural and Design Decisions (DECISIONS.md)

This document records all decisions made where requirements were ambiguous, contradictory, or required concrete implementation choices, adhering strictly to the principle of fail-closed, restrictive security.

### Decision 1: API Keys Provider & Base URL Identification
- **Context**: File A (`api keys.docx`) contains 8 unlabelled API keys starting with `sk-or-v1-`.
- **Decision**: Recognized as OpenRouter OpenAI-compatible API keys. Base URL defaults to `https://openrouter.ai/api/v1`. Configured as 1 primary provider and 7 failover providers. Never hardcode provider/model in code; loaded dynamically via environment variables and configuration files (`config/analyzer.yaml`, `config/departments.yaml`).
- **Security Rationale**: API keys are isolated into per-process `.env.guard` and `.env.agents`, never exposed to Gateway, Demo, UI, or audit logs.

### Decision 2: Context Token Budget Default (Section 5.2)
- **Context**: File B does not provide a numeric token limit per LLM call.
- **Decision**: Under Prompt Section 5.2, default to a conservative budget of 4,000 tokens per call. Token counting employs provider tokenizer when available, fallback to `ceil(len(text) / 3)`. Packing strictly enforces priority tiers (1: System + Schema, 2: Canonical Action + Resolved Context, 3: Risk Factors, 4: Policy Chunks, 5: Content Excerpt). Overflow of tiers 1-3 halts proposal or yields `context_overflow` for analyzer, retaining deterministic decision.

### Decision 3: Redaction Pattern Defaults
- **Context**: Prompt Section 5.2 requires redacting national IDs, cards, and emails before sending to LLM.
- **Decision**: Regex patterns implemented:
  - 12-digit national ID: `\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b` -> `[REDACTED_ID]`
  - 13-19 digit card numbers: `\b(?:\d[ -]*?){13,19}\b` matching Luhn/card patterns -> `[REDACTED_CARD]`
  - Emails: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b` -> `[REDACTED_EMAIL]`

### Decision 4: Multi-Process Isolation & Port Allocation
- **Context**: Section 3 mandates separate processes and distinct `.env` files:
  - Guard: port 8001 (`.env.guard`)
  - Gateway: port 8002 (`.env.gateway`)
  - Agents: port 8003 (`.env.agents`)
  - Demo: port 8004 (`.env.demo`)
  - Dashboard: port 5173 (React Vite)
- **Decision**: Each service runs as an independent FastAPI process with isolated environment loading. Boundary tests enforce that `agents/` has zero access to tool credentials or guard secrets.

### Decision 5: Atomic Cumulative Checks & Reservations
- **Context**: Invariants I10 and Section 8, Step 6 specify cumulative gate sliding 24-hour window per `(agent_id, action, target)`.
- **Decision**: Implemented using explicit transactions with `BEGIN IMMEDIATE` in SQLite ledger. An active reservation expires in 60s if unconfirmed, and `/guard/confirm` transitions status to executed or releases it on failure.

### Decision 6: Makefile and Portable CLI Wrapper
- **Context**: Host system environment does not have GNU `make` installed in system PATH.
- **Decision**: Provided standard POSIX `Makefile` as required, and also created an executable `./make` runner that supports `./make seed`, `./make test`, and `./make demo`.


### Phase A2: test_invariant_i10
- **Decision:** Changed test_invariant_i10 to assert BLOCK instead of REVIEW for an amount exceeding the hard cap (250,000 > 200,000). Per invariant I4, the most severe check wins, so exceeding the hard cap must yield BLOCK regardless of the soft limits. The test was stale.

### Decision 7: Threshold Decision (B2)
- **Context**: `policies/thresholds.yaml` historically had 45, but README and older docs mentioned 40.
- **Decision**: Keep the threshold at 40 (`allow_max: 39`, `review_min: 40`). This decision is now applied consistently across config and tests.
