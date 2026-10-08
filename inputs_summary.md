# Inputs Summary

## 1. Providers, Models, Base URLs, and Key Variable Names

### Provider Priority Order
The API file (`api keys.docx`) contains 8 API keys, all sharing the `sk-or-v1-` prefix, corresponding to **OpenRouter**.
Since OpenRouter provides an OpenAI-compatible API, a generic OpenAI-compatible adapter (`httpx`-based) is utilized without hardcoding provider or model names.

1. **Primary Provider**:
   - Provider Name: `openrouter_primary`
   - Base URL: `https://openrouter.ai/api/v1` (configurable via `LLM_BASE_URL` / `OPENROUTER_BASE_URL`)
   - Key Variable Name: `OPENROUTER_API_KEY` (Key #1 from `api keys.docx`)
   - Default Model: Configured via `LLM_MODEL` / `config/analyzer.yaml` / `config/departments.yaml` (e.g., `qwen/qwen-2.5-72b-instruct`)
2. **Failover Providers (Tier 1 to 7)**:
   - Provider Names: `openrouter_failover_1` through `openrouter_failover_7`
   - Base URL: `https://openrouter.ai/api/v1`
   - Key Variable Names: `OPENROUTER_API_KEY_FAILOVER_1` through `OPENROUTER_API_KEY_FAILOVER_7` (Keys #2 through #8 from `api keys.docx`)
   - One attempt per provider upon connection error, timeout (4s for analyzer), or HTTP 429; no unbounded retries.

*Note on Secrets: In compliance with Invariant I11 and Section 0, zero key values are echoed or written to this document, code, logs, or audit records. All values are extracted directly into `.env.guard` and `.env.agents`, and `.env*` is excluded via `.gitignore`.*

---

## 2. Limits Stated in File B (`database_agent_implementation_plan.md`)

1. **Functional Scope Limits**:
   - The Database Implementation Plan Agent's primary responsibility is converting user requirements into database implementation plans; it does *not* primarily execute database operations directly.
   - Guarded execution: Tool calls and mutations must be proposed and governed through authorization layers.
2. **Knowledge Retrieval Limits**:
   - RAG must retrieve *only* information relevant to the current requirement, rather than dumping arbitrary database encyclopedias into prompt context.
3. **Candidate Generation Limits**:
   - Proposing systems must not compare every database in existence; candidates must be constrained to a small set of technically plausible candidates.
4. **Architecture Complexity Limits**:
   - Systems must not inject read replicas, caching, sharding, partitioning, or HA automatically; every architectural complexity must have an explicit justified requirement.
5. **Critic Validation Requirement**:
   - A mandatory critic/validator stage must challenge initial proposals. The first proposal is never automatically accepted.
6. **Model Recommendation**:
   - Recommends Qwen3.5-class models (Qwen3.5-9B for low-resource/local, Qwen3.5-35B-A3B or equivalent for hosted/high quality).
7. **Context & Token Budgets**:
   - File B does not state explicit numeric token budgets for LLM context windows. As mandated by Section 5.2, a conservative context limit budget is defaulted (see below).

---

## 3. Ambiguities and Resolutions

1. **Unlabelled Keys in File A**:
   - *Observation*: File A contains 8 keys without explicit text labels, provider names, or base URLs.
   - *Resolution*: Identified by format `sk-or-v1-*` (73 characters) as OpenRouter keys. Configured with standard base URL `https://openrouter.ai/api/v1` and OpenAI-compatible completions format. Priority assigned sequentially: Key 1 as primary, Keys 2-8 as failover pool.
2. **Context Token Budget Default (Prompt Section 5.2)**:
   - *Observation*: File B specifies qualitative context limits ("retrieve only relevant information", "small candidate set", "structured context") but no exact integer token budget.
   - *Resolution (Fail-Closed)*: Under prompt section 5.2 ("If file B gives none, default to a conservative budget and note it in DECISIONS.md"), we set a conservative per-call budget of **4,000 tokens**. Token estimation uses provider tokenizer if available, otherwise `ceil(character_count / 3)`. Section packing strictly enforces Priorities 1–5:
     - Priority 1: System instructions + output schema (never truncated)
     - Priority 2: Canonical action + resolved context
     - Priority 3: Risk factors
     - Priority 4: Retrieved policy chunks (top 3, truncated as needed)
     - Priority 5: Content excerpt (truncated to 200 chars or dropped)
     - If Priorities 1–3 alone exceed 4,000 tokens: analyzer returns `context_overflow` (deterministic decision stands); proposer returns error.
3. **Scope Alignment (Five Department Agents vs Single Database Agent Document)**:
   - *Observation*: File B details a database planning workflow, while the prompt requires five department agents (`analytics`, `database`, `coding`, `finance`, `devops`) on one generic `AgentRuntime`.
   - *Resolution*: Follow the prompt precedence hierarchy (Invariants > File B > Prompt). File B guides the database department persona, knowledge patterns, and context constraints, while the overall AgentGuard platform governs all five department agents with identical enforcement, policy, risk scoring, cumulative gating, and audit invariants.
