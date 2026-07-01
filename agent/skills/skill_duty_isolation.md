---
name: skill_duty_isolation
capability: B4
applies_to: all_duties
build_priority: 2
status: ready
---

# Skill: Duty Isolation (B4)

**One-line purpose:** Architectural boundary ensuring no duty's finding ever contaminates another duty's independent investigation.

## Why this matters
If str_009 has a cash shortage (cash_over_short duty) AND a high-void cashier (loss_prevention duty), these are correlated findings — but they must be independently arrived at. The cash duty cannot use the void signal as evidence. The loss duty cannot use the cash short as evidence. Each duty must stand alone on its own SQL evidence.

Cross-duty correlation (noting the correlation in write-ups) is allowed, but only AFTER both duties have independently reached their verdicts.

## Rules

### Rule 1 — No cross-duty evidence sharing during investigation
When running duty X, do not use evidence gathered during duty Y as input to duty X's known-cause checks, confidence gate, or outcome classification.

**Violation example (do NOT do this):**
> "I already found a cash short at str_009 from the cash duty, so I'll treat the void anomaly as confirmed fraud."

**Correct approach:**
> Run loss_prevention independently. Reach a verdict based solely on void rate data.

### Rule 2 — Cross-duty correlation runs after, not during
After ALL duties have independently reached verdicts, you may note correlations in the evidence trail:
> "Note: str_009 also has a cash_over_short finding (independent verdict from cash duty). Correlation noted for controller review. Not used as evidence in this verdict."

This is the B4_cross_duty_correlation stage — it runs AFTER B5 write-ups, never feeding back into B2/B3.

### Rule 3 — Shared SQL queries are allowed; shared verdicts are not
You may run the same run_sql query in two duties (e.g., checking a store's transaction history). The data from that query is analyzed independently under each duty's own framework.

### On violation
If you realize you have used cross-duty evidence in a verdict:
1. Discard the cross-duty input.
2. Re-run the affected duty's B2_evidence_gathering in isolation.
3. Reach a new verdict without the cross-duty input.

## Enforces
- **GR3**: No cross-duty contamination.
