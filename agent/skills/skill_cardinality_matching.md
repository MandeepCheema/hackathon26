---
name: skill_cardinality_matching
capability: B2
applies_to: [settlement_reconciliation]
build_priority: 3
status: ready
---

# Skill: Cardinality Matching (B2)

**One-line purpose:** Determine whether a reconciliation is 1:1, 1:many, or many:1 before computing any gap. Computing a gap on the wrong cardinality produces a false result.

This is a **new capability** not in the original agent design. GR10 requires it before any settlement gap is computed.

## Why cardinality matters
A bank may batch-deposit multiple store-days into one deposit record (1:many on the bank side).
A store may split one day's card receipts across multiple settlements (many:1 on the register side).
Computing `register_total - deposit_amount` without knowing cardinality will produce a spurious gap.

## Procedure

### Step 1 — Count register records vs deposit records for the candidate period
```sql
SELECT
  s.covers_date,
  COUNT(DISTINCT r.business_date)   AS register_days,
  COUNT(DISTINCT s.id)              AS deposit_records,
  SUM(r.card_cents)                 AS total_register_card,
  SUM(s.net_deposit_cents)          AS total_deposit,
  CASE
    WHEN COUNT(DISTINCT r.business_date) = 1 AND COUNT(DISTINCT s.id) = 1 THEN '1:1'
    WHEN COUNT(DISTINCT r.business_date) = 1 AND COUNT(DISTINCT s.id) > 1  THEN '1:many'
    WHEN COUNT(DISTINCT r.business_date) > 1 AND COUNT(DISTINCT s.id) = 1  THEN 'many:1'
    ELSE 'many:many'
  END AS cardinality
FROM world.fin_register_totals r
JOIN world.fin_bank_settlements s
  ON s.store_id = r.store_id
  AND r.business_date BETWEEN s.covers_date - INTERVAL '2 days' AND s.covers_date + INTERVAL '2 days'
WHERE r.store_id = $store_id
  AND r.business_date BETWEEN $start_date AND $end_date
GROUP BY s.covers_date, s.store_id;
```

### Step 2 — Apply cardinality-appropriate gap formula

**1:1 (most common):**
```
gap = register_card_cents - expected_fee_cents - net_deposit_cents
```

**1:many (one store-day, multiple deposit batches):**
```
gap = register_card_cents - expected_fee_cents - SUM(net_deposit_cents for all matching deposits)
```

**many:1 (multiple store-days batched into one deposit):**
```
gap = SUM(register_card_cents for all batched days) - SUM(expected_fee_cents for all batched days) - net_deposit_cents
```

**many:many:**
Route to ABSTAIN unless you can cleanly decompose the batch. Note the cardinality type in the evidence trail.

### Step 3 — Record cardinality in the evidence trail
Every settlement verdict must state the cardinality type:
> "Cardinality: 1:1. Register card: $4,821.00. Expected fee: $96.42. Deposit: $4,680.12. Gap: $44.46."

## Output
Returns:
- `cardinality_type`: "1:1" | "1:many" | "many:1" | "many:many"
- `register_total_cents`: aggregated register card amount
- `deposit_total_cents`: aggregated deposit amount
- `register_record_count`: number of register records
- `deposit_record_count`: number of deposit records

## Guardrails enforced
- **GR10**: Cardinality must be determined before any gap is computed. Discarding a computed gap and re-running with correct cardinality is required if this was skipped.
