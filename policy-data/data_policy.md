# Enterprise Data Governance & Retention Policy

## 1. Classification of Data Assets
Enterprise data is classified into: Public, Internal, Confidential, Financial, and Personally Identifiable Information (PII). PII carries the highest standard of protection.

## 2. data_policy_pii_retention: PII Retention and Protection
Production datasets containing customer Personally Identifiable Information (`customers_prod`) represent irreversible corporate liabilities.
- **Strict Prohibition on Production PII Deletion**: Autonomous agents and automated systems are strictly forbidden from executing DELETE operations against production PII stores under rule DATA-004.
- All requests attempting bulk or single-record deletion against production PII must be unconditionally BLOCKED.
- Permitted mutations are strictly limited to staging environments and designated test stores.

## 3. Blast Radius and Modification Caps
All database updates and deletions must declare a bounded `record_count`. Agents must never attempt unbounded mass updates.
