-- agent/duties/cogs_leakage.sql
-- Candidate-net query for the cogs_leakage duty.
--
-- What this computes:
--   theoretical_cogs = net_sales * target_pct (from finpol_foodcost, typically 30%)
--   variance_pct = (actual_cogs - theoretical_cogs) / net_sales
--
-- Candidate thresholds (from finpol_foodcost — fetch live values before applying):
--   variance_pct > upper_band (34% placeholder) → leakage candidate
--   variance_pct < lower_band (28% placeholder) → favorable
--   lower_band <= variance_pct <= upper_band    → within_tolerance
--
-- skill_trend_vs_spike determines whether a candidate is a spike (single period) or trend.
-- skill_known_cause_gate checks: vendor_price_list_change, recipe_bom_update, substitution_log_entry.
--
-- NOTE: the exact table for actual COGS data must be confirmed via skill_tool_discovery.
-- The query below uses `world.inv_usage_daily` as the expected table. If this table does not
-- exist, check for: inv_cogs_daily, fin_purchasing_summary, or a view.
--
-- Run via: run_sql(query=<this file>, purpose="COGS leakage candidate net — all stores by month")

WITH policy AS (
  -- Fetch live thresholds (substitute into the query below)
  SELECT
    (body->>'target_pct')::NUMERIC   AS target_pct,
    (body->>'lower_band')::NUMERIC   AS lower_band,
    (body->>'upper_band')::NUMERIC   AS upper_band
  FROM world.fin_policy
  WHERE id = 'finpol_foodcost'
    AND (effective_to IS NULL OR effective_to > CURRENT_DATE)
  ORDER BY effective_from DESC
  LIMIT 1
),
monthly_sales AS (
  -- Net sales per store per month (adjust source table after tool_discovery)
  SELECT
    store_id,
    DATE_TRUNC('month', business_date)  AS period,
    SUM(net_sales_cents)                AS net_sales_cents
  FROM world.fin_register_totals
  GROUP BY store_id, DATE_TRUNC('month', business_date)
),
monthly_cogs AS (
  -- Actual food cost per store per month (confirm table via tool_discovery)
  SELECT
    store_id,
    DATE_TRUNC('month', usage_date)     AS period,
    SUM(cost_cents)                     AS actual_cogs_cents
  FROM world.inv_usage_daily
  GROUP BY store_id, DATE_TRUNC('month', usage_date)
)
SELECT
  s.store_id,
  s.period,
  s.net_sales_cents,
  COALESCE(c.actual_cogs_cents, 0)                                    AS actual_cogs_cents,
  -- Theoretical COGS using live policy target_pct
  ROUND(s.net_sales_cents * p.target_pct)                             AS theoretical_cogs_cents,
  -- Variance in cents
  COALESCE(c.actual_cogs_cents, 0)
    - ROUND(s.net_sales_cents * p.target_pct)                         AS variance_cents,
  -- Variance as pct of net sales
  ROUND(
    (COALESCE(c.actual_cogs_cents, 0)
      - ROUND(s.net_sales_cents * p.target_pct))::NUMERIC
    / NULLIF(s.net_sales_cents, 0),
  4)                                                                  AS variance_pct,
  -- Policy bands for reference
  p.target_pct,
  p.lower_band,
  p.upper_band,
  -- Pre-classification (will be re-evaluated after known-cause and trend checks)
  CASE
    WHEN ROUND(
      (COALESCE(c.actual_cogs_cents, 0) - ROUND(s.net_sales_cents * p.target_pct))::NUMERIC
      / NULLIF(s.net_sales_cents, 0), 4) > p.upper_band
    THEN 'above_upper_band'
    WHEN ROUND(
      (COALESCE(c.actual_cogs_cents, 0) - ROUND(s.net_sales_cents * p.target_pct))::NUMERIC
      / NULLIF(s.net_sales_cents, 0), 4) < p.lower_band
    THEN 'below_lower_band'
    ELSE 'within_band'
  END                                                                 AS band_classification
FROM monthly_sales s
CROSS JOIN policy p
LEFT JOIN monthly_cogs c
  ON  c.store_id = s.store_id
  AND c.period   = s.period
ORDER BY variance_pct DESC;  -- highest overage first
