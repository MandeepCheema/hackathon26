---
name: policy
description: Look up McContext's active, effective-dated policies before judging a finance exception, and cite the policy id.
---
# Policy grounding
Before a three-way-match or cogs verdict, run `agent/duties/policy_lookup.sql` via `run_sql` and apply:
- **finpol_materiality** — don't raise a 3-way exception under $5.00 AND under 0.5% of the line (both).
- **finpol_pricetol** — a billed price within 0.5% of contract is within tolerance (not an exception).
- **finpol_foodcost** — food cost ~30% of net sales; flag leakage only when materially over 34% AND unexplained; under 28% is favorable.
Always use the ACTIVE row (never a retired policy) and cite its id in your note.
