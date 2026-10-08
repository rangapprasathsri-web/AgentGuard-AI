# AgentGuard AI

> **Execution-Authorization and Governance Layer for Autonomous AI Agents**  
> *Principle: "Don't trust the agent. Verify the action." AgentGuard decides, the Gateway enforces, the agent only proposes.*

---

## 1. Architecture Overview

AgentGuard AI sits between autonomous departmental AI agents and enterprise databases/tools. It provides deterministic policy enforcement, multi-dimensional risk scoring, atomic sliding cumulative limits, advisory GenAI consequence analysis, policy-evidence RAG, human-in-the-loop approvals, and an HMAC-SHA256 tamper-evident audit ledger.

### Process Topology & Ports
Each process runs in isolation with its own environment file (fail-closed secret validation):
- **Guard Service** (`:8001` - `.env.guard`): Authoritative registries, hard rules, risk engine, cumulative ledger, approval manager, consequence analyzer, and RAG.
- **Execution Gateway** (`:8002` - `.env.gateway`): The sole route to enterprise tools. Holds tool credentials. Verifies Guard HMAC signatures and action hashes.
- **Department Agents** (`:8003` - `.env.agents`): Five departments (`analytics`, `database`, `coding`, `finance`, `devops`) on one generic `AgentRuntime`. Holds zero tool credentials.
- **Operator Demo Service** (`:8004` - `.env.demo`): Live demo runner, clock injector, and audit tampering harness (active in `DEMO_MODE`).
- **Governance Dashboard** (`:5173`): Vite + React + TailwindCSS dashboard with role switching, live decisions stream, approval queue, audit chain verification, and scenario runner.

---

## 2. Security Invariants (I1 – I12)

All 12 security invariants are enforced in code and backed by automated tests:

- **I1**: The agent never holds tool credentials and has no code path to tools. The Gateway is the only route to tools.
- **I2**: Fail closed: if the Guard is unreachable, errors, times out, or returns an invalid/unsigned response, the Gateway denies (`503 denied_fail_closed`). Every tool-bound action is protected; there is no bypass list.
- **I3**: Context facts (environment, data class, reversibility, resource size, agent permissions, time) come from AgentGuard registries and the Guard clock, never from the request.
- **I4**: The final decision is the most severe of all deterministic checks (`ALLOW < REVIEW < BLOCK`). Decisions never move down. The LLM analyzer can never lower a score, never output `ALLOW`, never override a `BLOCK`, and can never by itself cause a `BLOCK`.
- **I5**: Approvals are bound to the SHA-256 hash of the exact canonical action, single-use, and expiring. No response means rejected. Nothing is ever auto-approved.
- **I6**: A hash mismatch voids the approval. A reused approval is blocked.
- **I7**: Untrusted content (`source.type = external_content`, retrieved policy text, `content_excerpt`) is data, never instructions. It can influence what an agent proposes, never what AgentGuard allows.
- **I8**: Policies, registries, and the policy corpus are read-only to agents and have no agent-callable write path. Policy changes require human action outside the agent flow.
- **I9**: The audit log is append-only and tamper-evident (HMAC hash chain). Every decision, including `ALLOW`, is logged.
- **I10**: Cumulative-limit checks and reservations are atomic (`BEGIN IMMEDIATE`) and count only executed or actively reserved amounts. Blocked or rejected requests never inflate totals.
- **I11**: Secrets never appear in logs, audit records, API responses, or the UI.
- **I12**: An approval can lift a `REVIEW` to execution. It can never override a `BLOCK`.

---

## 3. Quick Start & Execution

### Prerequisites
- Python 3.11+
- Node.js v18+ & npm
- Pinned Python requirements: `pip install -r requirements.txt`
- Dashboard packages: `cd dashboard && npm install`

### Seeding Data
Seed mock enterprise databases (`tools.db` with 50,000 customers, 2,000 orders, staging, and sales):
```bash
./make seed
# or: python3 -c "from tools.db import init_tools_db; init_tools_db()"
```

### Running the Test Suite (Offline & Deterministic)
All 38 automated tests run completely offline with `MockLLM` and no network requests:
```bash
./make test
# or: LLM_MODE=mock python3 -m pytest -v tests/
```

### Running the Full System (All 5 Processes)
Start the complete AgentGuard platform:
```bash
./make demo
# or: bash scripts/run_all.sh
```
Once launched, open the Governance Dashboard at `http://localhost:5173`.

---

## 4. Known Limits

- Assumes the Gateway is the only network route to tools and that agents never
  hold tool credentials; this is a deployment requirement, enforced here by
  separate processes and separate env files.
- Role headers are unauthenticated in this MVP; production would validate
  identity tokens.
- source.type is set by the agent runtime in the MVP; production needs
  Gateway-level provenance tagging.
- The hash chain with HMAC is tamper-evident, not tamper-proof; deleting the most
  recent records or an attacker holding the HMAC key is not detected without an
  external anchor.
- Does not defend against a compromised Gateway host or a malicious admin editing
  policy files.
- The cumulative gate is keyed per (agent, action, target); splitting across
  different agents is not caught (cross-agent correlation is roadmap).
- Hash-bound approval in MVP; per-action signed authorization tokens are
  roadmap. The Guard-to-Gateway HMAC is service authentication only.
- With live LLMs, analyzer variance can escalate borderline ALLOW decisions to
  REVIEW; deterministic tests use MockLLM.
- Policy documents are illustrative samples; AgentGuard provides controls and
  evidence, not automatic legal compliance.
