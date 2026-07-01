-- agent/duties/settlement_reconciliation.sql
-- Candidate-net query for the settlement_reconciliation duty.
--
-- What this computes:
--   expected_fee = SUM per card type of (gross_cents * mdr_bps / 10000 + txn_count * per_txn_fee_cents)
--   missing = register_card_cents - expected_fee_cents - net_deposit_cents - adjustment_cents
--   deposit_lag_days = deposit_date - business_date (T+1/T+2 is normal)
--
-- Cardinality note: this query assumes 1:1 (one register day : one deposit record).
-- Run skill_cardinality_matching BEFORE interpreting results if deposit_lag patterns are unusual.
--
-- Candidate thresholds:
--   missing > 0 after fee modeling → shortfall candidate
--   deposit_lag_days > 2 → timing_pending candidate (check before flagging shortfall)
--   missing <= 0 → reconciled (submit to record it was checked)
--
-- Run via: run_sql(query=<this file>, purpose="settlement reconciliation candidate net — all store-days")

WITH fee_modeled AS (
  SELECT
    cm.store_id,
    cm.business_date,
    SUM(cm.gross_cents)                                                   AS register_card_cents,
    SUM(
      cm.gross_cents::NUMERIC * fs.mdr_bps / 10000.0
      + cm.txn_count * fs.per_txn_fee_cents
    )::BIGINT                                                             AS expected_fee_cents
  FROM world.fin_card_mix cm
  JOIN world.fin_fee_schedule fs
    ON  fs.processor   = cm.processor
    AND fs.card_type   = cm.card_type
    -- Use the fee schedule in effect on the business date
    AND fs.effective_date = (
      SELECT MAX(effective_date)
      FROM world.fin_fee_schedule fs2
      WHERE fs2.processor  = cm.processor
        AND fs2.card_type  = cm.card_type
        AND fs2.effective_date <= cm.business_date
    )
  GROUP BY cm.store_id, cm.business_date
),
adjustments AS (
  SELECT
    store_id,
    business_date,
    SUM(amount_cents) AS adj_cents
  FROM world.fin_settlement_adjustments
  GROUP BY store_id, business_date
)
SELECT
  rt.store_id,
  rt.business_date,
  f.register_card_cents,
  f.expected_fee_cents,
  bs.net_deposit_cents,
  bs.deposit_date,
  bs.deposit_date - rt.business_date                AS deposit_lag_days,
  COALESCE(a.adj_cents, 0)                          AS adj_cents,
  -- The gap: what's missing after fee modeling and logged adjustments
  f.register_card_cents
    - f.expected_fee_cents
    - bs.net_deposit_cents
    - COALESCE(a.adj_cents, 0)                      AS missing_cents,
  -- Convenience flag
  CASE
    WHEN bs.deposit_date - rt.business_date > 2 THEN true
    ELSE false
  END                                               AS is_timing_lag
FROM world.fin_register_totals rt
JOIN fee_modeled f
  ON  f.store_id      = rt.store_id
  AND f.business_date = rt.business_date
JOIN world.fin_bank_settlements bs
  ON  bs.store_id   = rt.store_id
  AND bs.covers_date = rt.business_date
LEFT JOIN adjustments a
  ON  a.store_id      = rt.store_id
  AND a.business_date = rt.business_date
WHERE rt.card_cents > 0  -- only days with card transactions
ORDER BY ABS(
  f.register_card_cents - f.expected_fee_cents - bs.net_deposit_cents - COALESCE(a.adj_cents, 0)
) DESC;  -- largest gaps first
