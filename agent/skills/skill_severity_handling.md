---
name: skill_severity_handling
capability: B3
applies_to: [cash_over_short]
build_priority: 6
status: ready
---

# Skill: Severity Handling (B3)

**One-line purpose:** Large one-off variances receive MORE scrutiny before flagging, not less. Small persistent patterns are the real signal.

This is a **new capability** — counterintuitive and easy to get wrong. The instinct is to flag big numbers immediately. That instinct is wrong.

## The counterintuitive rule (GR8)

A single-day variance of -$500 is LESS alarming than a persistent -$40/day over 3 weeks:
- A $500 one-off is almost always explained by a float change, manager correction, or end-of-day error.
- A -$40/day persistent pattern over 21 days (t = -3.9) is a real signal.

Therefore: the larger the one-off variance, the MORE known-cause checks you must complete before flagging.

## Procedure

### Step 1 — Classify the pattern type
After running the candidate SQL from skill_population_outlier_detection, classify each store's pattern:

| Pattern | Definition | Scrutiny level |
|---|---|---|
| `persistent_small` | Low avg_var_cents, high |tstat| (≥ 3), many days | Standard scrutiny |
| `one_off_large` | One day dominates avg_var_cents, |tstat| elevated only because of that day | Elevated scrutiny |
| `mixed` | Both days with large variance AND persistent small variance | Elevated scrutiny on large days, standard on the pattern |
| `noise` | |tstat| < 3 | No scrutiny needed — submit balanced |

Classify by comparing: `max(|var_cents|) vs avg(|var_cents|)`
- If `max > 5 × avg`: likely one_off_large
- If `max < 2 × avg`: likely persistent_small

### Step 2 — Apply elevated scrutiny for one_off_large

For a `one_off_large` candidate:
1. Query the specific high-variance day in detail:
   ```sql
   SELECT * FROM world.fin_paid_outs
   WHERE store_id = $store AND business_date = $large_variance_date;

   SELECT * FROM world.fin_cash_counts
   WHERE store_id = $store AND business_date = $large_variance_date;
   ```
2. Check for logged vault/safe transfers on that specific date.
3. Check for end-of-month float resets.
4. Check for staff changeovers (new cashier, new manager).

If the large-variance day is explained: exclude it from the t-statistic calculation and re-compute. If the residual t-stat drops below -3.0 after exclusion: the pattern disappears — submit `balanced`.

### Step 3 — Document the scrutiny level in the evidence trail
```
Pattern type: persistent_small
Scrutiny level: standard (tstat = -3.8 over 14 days, max/avg ratio = 1.3)
Large-day check: not required (no single day dominates)
```
Or:
```
Pattern type: one_off_large
Scrutiny level: elevated (day 2026-01-15 contributes 68% of net_cents)
Elevated checks run: fin_paid_outs (0 rows), vault transfers (0 rows)
Day excluded: 2026-01-15 ($312 single-day variance)
Re-computed tstat (13 days): -1.4 → below -3.0 threshold → CLEAR
```

## Why this matters for scoring
The bench penalizes false positives equally with missed leaks. A confident flag on a one-off large variance that has an obvious explanation is a false positive. Running elevated scrutiny and clearing it correctly is a scored correct action.

## Guardrails enforced
- **GR8**: Large one-offs get MORE scrutiny. Re-run the known-cause gate with elevated thoroughness before finalizing a flag on a large one-off.
