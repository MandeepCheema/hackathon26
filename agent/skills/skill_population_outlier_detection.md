---
name: skill_population_outlier_detection
capability: B2
applies_to: [loss_prevention, cash_over_short]
build_priority: 4
status: ready
---

# Skill: Population Outlier Detection (B2)

**One-line purpose:** Compute peer/rolling-window baselines and surface anomalous entities as candidates. Parameterized by metric (void rate, cash variance) and population (store, shift type, peer group).

## When to use
Use for duties with the `B_population_pattern` workflow shape: `loss_prevention` and `cash_over_short`.

The pattern: aggregate over a rolling window → compute baseline → test for persistent anomaly → surface candidates.

## Procedure

### For cash_over_short

**Metric:** `till_variance = counted_cash_cents - expected_cash_cents`
**Population:** all store-days in the analysis window
**Test:** one-sample t-statistic testing whether mean daily variance differs from zero

```sql
WITH v AS (
  SELECT
    rt.store_id,
    rt.business_date,
    cc.counted_cash_cents
      - (rt.cash_cents - COALESCE(po.amt, 0))   AS var_cents
  FROM world.fin_register_totals rt
  JOIN world.fin_cash_counts cc
    ON cc.store_id = rt.store_id
    AND cc.business_date = rt.business_date
  LEFT JOIN (
    SELECT store_id, business_date, SUM(amount_cents) AS amt
    FROM world.fin_paid_outs
    GROUP BY store_id, business_date
  ) po
    ON po.store_id = rt.store_id
    AND po.business_date = rt.business_date
)
SELECT
  store_id,
  COUNT(*)                                                             AS days,
  SUM(CASE WHEN var_cents <> 0 THEN 1 ELSE 0 END)                     AS nonzero_days,
  ROUND(AVG(var_cents))                                                AS avg_var_cents,
  ROUND(STDDEV_POP(var_cents))                                         AS sd_cents,
  SUM(var_cents)                                                       AS net_cents,
  ROUND(
    (AVG(var_cents) / NULLIF(STDDEV_POP(var_cents), 0))
      * SQRT(COUNT(*))::NUMERIC,
  2)                                                                   AS tstat
FROM v
GROUP BY store_id;
```

**Candidate thresholds:**
- `tstat <= -3` AND `net_cents < 0` → `pattern_short` candidate
- `tstat >= 3` AND `net_cents > 0` → `over` candidate
- `|tstat| < 3` → noise → submit `balanced` to record it was checked

**Thin evidence rule:** Do not classify a store with fewer than 7 days of data. Record "Insufficient data (N < 7 days)" and route to ABSTAIN.

### For loss_prevention

**Metric:** void_rate, no_sale_rate, discount_rate per cashier
**Population:** all cashiers in the store (same-store peer baseline)
**Test:** z-score vs peer mean and standard deviation

```sql
WITH s AS (
  SELECT
    staff_id,
    store_id,
    SUM((txn_type = 'sale')::INT)     AS sales,
    SUM((txn_type = 'void')::INT)     AS voids,
    SUM((txn_type = 'refund')::INT)   AS refunds,
    SUM((txn_type = 'no_sale')::INT)  AS no_sales,
    SUM((txn_type = 'discount')::INT) AS discounts
  FROM world.fin_register_txns
  GROUP BY staff_id, store_id
),
r AS (
  SELECT *,
    voids::NUMERIC  / NULLIF(sales + voids, 0)    AS void_rate,
    no_sales::NUMERIC / NULLIF(sales + no_sales, 0) AS no_sale_rate,
    discounts::NUMERIC / NULLIF(sales, 0)          AS discount_rate
  FROM s
),
peer AS (
  SELECT
    AVG(void_rate)     AS pm_void,
    STDDEV_POP(void_rate) AS ps_void,
    AVG(no_sale_rate)  AS pm_no_sale,
    STDDEV_POP(no_sale_rate) AS ps_no_sale
  FROM r
),
store_agg AS (
  SELECT
    store_id,
    SUM(voids)::NUMERIC / NULLIF(SUM(sales + voids), 0) AS store_void_rate
  FROM r GROUP BY store_id
)
SELECT
  r.staff_id,
  r.store_id,
  r.sales,
  r.voids,
  r.refunds,
  r.no_sales,
  r.discounts,
  ROUND(r.void_rate, 3)       AS void_rate,
  ROUND(peer.pm_void, 3)      AS peer_mean_void,
  ROUND(peer.ps_void, 3)      AS peer_sd_void,
  ROUND((r.void_rate - peer.pm_void) / NULLIF(peer.ps_void, 0), 2)  AS z_void,
  ROUND(r.no_sale_rate, 3)    AS no_sale_rate,
  ROUND((r.no_sale_rate - peer.pm_no_sale) / NULLIF(peer.ps_no_sale, 0), 2) AS z_no_sale,
  ROUND(sa.store_void_rate, 3) AS store_void_rate
FROM r
CROSS JOIN peer
JOIN store_agg sa ON sa.store_id = r.store_id;
```

**Candidate thresholds:**
- `z_void >= 2.5` AND `(sales + voids) >= 20` AND NOT store-wide → `refer_investigation`
- `1.5 <= z_void < 2.5` AND individual → `monitor`
- Store-wide detection: if 3+ cashiers in the same store have `z_void >= 2.5` → store-wide signal → `clear` all
- Activity floor: `(sales + voids) < 20` → exclude from referral (too few transactions to be meaningful)

## Output
Returns candidate list per entity with computed metrics. Pass to skill_severity_handling (cash) or skill_known_cause_gate (loss) for next stage.
