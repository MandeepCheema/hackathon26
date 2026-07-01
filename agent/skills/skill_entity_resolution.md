---
name: skill_entity_resolution
capability: B2
applies_to: all_duties
build_priority: 6
status: ready
---

# Skill: Entity Resolution (B2)

**One-line purpose:** Resolves colliding or inconsistent identifiers to a canonical entity before any verdict is issued. Prevents a finding from being mis-attributed to the wrong store, cashier, or vendor.

## When to use
Use when:
- A query returns an entity ID that doesn't match what you expect (e.g., `str_09` vs `str_009`)
- Two entity records appear to refer to the same real-world entity with different IDs
- A staff_id appears in txns but not in the staff table
- A po_id appears in invoices but not in the PO table

## Procedure

### Step 1 — Check for ID format inconsistencies
After running a candidate query, verify that the entity IDs in the result match the canonical format used in the system:

```sql
-- Check store ID format
SELECT DISTINCT store_id FROM world.fin_register_totals ORDER BY store_id;
-- Expected: str_001, str_002, ..., str_010

-- Check staff ID format
SELECT DISTINCT staff_id FROM world.fin_register_txns ORDER BY staff_id;
-- Expected: stf_009_1, stf_009_2, ...

-- Check supplier ID format
SELECT DISTINCT supplier_id FROM world.fin_purchase_orders ORDER BY supplier_id;
```

If an ID in your candidate result doesn't match the canonical format, do NOT assume it's the same entity. Query to confirm.

### Step 2 — Verify orphaned IDs
If a candidate entity ID doesn't exist in its primary table, it may be:
- A data error (orphaned record)
- A recently added entity not yet in all tables
- A test/dummy record

```sql
-- Example: staff_id in txns but not in staff table
SELECT t.staff_id
FROM world.fin_register_txns t
LEFT JOIN world.fin_staff s ON s.id = t.staff_id
WHERE s.id IS NULL
GROUP BY t.staff_id;
```

If an orphaned ID is in your candidate set: note it in the evidence trail. Do not fabricate a resolution — flag it as "entity not found in primary table; entity resolution incomplete."

### Step 3 — Near-match resolution (conservative)
If you suspect two IDs refer to the same entity (e.g., `str_09` and `str_009`):
1. Check both IDs in relevant tables.
2. If they share the same address, manager, or related records: they may be the same entity.
3. **Do not merge them without confirmation.** Note the potential collision in the evidence trail.
4. Assign the finding to the ID that appears in the authoritative table (fin_register_totals, fin_purchase_orders).

### Step 4 — Document in the evidence trail
```
Entity resolution: str_009 confirmed (found in fin_register_totals, fin_cash_counts, fin_register_txns)
Entity resolution: stf_009_6 confirmed (found in fin_register_txns; not queried in fin_staff — table presence unverified)
```

## Output
Returns: canonical entity ID with confidence flag.
- `confirmed`: entity found in primary table
- `unverified`: entity found in transaction tables but not in master table
- `collision_suspected`: two IDs may refer to same entity; not resolved

## Guardrails enforced
- Anti-hallucination: never state an entity is confirmed if it wasn't actually found in the primary table query.
