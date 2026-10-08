# Enterprise Security & Agent Governance Policy

## 1. sec_policy_agent_identity: Agent Identity Verification
Every action submitted to the execution gateway must originate from an agent whose identity is verified and active in the enterprise Agent Registry. Unknown or inactive agents must be BLOCKED immediately under rule AGT-001.

## 2. sec_policy_least_privilege: Least Privilege and Access Control
Autonomous agents operate on strict least-privilege principles. Agents hold zero default permissions. Every action must match an explicit permission rule defined in the Agent Registry under rule PERM-001.

## 3. sec_policy_prompt_injection: Indirect Injection and External Content Defense
When an agent acts upon untrusted external content (e.g. email bodies, customer feedback, web scraping, external documents), the system treats all external tokens as passive data. Destructive mutations, deployments, permission changes, or resource transfers triggered by external content must be BLOCKED under rule INJ-002.

## 4. sec_policy_target_governance: Target Governance and Default-Deny
Any target not catalogued in the Resource Registry is treated as an unknown asset. Unknown targets default to worst-case sensitivity (production, confidential, irreversible). Destructive actions, deployments, and permission changes against unknown targets are strictly BLOCKED under rule REG-003.
