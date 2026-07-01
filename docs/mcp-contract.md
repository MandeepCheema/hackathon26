# McContext MCP — tool contract & rubric

> Server: `mccontext-company-systems` v1.28.1 · endpoint in `.env` (`MCCTX_MCP_URL` + `MCP_AUTH_TOKEN`).
> Discovered live via `tools/list`. **The tool descriptions ARE the scoring rubric** — each names exactly what to flag and what NOT to (the decoys).

## All 17 tools

**Investigate (read):**
- `run_sql(query, purpose)` — READ-ONLY `SELECT`/`WITH` against the `world.*` schema. The only read tool; explore schema via `information_schema`.

**Penny · Finance & Controls (action = graded output):**
- `submit_cash_variance` · `submit_duplicate_payment` · `submit_match_exception` · `submit_loss_flag` · `submit_cogs_variance` · `submit_settlement`

**Patty · Support:** `issue_credit` · `issue_refund` · `escalate` · `create_ticket`
**Stock · Inventory:** `submit_variance` · `submit_forecast` · `submit_reorder` · `submit_markdown`
**Pivot · Analyst:** `submit_answer` · `submit_report`

## Penny action-tool schemas (\* = required)

### `submit_cash_variance`
> Flag a cash over/short for a store-day (or a persistent pattern). `expected_cash = cash sales − logged paid-outs`. **Do NOT flag normal single-day variance or a short explained by a logged paid-out / change order; the real signal is a persistent directional short** (use `business_date='pattern'`).
- `*store_id` · `*business_date` · `*status` ∈ `{balanced, short, over, pattern_short}` · `expected_cash_cents` · `counted_cash_cents` · `variance_cents` · `note`

### `submit_duplicate_payment`
> Flag a duplicate payment: `invoice_id` paid again for goods already covered by `duplicate_of_invoice_id`. **Do NOT flag legitimate recurring charges (distinct periods) or a re-issued invoice whose original was voided/credited.**
- `*supplier_id` · `*invoice_id` · `*duplicate_of_invoice_id` · `*amount_cents` · `note`

### `submit_match_exception`
> Three-way-match exception on a PO line (ordered vs received vs billed). `amount_cents = recoverable error`. **Do NOT flag lines that reconcile within the materiality threshold or are explained (contracted price, credit memo).**
- `*po_id` · `*po_line_id` · `*exception_type` ∈ `{price_variance, over_billed_qty, short_received, duplicate_invoice, unauthorized_charge, tax_miscalc}` · `*amount_cents` · `note`

### `submit_loss_flag`
> Flag a cashier for loss prevention (submit only non-clear). **Compare against the peer baseline; do NOT refer honest outliers (trainees, managers, store-wide POS-outage spikes).**
- `*staff_id` · `*store_id` · `*risk_level` ∈ `{refer_investigation, monitor, clear}` · `*primary_signal` ∈ `{void_rate, refund_to_card, no_sale_opens, discount_abuse, refund_no_sale}` · `evidence_note`

### `submit_cogs_variance`
> COGS / margin-leakage verdict for a store-period. `theoretical_cents = revenue × target food-cost %`. **Flag leakage only when materially over target and unexplained by contracted prices.**
- `*store_id` · `*period` · `*status` ∈ `{within_tolerance, leakage, favorable}` · `theoretical_cents` · `actual_cents` · `variance_pct` · `note`

### `submit_settlement`
> Settlement reconciliation for one store-day. For a real shortfall, `missing_cents = unexplained gap AFTER expected processor fee and any logged refund/chargeback/timing`. **Submit only days that don't reconcile.**
- `*store_id` · `*business_date` · `*status` ∈ `{reconciled, shortfall, over_deposit, timing_pending}` · `register_card_cents` · `expected_fee_cents` · `deposit_cents` · `missing_cents` · `note`

## Design implications
- Read = `run_sql`; the "deterministic sidecar" is SQL the agent composes/runs.
- **Clearing a decoy is an explicit action** (`risk_level=clear`, `status=within_tolerance`/`balanced`) — precision is scored by submitting the *right status*, not by silence.
- Every skill = { the tool's definition + the governing policy (see [policies.md](policies.md)) + the named decoy exclusions }.
