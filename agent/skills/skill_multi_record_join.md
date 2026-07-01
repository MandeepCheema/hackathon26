---
name: skill_multi_record_join
capability: B2
applies_to: [three_way_match, settlement_reconciliation]
build_priority: 3
status: ready
---

# Skill: Multi-Record Join (B2)

**One-line purpose:** Generalized cross-source join for reconciliation duties. Parameterized per duty's entities and join keys.

## When to use
Use this skill when a duty requires comparing records across more than two tables — specifically three-way match (PO + receipt + invoice) and settlement reconciliation (register + fee schedule + bank deposit + adjustments).

## Procedure

### For three_way_match

**Join pattern:**
```sql
WITH po_lines AS (
  SELECT
    pl.id               AS po_line_id,
    pl.po_id,
    pl.sku_id,
    pl.ordered_qty,
    pl.agreed_unit_cost_cents,
    p.supplier_id,
    p.store_id
  FROM world.fin_po_lines pl
  JOIN world.fin_purchase_orders p ON p.id = pl.po_id
  WHERE p.status NOT IN ('cancelled', 'draft')
),
receipts AS (
  SELECT po_line_id, SUM(received_qty) AS received_qty
  FROM world.fin_goods_receipts
  GROUP BY po_line_id
),
invoiced AS (
  SELECT
    il.po_line_id,
    SUM(il.billed_qty)             AS billed_qty,
    MAX(il.billed_unit_cost_cents) AS billed_unit_cost_cents
  FROM world.fin_invoice_lines il
  GROUP BY il.po_line_id
),
credits AS (
  SELECT po_line_id, SUM(amount_cents) AS credited_cents
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
  COALESCE(r.received_qty, 0)                                    AS received_qty,
  COALESCE(inv.billed_qty, 0)                                    AS billed_qty,
  COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents) AS billed_unit_cost_cents,
  COALESCE(cr.credited_cents, 0)                                 AS credited_cents,
  -- Variances
  COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents) - pol.agreed_unit_cost_cents AS price_var_cents,
  COALESCE(inv.billed_qty, 0) - COALESCE(r.received_qty, 0)      AS qty_var,
  (COALESCE(inv.billed_qty, 0) * COALESCE(inv.billed_unit_cost_cents, pol.agreed_unit_cost_cents))
    - (COALESCE(r.received_qty, 0) * pol.agreed_unit_cost_cents)
    - COALESCE(cr.credited_cents, 0)                             AS net_amount_var_cents
FROM po_lines pol
LEFT JOIN receipts r ON r.po_line_id = pol.po_line_id
LEFT JOIN invoiced inv ON inv.po_line_id = pol.po_line_id
LEFT JOIN credits cr ON cr.po_line_id = pol.po_line_id
WHERE COALESCE(inv.billed_qty, 0) > 0  -- only lines that have been invoiced
```

Record any missing join sides:
- `LEFT JOIN receipts` with no match → receipt not found → note as "no goods receipt on file"
- `LEFT JOIN invoiced` with no match → not yet invoiced → skip (not a three-way match case yet)

### For settlement_reconciliation

**Join pattern:**
```sql
WITH card_by_type AS (
  SELECT
    cm.store_id,
    cm.business_date,
    SUM(cm.gross_cents)                              AS register_card_cents,
    SUM(cm.gross_cents * fs.mdr_bps / 10000.0
        + cm.txn_count * fs.per_txn_fee_cents)       AS expected_fee_cents
  FROM world.fin_card_mix cm
  JOIN world.fin_fee_schedule fs
    ON fs.processor = cm.processor
    AND fs.card_type = cm.card_type
    AND fs.effective_date <= cm.business_date
  GROUP BY cm.store_id, cm.business_date
),
adjustments AS (
  SELECT store_id, business_date, SUM(amount_cents) AS adj_cents
  FROM world.fin_settlement_adjustments
  GROUP BY store_id, business_date
)
SELECT
  rt.store_id,
  rt.business_date,
  c.register_card_cents,
  c.expected_fee_cents,
  bs.net_deposit_cents,
  bs.deposit_date,
  COALESCE(a.adj_cents, 0)                    AS adj_cents,
  c.register_card_cents
    - c.expected_fee_cents
    - bs.net_deposit_cents
    - COALESCE(a.adj_cents, 0)                AS missing_cents,
  bs.deposit_date - rt.business_date          AS deposit_lag_days
FROM world.fin_register_totals rt
JOIN card_by_type c
  ON c.store_id = rt.store_id AND c.business_date = rt.business_date
JOIN world.fin_bank_settlements bs
  ON bs.store_id = rt.store_id
  AND bs.covers_date = rt.business_date
LEFT JOIN adjustments a
  ON a.store_id = rt.store_id AND a.business_date = rt.business_date
WHERE rt.card_cents > 0
```

### Missing source handling (GR6)
If a join produces no rows:
- Check whether the source table exists (was confirmed in skill_tool_discovery).
- If the table exists but has no matching rows for this entity/date: record "no receipt/deposit/invoice found" in the evidence trail.
- If the table does not exist: route to ABSTAIN per GR6.

## Output
Returns the full joined record set for the duty. Pass to skill_known_cause_gate for each row with a variance.
