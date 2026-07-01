-- agent/duties/three_way_match.sql
-- Candidate-net query for the three_way_match duty.
--
-- What this computes per PO line:
--   price_var_cents      = billed_unit_cost - agreed_unit_cost
--   qty_var              = billed_qty - received_qty
--   net_amount_var_cents = (billed_qty * billed_unit_cost) - (received_qty * agreed_unit_cost) - credited_cents
--   price_pct_diff       = |price_var| / agreed_unit_cost (for price tolerance check)
--   amount_pct_of_line   = |net_amount_var| / (received_qty * agreed_unit_cost)
--
-- Materiality filter (from finpol_materiality — fetch live values before applying):
--   net_amount_var > $5 AND amount_pct_of_line > 0.5% → material candidate
-- Price tolerance filter (from finpol_pricetol):
--   price_pct_diff > 0.5% → price exception candidate
--
-- NOTE: fetch finpol_materiality and finpol_pricetol from world.fin_policy BEFORE running this
-- query and substitute their values for the placeholder values below ($500 cents, 0.005, 0.005).
--
-- Run via: run_sql(query=<this file>, purpose="three-way match exception candidates — all open PO lines")

WITH po_lines AS (
  SELECT
    pl.id                           AS po_line_id,
    pl.po_id,
    pl.sku_id,
    pl.ordered_qty,
    pl.agreed_unit_cost_cents,
    po.supplier_id,
    po.store_id,
    po.created_at                   AS po_date
  FROM world.fin_po_lines pl
  JOIN world.fin_purchase_orders po ON po.id = pl.po_id
  WHERE po.status NOT IN ('cancelled', 'draft')
),
receipts AS (
  SELECT
    po_line_id,
    SUM(received_qty)               AS received_qty,
    MAX(received_at)                AS receipt_date
  FROM world.fin_goods_receipts
  GROUP BY po_line_id
),
invoiced AS (
  SELECT
    po_line_id,
    SUM(billed_qty)                 AS billed_qty,
    MAX(billed_unit_cost_cents)     AS billed_unit_cost_cents,
    MAX(invoice_id)                 AS invoice_id,
    MAX(invoiced_at)                AS invoice_date
  FROM world.fin_invoice_lines
  GROUP BY po_line_id
),
credits AS (
  SELECT
    po_line_id,
    SUM(amount_cents)               AS credited_cents
  FROM world.fin_credit_memos
  GROUP BY po_line_id
)
SELECT
  pol.po_id,
  pol.po_line_id,
  pol.supplier_id,
  pol.store_id,
  pol.sku_id,
  pol.ordered_qty,
  pol.agreed_unit_cost_cents,
  COALESCE(r.received_qty, 0)                                           AS received_qty,
  COALESCE(inv.billed_qty, 0)                                          AS billed_qty,
  COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents)     AS billed_unit_cost_cents,
  COALESCE(cr.credited_cents, 0)                                       AS credited_cents,
  inv.invoice_id,
  r.receipt_date,
  inv.invoice_date,
  -- Variances
  COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents)
    - pol.agreed_unit_cost_cents                                        AS price_var_cents,
  COALESCE(inv.billed_qty, 0) - COALESCE(r.received_qty, 0)           AS qty_var,
  -- Net amount variance after credits
  (COALESCE(inv.billed_qty, 0) * COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents))
    - (COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents)
    - COALESCE(cr.credited_cents, 0)                                   AS net_amount_var_cents,
  -- % metrics for threshold application
  ROUND(
    ABS(COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents)
      - pol.agreed_unit_cost_cents)::NUMERIC
      / NULLIF(pol.agreed_unit_cost_cents, 0),
  4)                                                                   AS price_pct_diff,
  ROUND(
    ABS(
      (COALESCE(inv.billed_qty, 0) * COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents))
      - (COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents)
      - COALESCE(cr.credited_cents, 0)
    )::NUMERIC
    / NULLIF(COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents, 0),
  4)                                                                   AS amount_pct_of_line,
  -- Pre-filter flag: exceeds rough materiality cutoff (use live policy values, not hardcoded)
  -- Placeholder: $5 AND 0.5% — substitute with finpol_materiality values
  CASE WHEN
    ABS(
      (COALESCE(inv.billed_qty, 0) * COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents))
      - (COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents)
      - COALESCE(cr.credited_cents, 0)
    ) > 500   -- $5 placeholder — replace with live finpol_materiality value
    AND ABS(
      (COALESCE(inv.billed_qty, 0) * COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents))
      - (COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents)
      - COALESCE(cr.credited_cents, 0)
    )::NUMERIC
    / NULLIF(COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents, 0) > 0.005  -- 0.5% placeholder
  THEN true ELSE false END                                             AS exceeds_materiality_placeholder
FROM po_lines pol
LEFT JOIN receipts r    ON r.po_line_id  = pol.po_line_id
LEFT JOIN invoiced inv  ON inv.po_line_id = pol.po_line_id
LEFT JOIN credits cr    ON cr.po_line_id  = pol.po_line_id
WHERE COALESCE(inv.billed_qty, 0) > 0  -- only invoiced lines
ORDER BY ABS(net_amount_var_cents) DESC;
