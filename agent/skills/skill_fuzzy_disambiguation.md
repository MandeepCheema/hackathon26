---
name: skill_fuzzy_disambiguation
capability: B2
applies_to: [duplicate_payment]
build_priority: 6
status: ready
---

# Skill: Fuzzy Disambiguation (B2)

**One-line purpose:** Near-match invoice detection for duplicate payment. Goes beyond exact-match ERP detection to catch near-duplicate invoice IDs and partially-matching line items.

This is a **new capability** not in the original design. Exact-match on `invoice_id` catches obvious duplicates but misses cases where an invoice was resubmitted with a slightly different ID (e.g., `INV-2024-0042` vs `INV-2024-042`).

## Procedure

### Step 1 — Coarse match: same vendor + amount + date proximity
```sql
SELECT
  a.id            AS payment_id_1,
  b.id            AS payment_id_2,
  a.supplier_id,
  a.invoice_id    AS invoice_id_1,
  b.invoice_id    AS invoice_id_2,
  a.amount_cents,
  a.paid_at       AS paid_at_1,
  b.paid_at       AS paid_at_2,
  ABS(EXTRACT(EPOCH FROM (b.paid_at - a.paid_at)) / 86400) AS days_apart
FROM world.fin_payments_out a
JOIN world.fin_payments_out b
  ON  a.supplier_id = b.supplier_id
  AND a.amount_cents = b.amount_cents
  AND a.id < b.id   -- avoid self-join and duplicate pairs
  AND ABS(EXTRACT(EPOCH FROM (b.paid_at - a.paid_at)) / 86400) <= 30  -- within 30 days
ORDER BY a.supplier_id, days_apart;
```

This is the HIGH-RECALL net. Most rows will be legitimate recurring payments (same vendor, same monthly invoice amount). The disambiguation steps below narrow to true duplicates.

### Step 2 — Exact invoice_id match (definitive)
From the coarse-match candidates, check for exact same `invoice_id`:
- If `invoice_id_1 = invoice_id_2`: strong duplicate signal. Proceed to Step 4 (credit memo check).
- If `invoice_id_1 ≠ invoice_id_2`: proceed to Step 3 (near-match).

### Step 3 — Near-match invoice ID scoring
For candidates with different invoice IDs, compute a similarity score:

**Heuristics (apply in order; stop when one gives a clear signal):**

1. **Numeric suffix match:** Strip non-numeric characters and compare the numbers.
   - `INV-2024-0042` → `20240042` vs `INV-2024-042` → `2024042` — same number, different padding → HIGH similarity
   - `INV-2024-0042` vs `INV-2024-0043` — sequential numbers → LOW similarity (distinct invoices)

2. **Line item overlap:** If invoice line detail is available, compare line items:
   ```sql
   SELECT
     a_lines.sku_id,
     a_lines.billed_qty,
     b_lines.billed_qty
   FROM world.fin_invoice_lines a_lines
   JOIN world.fin_invoice_lines b_lines
     ON a_lines.sku_id = b_lines.sku_id
   WHERE a_lines.invoice_id = $invoice_id_1
     AND b_lines.invoice_id = $invoice_id_2;
   ```
   If line_item_overlap_pct > 90% → HIGH similarity (likely same invoice, different ID)
   If line_item_overlap_pct < 50% → LOW similarity (different invoices)

3. **PO reference match:** If both invoices reference the same `po_id`, they may be duplicates — or they may be split invoices against one PO. Check if their combined total exceeds the PO amount.

### Step 4 — Credit memo check (required before any FLAG)
Before flagging any confirmed duplicate, check for a credit memo that voids the original:
```sql
SELECT id, amount_cents, issued_at, reason
FROM world.fin_credit_memos
WHERE invoice_id = $invoice_id_1
   OR invoice_id = $invoice_id_2;
```
- If a credit memo exists for the original payment: the second payment is a re-issuance, NOT a duplicate. Submit nothing (silence = cleared for this tool).
- If no credit memo: confirmed duplicate. Proceed to FLAG.

### Step 5 — Classify outcome

| Signal | Action |
|---|---|
| Exact same `invoice_id`, no credit memo | FLAG as duplicate |
| Near-match ID (padded number), high line-item overlap, same PO, no credit memo | FLAG as duplicate |
| Same vendor + amount, different invoice_id, different line items | CLEAR — recurring payment |
| Same vendor + amount, different invoice_id, different PO reference | CLEAR — distinct invoices |
| Credit memo found | CLEAR — re-issuance |
| Ambiguous (similarity score 40–60%) | ABSTAIN — name the ambiguity |

## Output
Returns: `is_duplicate: true|false|ambiguous`, `similarity_score`, `line_item_overlap_pct`, `classification_reason`

## Note on visible data
The visible McContext dataset contains 55 recurring same-amount payments that are all legitimate (distinct invoice IDs, weekly cadence). The correct answer is silence for all 55. Real duplicates only appear in hidden bench cases.
