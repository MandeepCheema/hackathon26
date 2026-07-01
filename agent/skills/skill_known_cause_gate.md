---
name: skill_known_cause_gate
capability: B3
applies_to: all_duties
build_priority: 2
status: ready
---

# Skill: Known-Cause Gate (B3)

**One-line purpose:** For every candidate that passed evidence gathering, run an ordered checklist of known causes before flagging. A variance that matches a known cause is CLEARED — do not flag it.

This is the core false-positive suppressor. Most anomalies have benign explanations. The known-cause gate finds them before a flag is submitted.

## Core principle
A flag is only valid when the variance is BOTH:
1. Statistically anomalous (from B2 evidence gathering), AND
2. Unexplained after ALL relevant known-cause checks pass without a match.

If a known cause explains the variance: submit the cleared status. Do not stay silent.

## Procedure

### Step 1 — Identify the duty's known-cause checklist
Each duty has a defined known-cause check list (from the duty config in the context layer):

| Duty | Known-cause checks |
|------|-------------------|
| three_way_match | partial_or_backordered_delivery, split_invoice_across_pos, logged_price_amendment |
| settlement_reconciliation | processor_fee, t1_posting_lag, same_day_refund_or_chargeback, till_float_change |
| loss_prevention | manager_override_log, promo_calendar_match |
| duplicate_payment | distinct_invoice_id, differing_line_items, differing_po_reference, split_payment_grouping |
| cogs_leakage | vendor_price_list_change, recipe_bom_update, substitution_log_entry |
| cash_over_short | float_change_log, manager_correction_log, same_cashier_shift_assignment |

Run ALL checks on the list. Never skip a check to save tool calls (GR7).

### Step 2 — Run each known-cause check

For each cause, query the relevant table to see if a matching record exists:

**cash_over_short:**
- `float_change_log`: `SELECT * FROM world.fin_paid_outs WHERE store_id = $store AND business_date = $date AND reason ILIKE '%float%'`
- `manager_correction_log`: `SELECT * FROM world.fin_paid_outs WHERE store_id = $store AND business_date = $date AND reason ILIKE '%correction%'`
- `same_cashier_shift_assignment`: `SELECT staff_id, COUNT(*) FROM world.fin_register_txns WHERE store_id = $store AND business_date IN ($dates) GROUP BY staff_id` — check if the same cashier worked all variance days

**loss_prevention:**
- `manager_override_log`: `SELECT * FROM world.fin_register_txns WHERE store_id = $store AND staff_id = $staff AND txn_type = 'void' AND authorized_by IS NOT NULL`
- `promo_calendar_match`: `SELECT * FROM world.fin_promo_calendar WHERE store_id = $store AND period_includes($date)` — if this table doesn't exist, note it as not-run (do NOT treat as run-and-passed)

**settlement_reconciliation:**
- `processor_fee`: Compute `expected_fee` per `fin_fee_schedule` and check if the residual is ≤ $1 after fee netting
- `t1_posting_lag`: Check if `deposit_date - business_date <= 2` (T+1/T+2 is normal)
- `same_day_refund_or_chargeback`: `SELECT SUM(amount_cents) FROM world.fin_settlement_adjustments WHERE store_id = $store AND business_date = $date`

**three_way_match:**
- `partial_or_backordered_delivery`: Check `fin_goods_receipts.received_qty < fin_po_lines.ordered_qty` — if yes and the invoice matches received_qty, it's a legitimate partial
- `split_invoice_across_pos`: Check if multiple invoice lines sum to the PO amount
- `logged_price_amendment`: `SELECT * FROM world.fin_price_list WHERE supplier_id = $supplier AND effective_date <= $invoice_date` — if price was amended before invoice, the price is legitimate

**duplicate_payment:**
- `distinct_invoice_id`: Verify the two payments reference different `invoice_id` values — if yes, not a duplicate
- `differing_line_items`: Compare line items across the two invoices — if different, not a duplicate
- `differing_po_reference`: Check if po_ids differ
- `split_payment_grouping`: Check if two payments together equal one invoice total (intentional split)

**cogs_leakage:**
- `vendor_price_list_change`: `SELECT * FROM world.fin_price_list WHERE supplier_id IN ($suppliers) AND effective_date BETWEEN $period_start AND $period_end`
- `recipe_bom_update`: Query for recipe/BOM changes in the period
- `substitution_log_entry`: Check for logged ingredient substitutions

### Step 3 — Evaluate results

For each cause:
- **Match found** → cause confirmed → candidate is CLEARED. Record: "Cleared by [cause]: [evidence]." Submit the cleared status.
- **No match found** → cause ruled out. Record: "Checked [cause]: no matching record found."
- **Table/data not available** → cause NOT run. Record: "Could not check [cause]: [table] not present." Do NOT treat as run-and-passed (anti-hallucination rule).

### Step 4 — Decision after checklist

- All causes checked AND all cleared → submit clear/balanced/within_tolerance
- All causes checked AND none explain variance → candidate survives → proceed to B3_confidence_gate
- Any cause not runnable due to missing data → route to abstain; name the exact missing data

## Output
Returns one of:
- `CLEARED(cause_id, evidence)` → submit cleared status
- `UNCOVERED` → proceed to confidence gate
- `ABSTAIN(missing: table_or_record)` → cannot complete the checklist

## Guardrails enforced
- **GR1**: No flag without a completed known-cause check.
- **GR6**: A failed check (missing table) is surfaced, never treated as passed.
- **GR7**: Never skip the minimum checklist to save tool calls.
