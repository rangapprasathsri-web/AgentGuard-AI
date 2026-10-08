# Enterprise Finance & Payments Policy

## 1. Scope and Authority
This policy governs all automated financial transactions, payouts, refunds, and ledger modifications initiated by autonomous agents or human operators across enterprise payment gateways.

## 2. fin_policy_cumulative_limits: Cumulative Thresholds and Spending Limits
Automated agents operating on payments APIs are constrained by strict velocity and cumulative ceilings:
- **Soft Limit**: A cumulative 24-hour limit of ₹50,000. Transactions pushing total velocity above ₹50,000 require human operator review.
- **Hard Cap**: An absolute cumulative 24-hour limit of ₹200,000. Any transaction that would cause total executed and actively reserved disbursements to exceed ₹200,000 must be immediately BLOCKED.
- **Rapid Velocity Ceiling**: If 5 or more payment requests occur within any 10-minute sliding window, and the total exceeds the soft limit, the request must be BLOCKED to prevent runaway automated looping.

## 3. Discretionary Refund Guidelines
Single refunds exceeding ₹10,000 are designated high-risk and require explicit dual-authorization or approver review. All refunds must bind to a verified `customer_id`.
