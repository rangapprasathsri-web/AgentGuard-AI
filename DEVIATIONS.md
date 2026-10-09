# Deviations from Specification (DEVIATIONS.md)

### Deviation 1: Irreversible Risk Factor Applicability
- **Deviation**: The `irreversible +15` risk factor only applies when an action performs a state mutation (`CREATE`, `UPDATE`, `DELETE`, `TRANSFER`, `DEPLOY`, `CHANGE_PERMISSION`) on an irreversible resource. For non-mutating actions like `READ`, it does not apply.
- **Reason**: In Scenario 9, `database-agent READ customers_prod` was stated to score 35 (5 base + 10 restricted + 20). If `irreversible` (+15) applied to `READ`, the score would be higher. `READ` is inherently non-destructive, so treating it as irreversible conceptually doesn't make sense.

All other implementation details adhere strictly to the precedence order: Security Invariants > File B > Specification Prompt.
