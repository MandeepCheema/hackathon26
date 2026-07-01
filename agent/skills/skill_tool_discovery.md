---
name: skill_tool_discovery
capability: B1
applies_to: all_duties
build_priority: 1
status: ready
---

# Skill: Tool Discovery (B1)

**One-line purpose:** Enumerate MCP tools and live schema before any duty runs. No table or field name is trusted until this skill confirms it exists.

## When to run
Run ONCE at session start, before the first duty. Cache the result. Do NOT re-run per duty (token efficiency rule).

## Procedure

### Step 1 — List available MCP action tools
Run a query to confirm the submit_* tools available this session:
```sql
-- This is a schema introspection query, not a data query.
-- Use whatever the MCP exposes for tool listing, or proceed to Step 2
-- and rely on the tool definitions provided in your context.
```
If the MCP provides a tools/list endpoint, record all tool names and their required fields.
If not, trust the tool definitions injected in your system prompt.

### Step 2 — Enumerate the live database schema
```sql
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema IN ('world', 'synth')
ORDER BY table_schema, table_name, ordinal_position;
```
If this query fails (table not accessible), try:
```sql
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
```

Record which tables exist. **Never reference a table that did not appear in this query.**

### Step 3 — Verify per-duty tables exist
For each duty you are about to run, confirm its core tables are present.
Expected tables per duty (verify, do not assume):

| Duty | Expected tables |
|------|----------------|
| cash_over_short | fin_register_totals, fin_cash_counts, fin_paid_outs |
| loss_prevention | fin_register_txns |
| settlement_reconciliation | fin_bank_settlements, fin_card_mix, fin_register_totals, fin_fee_schedule, fin_settlement_adjustments |
| three_way_match | fin_purchase_orders, fin_po_lines, fin_goods_receipts, fin_invoice_lines, fin_price_list, fin_policy |
| duplicate_payment | fin_payments_out, fin_invoices, fin_credit_memos |
| cogs_leakage | fin_policy, fin_price_list |

If a table is missing: do not proceed with that duty. Surface the missing table per GR6 and route to abstain.

### Step 4 — Cache the trusted table list
After confirming which tables exist, the session has a trusted schema. All subsequent SQL queries must only reference tables from this confirmed list.

### Step 5 — Verify policy tables
```sql
SELECT id, body, effective_from, effective_to
FROM world.fin_policy
ORDER BY effective_from DESC;
```
Record all active policy IDs. Key IDs to look for:
- `finpol_materiality` — three-way match materiality threshold
- `finpol_pricetol` — price tolerance for three-way match
- `finpol_foodcost` — COGS target band (28%/30%/34%)

If policy tables are missing or return no rows: note this. GR9 requires surfacing unconfigured thresholds rather than defaulting silently.

## Output
After this skill completes:
- You know which tables exist in the live schema.
- You know which policy IDs are active.
- You know which action tools are available.
- Proceed to the duty router.

## Guardrails enforced
- **GR6**: A missing table is surfaced explicitly, never treated as "no issue found."
- **Anti-hallucination**: Never state a table name not returned by this enumeration.
