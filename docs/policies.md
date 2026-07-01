# McContext policies (the grounding for every verdict)

> Source tables: `world.fin_policy`, `world.policy_registry`, `world.fin_fee_schedule`.
> **The agent must read these, cite them, and use only the ACTIVE, effective-dated version.** A no-policy agent cries wolf (flags within-tolerance lines) or over-refunds (uses a retired policy) → zeroed.

## `fin_policy` — finance thresholds (Penny)

| id | topic | rule |
|---|---|---|
| `finpol_materiality` | materiality | Don't raise a 3-way exception for a variance **under $5.00 AND under 0.5% of the line** — both must hold. Genuine price/qty/duplicate/unauthorized/tax errors above this MUST be flagged. |
| `finpol_pricetol` | price_tolerance | A billed unit price **within 0.5% of contracted price** is within tolerance and NOT a price-variance exception — even if the absolute diff exceeds the $5 floor. Flag only if it exceeds BOTH materiality AND tolerance. |
| `finpol_foodcost` | cogs_target | Expected food cost ≈ **30%** of net sales. A store-period **over 34%** with no contracted-price / mix explanation is leakage to investigate; **under 28%** is favorable. |

**Effect (measured):** naive three-way match flags 11 lines; policy-aware (materiality + tolerance) → **7 real, ~$376**; the other 4 are within tolerance = false positives.

## `policy_registry` — versioned, effective-dated (mostly Patty; a version trap)

| id | topic | status | rule |
|---|---|---|---|
| `pol_refund_v2` | refund | **RETIRED** (to 2025-09-01) | issue FULL REFUND to original payment. ⚠️ using this over-refunds. |
| `pol_refund_v3` | refund | **ACTIVE** (from 2025-09-01) | Missing item: STORE CREDIT = item menu price only (no tax). Wrong order: credit = pre-tax subtotal. Tips non-refundable. **7-day window. Tier-1 may issue ≤ $25; above → escalate to tier2.** |
| `pol_outage_v1` | outage_sla | **RETIRED** | FULL REFUND for any affected order. |
| `pol_outage_v2` | outage_sla | **ACTIVE** | Only if a DELIVERY order placed WITHIN a declared delivery-outage window AND delivery fails → STORE CREDIT = pre-tax subtotal (tax/fees/tips excluded). Not otherwise. |

(17 rows total; resolve by `status='active' AND effective_date <= as_of`, newest wins.)

## `fin_fee_schedule` — processor fees (Penny settlement)

| processor | card_type | mdr_bps | per_txn_fee_cents |
|---|---|---|---|
| cardnet | credit | 180 | 10 |
| cardnet | debit | 90 | 10 |
| cardnet | amex | 250 | 0 |

`expected_fee = Σ_cardtype( gross_cents × mdr_bps/10000 + txn_count × per_txn_fee_cents )`.
Settlement `missing = register_card − expected_fee − net_deposit`, after logged adjustments.

## Rule of thumb for the agent
Every flag/clear must be defensible as: **"per policy `<id>`, this variance is / isn't an exception because …"**.
