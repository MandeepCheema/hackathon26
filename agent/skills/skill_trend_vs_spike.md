---
name: skill_trend_vs_spike
capability: B2
applies_to: [cogs_leakage, settlement_reconciliation]
build_priority: 6
status: ready
---

# Skill: Trend vs Spike (B2)

**One-line purpose:** Distinguishes sustained drift from a single-period spike before flag eligibility. Only sustained trends are flag-eligible; one-period spikes require a different response.

This is a **new capability**. Without it, COGS and settlement duties will fire on single anomalous months that correct themselves the next period.

## When to use
Use for `B_population_pattern` and `C_rate_contract_compliance` workflow shapes when the anomaly is measured over multiple periods: COGS leakage (monthly) and settlement reconciliation (daily pattern, not single-day).

## Core distinction

**Spike:** A single period with anomalous value that does not persist.
- Action: Note it, do NOT flag. Monitor next period.
- Submit: `within_tolerance` with note "single-period spike; not flag-eligible until sustained"

**Trend:** Anomalous value that persists across multiple consecutive periods.
- Action: Flag-eligible if it passes all other gates.
- Submit: `leakage` / `shortfall` with persistence data cited.

## Procedure

### Step 1 — Determine the analysis window
Minimum periods for trend classification:

| Duty | Cadence | Min periods for trend |
|---|---|---|
| cogs_leakage | monthly | 2 consecutive months |
| settlement_reconciliation | daily | 3 consecutive days at same store |

If fewer than the minimum periods are available: record "Insufficient history for trend/spike classification" and route to ABSTAIN.

### Step 2 — Query the multi-period data
**For cogs_leakage:**
```sql
-- Compute variance_pct per store per month over available history
WITH monthly AS (
  SELECT
    store_id,
    DATE_TRUNC('month', business_date)  AS period,
    SUM(actual_cogs_cents)              AS actual_cents,
    SUM(theoretical_cogs_cents)         AS theoretical_cents,
    ROUND(
      (SUM(actual_cogs_cents) - SUM(theoretical_cogs_cents))::NUMERIC
        / NULLIF(SUM(net_sales_cents), 0),
    4)                                  AS variance_pct
  FROM world.inv_cogs_daily   -- or equivalent table discovered via tool_discovery
  GROUP BY store_id, period
)
SELECT *,
  LAG(variance_pct) OVER (PARTITION BY store_id ORDER BY period) AS prev_variance_pct,
  LAG(variance_pct, 2) OVER (PARTITION BY store_id ORDER BY period) AS prev2_variance_pct
FROM monthly
ORDER BY store_id, period;
```

**For settlement_reconciliation (consecutive-days check):**
After computing daily gaps, check how many consecutive days a store shows a gap:
```sql
SELECT
  store_id,
  business_date,
  missing_cents,
  COUNT(*) OVER (
    PARTITION BY store_id
    ORDER BY business_date
    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
  ) AS consecutive_gap_days
FROM settlement_gaps  -- from skill_multi_record_join output
WHERE missing_cents > 0;
```

### Step 3 — Classify
**Spike (single period above threshold):**
- Current period > threshold, previous period(s) within tolerance.
- `variance_pct_now > 0.34` AND `prev_variance_pct <= 0.34`.
- → NOT flag-eligible. Submit `within_tolerance` with note: "Single-period spike (current: X%, prior period: Y%). Not flag-eligible until trend confirmed."

**Trend (multiple consecutive periods above threshold):**
- Current AND previous period(s) above threshold.
- `variance_pct_now > 0.34` AND `prev_variance_pct > 0.34`.
- → Flag-eligible. Proceed to known-cause gate.

**Mixed (trend partially explained by known cause):**
- Some periods explained by a price change, some not.
- → Flag only the unexplained periods. Cite the explained ones in the evidence trail.

### Step 4 — Document persistence in the evidence trail
```
Trend classification: TREND (2 consecutive months above 34% band)
  2026-04: variance_pct = 36.2%  (above upper band 34%)
  2026-05: variance_pct = 37.8%  (above upper band 34%)
  Flag-eligible: YES
```
Or:
```
Trend classification: SPIKE (1 period only)
  2026-05: variance_pct = 38.1%  (above upper band 34%)
  2026-04: variance_pct = 29.4%  (within band)
  Flag-eligible: NO — submit within_tolerance with monitoring note
```

## Guardrails enforced
- **GR1**: Known-cause gate still required even for confirmed trends (a price change can explain a multi-month variance).
- Anti-hallucination: period counts must be sourced from actual query rows, not estimated.
