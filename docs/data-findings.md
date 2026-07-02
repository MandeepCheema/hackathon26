# Data findings — the `world` schema & Penny's real leak inventory

> Read-only Postgres, `world.*` schema (44 tables). Connect via `WORLD_PG_URI` in `.env`.
> All figures **rubric-grounded** (see [mcp-contract.md](mcp-contract.md), [policies.md](policies.md)). Dev subset = 10 stores, ~182 days (Dec 2025 – Jun 2026).

## Schema by domain

- **Support (Patty):** `customers`, `orders`, `order_items`, `payments`, `tickets`, `incidents`, `refunds_credits`, `loyalty_accounts`, `loyalty_ledger`, `gift_cards`, `fraud_flags`, `policy_registry`, `menu_items`, `catering_orders`, `deliveries`
- **Finance (Penny):** `fin_purchase_orders`, `fin_po_lines`, `fin_goods_receipts`, `fin_invoices`, `fin_invoice_lines`, `fin_payments_out`, `fin_credit_memos`, `fin_register_totals`, `fin_register_txns`, `fin_card_mix`, `fin_bank_settlements`, `fin_settlement_adjustments`, `fin_cash_counts`, `fin_paid_outs`, `fin_fee_schedule`, `fin_price_list`, `fin_policy`, `fin_suppliers`, `fin_staff`
- **Inventory (Stock):** `inv_skus`, `inv_recipes`, `inv_counts`, `inv_receipts`, `inv_sales_daily`, `inv_usage_daily`, `inv_waste_logs`, `inv_shift_logs`
- **Shared:** `stores`, `world_meta`

## Penny leak inventory (visible data — the real signal)

| Duty | Real finding | Decoy (do NOT flag) |
|---|---|---|
| **Cash over/short** | `str_009` −$610 (t=−3.8), `str_003` −$569 (t=−3.8) → `pattern_short`. `expected = cash_sales − paid_outs`. | Single-day one-offs; sub-$5 noise (269 store-days); `str_001` +$27 *over*. |
| **Loss prevention** | `stf_009_6` @ str_009 = 0.61 void rate vs 0.17 peer → `refer_investigation`; **corroborates str_009 cash short**. | `str_004` high-void *cluster* = store-wide (POS) → `clear`/`monitor`. |
| **Settlement** | **7** store-days, **$905** unreconciled after fees AND logged adjustments. | 3 adjustment-explained decoys (str_008 03-02 terminal_reset, str_010 03-16 refund batch, str_010 03-17 chargeback — residual $0); plain fee/timing gaps. |
| **Three-way match** | **6** policy-aware exceptions, **~$311**. | pol_00150: over-billing exactly covered by credit memo memo_00001 (engineered trap); lines within materiality/tolerance (pol_00037/090/148). |
| **Duplicate payment** | **0** in visible data (0 po-lines double-billed, 0 invoices paid twice). | 55 recurring same-amount payments (distinct invoices, weekly cadence). Real dups only in hidden bench cases. |
| **COGS leakage** | compute revenue×30% vs actual purchasing; flag store-periods >34% unexplained. | 28–34% band = within tolerance. |

## Method notes (traps we hit)
- Cash expected must subtract `fin_paid_outs` and flag only **persistent directional** shorts — not single-day variance.
- Settlement gaps must net out `expected_fee` (from `fin_fee_schedule`) + logged adjustments before flagging.
- Loss prevention must compare to a **peer baseline** and exclude store-wide spikes (POS outage) and trainees/managers.
- Three-way match must apply **materiality + price-tolerance** (policy) before flagging.
- "Same supplier + same amount, many times" is the recurring-payment **decoy**, not a duplicate.
- **Credit memos are the master trap key** (`fin_credit_memos`): memo_00001 explains pol_00150's three-way exception exactly; memo_00002 marks inv_00295 as voided-and-reissued (dup decoy).
- **Settlement gaps must also net `fin_settlement_adjustments`** (refund batch, chargeback, terminal reset) — 3 of the naive 10 shortfalls vanish.

## Demo spine (why Cash + Loss-Prevention lead)
`str_009` carries **both** a persistent cash short **and** a high-void cashier → Penny chains them into one investigative referral, while clearing `str_004`'s store-wide voids. Chained, judgment-heavy, real — the strongest proof it's an agent, not a rule.
