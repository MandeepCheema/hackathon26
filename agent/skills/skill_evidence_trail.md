---
name: skill_evidence_trail
capability: B5
applies_to: all_duties
build_priority: 5
status: ready
---

# Skill: Evidence Trail (B5)

**One-line purpose:** Standard evidence schema across all duties and all outcomes. What gets recorded is the grade.

## Schema

Every verdict — FLAG, CLEAR, or ABSTAIN — must produce an evidence trail with these fields:

```
EVIDENCE TRAIL
==============
duty:                  [cash_over_short | loss_prevention | ...]
entity_id:             [store_id / staff_id / po_id / invoice_id]
entity_type:           [store | cashier | po_line | invoice | ...]
period:                [YYYY-MM-DD or date range]
outcome:               [FLAG | CLEAR | ABSTAIN]
outcome_status:        [exact submit status value]

METRICS
-------
[list all computed metrics with their values and the SQL source records they came from]
e.g.:
  net_cents:       -61000  (source: fin_register_totals, fin_cash_counts — 14 rows)
  avg_var_cents:   -4357   (source: computed from above)
  tstat:           -3.80   (source: computed)

KNOWN-CAUSE CHECKS
------------------
[For each check in the duty's checklist, one line:]
  ✓ float_change_log:       CHECKED — no matching float-change record found (0 rows)
  ✓ manager_correction_log: CHECKED — no correction entries for this store in window (0 rows)
  ✓ same_cashier_shift:     CHECKED — stf_009_6 worked 11 of 14 variance days
  [Note: if a check could NOT be run:]
  ⚠ promo_calendar_match:   NOT RUN — world.fin_promo_calendar not present in schema

CONFIDENCE GATE
---------------
  confidence_score:           0.92
  evidence_sufficiency_score: 0.95
  gate:                       passed

POLICY CITATIONS
----------------
  [Policy ID cited for every threshold applied]
  e.g.: finpol_materiality applied: $5 AND 0.5% threshold (body: {...})

DOLLAR / OPERATIONAL IMPACT
----------------------------
  estimated_impact_cents: [integer]
  description: [one sentence]

VERDICT NOTE
------------
  [2–4 sentences. Lead with verdict. Numbers over adjectives. Non-accusatory.]
  e.g.: "str_009 is persistently short: -$610 net over 14 days, t = -3.8 (threshold: -3.0).
         All known causes checked and ruled out. No float-change or correction entries found.
         Confidence 0.92. Pattern warrants investigation."
```

## Rules for writing the evidence trail

1. **Every metric must cite its source records.** "avg_var_cents: -4357" is not acceptable alone. "avg_var_cents: -4357 (source: fin_register_totals + fin_cash_counts, 14 store-days)" is correct.

2. **Every known-cause check must be listed** — including ones that cleared (✓ no match) and ones that could not run (⚠ not run). A check not listed was not done.

3. **No qualitative language without quantification.** "persistently short" must be followed by the t-stat and net amount. "anomalously high void rate" must be followed by the void rate, peer mean, and z-score.

4. **Non-accusatory language.** Describe the pattern, not the person. (GR5)
   - ❌ "This cashier is stealing."
   - ✅ "stf_009_6 has a void rate of 0.61 vs peer mean of 0.17 (z = 2.9) over 1,847 transactions."

5. **Abstain requirements.** If outcome is ABSTAIN, the missing data must be named exactly:
   - ❌ "Insufficient information."
   - ✅ "Cannot complete known-cause check: world.fin_promo_calendar not present in schema. Without this table, manager_override_log check is incomplete."

6. **Length scales with complexity.** A simple 1:1 cleared record is 3 lines. A multi-week cash pattern with corroboration is a full paragraph. Padding a thin case is a fault.

## Guardrails enforced
- **GR5**: Non-accusatory language.
- **GR6**: NOT-RUN checks are listed as ⚠, never silently omitted.
- Anti-hallucination: every figure cites the SQL source records it was computed from.
