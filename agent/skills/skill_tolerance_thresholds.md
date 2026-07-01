---
name: skill_tolerance_thresholds
capability: B4
applies_to: all_duties
build_priority: 2
status: ready
---

# Skill: Tolerance Thresholds (B4)

**One-line purpose:** Every materiality and tolerance value is fetched from business config at runtime. Never hardcode a number. If a threshold is unconfigured, surface it — do not silently default.

## Procedure

### Step 1 — Fetch thresholds from fin_policy
Before applying any threshold, query the policy table:

```sql
SELECT id, body, effective_from, effective_to
FROM world.fin_policy
WHERE id IN (
  'finpol_materiality',
  'finpol_pricetol',
  'finpol_foodcost'
)
AND (effective_to IS NULL OR effective_to > CURRENT_DATE)
ORDER BY effective_from DESC;
```

Parse the `body` field for the numeric values. Common structure:
- `finpol_materiality`: `{"min_usd": 5.00, "min_pct": 0.005}` → $5 AND 0.5%
- `finpol_pricetol`: `{"max_pct": 0.005}` → 0.5% price tolerance
- `finpol_foodcost`: `{"target_pct": 0.30, "lower_band": 0.28, "upper_band": 0.34}`

### Step 2 — Check for unconfigured thresholds

If a required policy row is missing or its body does not contain the expected field:
- Do NOT apply a default value silently.
- Record: "Threshold [policy_id] not configured. Cannot apply materiality filter."
- For the affected duty, route the outcome to ABSTAIN with the specific missing threshold named.

**Example abstain note:**
> "Abstaining: finpol_materiality threshold not present in world.fin_policy as of today. Cannot determine whether $47 variance is material. Controller should configure this policy before re-running."

### Step 3 — Apply thresholds correctly
- Materiality is AND-logic: a variance must exceed BOTH the dollar floor AND the percentage floor to be material.
- Price tolerance: if billed unit price is within X% of the contracted price, it is within tolerance even if the absolute dollar amount is large.
- COGS band: only flag above the upper band; clear between lower and upper band; note favorable below lower band.

### Step 4 — Cite the policy ID in every verdict
Every verdict note must cite the policy ID used:
> "Flag: $47.20 price variance (po_line_id=pln_0042). Exceeds finpol_materiality: $5 AND 0.5% of line ($42 = 11.2%). Price diff 15.3% exceeds finpol_pricetol: 0.5%."

## Tunable defaults (for reference only — use actual policy table values)
These are industry-typical starting points from market research, not McContext-confirmed values:
- Three-way match materiality: ~$5 and 0.5% (reference only)
- Price tolerance: ~0.5% (reference only)
- COGS target: ~30%, band 28–34% (reference only)

These numbers appear in the design docs but must be confirmed from fin_policy before use.

## Guardrails enforced
- **GR9**: No hardcoded thresholds. If unconfigured, halt and surface — never default silently.
