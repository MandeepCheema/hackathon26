---
name: skill_investigation_depth
capability: B4
applies_to: all_duties
build_priority: 7
status: ready
---

# Skill: Investigation Depth (B4)

**One-line purpose:** Materiality-weighted decision on optional extra investigation beyond the minimum known-cause checklist. Low-materiality cases stop at the minimum; high-materiality cases run optional corroboration.

## Why this matters
The bench scores efficiency alongside precision/recall. Over-querying low-materiality cases wastes token budget and doesn't improve scoring. Under-querying high-materiality cases risks a missed finding or a false flag. Investigation depth calibrates the balance.

## Procedure

### Step 1 — Determine materiality tier
After the candidate net and initial evidence gathering:

| Tier | Condition | Max additional tool calls |
|---|---|---|
| Low | Impact < $100 OR |tstat| / |z| borderline (3.0–3.5) | 0 additional (minimum only) |
| Medium | $100–$1,000 impact OR |tstat| > 3.5 | 2 additional tool calls |
| High | > $1,000 impact OR multi-duty corroboration possible | 4 additional tool calls |
| Critical | > $5,000 impact OR cross-store pattern | Unlimited within budget |

### Step 2 — Minimum checklist (non-negotiable, all tiers)
These ALWAYS run regardless of tier (GR7):
- All known-cause checks listed for the duty (from skill_known_cause_gate)
- Entity resolution verification (skill_entity_resolution)
- Confidence and evidence sufficiency scoring (skill_confidence_gating)

### Step 3 — Optional additional investigation (medium and above)

For **medium-tier** cases, consider (up to 2 additional queries):
- Query the specific entity's full history for context: "Is this a recent change or long-standing?"
- Check if the same pattern appears at a related store or supplier.

For **high-tier** cases, consider (up to 4 additional queries):
- Run cross-corroboration (post-verdict, per skill_duty_isolation): does another duty show a signal for the same entity?
- Check for recent changes to the entity's operational setup (new manager, new POS system, recent staffing change).
- Query for prior investigation records for this entity.

For **critical-tier** cases: run all optional checks. The dollar amount justifies the tool call cost.

### Step 4 — Document in the evidence trail
```
Investigation depth: MEDIUM ($610 estimated impact)
  Minimum checklist: completed (3 known-cause checks)
  Additional queries (2/2 budget used):
    - str_009 full 90-day history: confirms pattern began 2026-01-27
    - str_003 checked for similar pattern: found (independent finding)
```

### Tool call budget accounting
Track tool calls used per duty. The `max_turns_per_duty` in agent.yaml is the ceiling. Do not approach it on low-materiality cases.

Typical distribution:
- 1 call: candidate SQL (always)
- 1–3 calls: known-cause checks
- 1 call: policy table lookup (if needed)
- 0–4 calls: optional per depth tier
- 1 call: submit action

Total: 4–10 calls for most cases. Low-materiality cases should be 4–5.

## Guardrails enforced
- **GR7**: Efficiency has a floor — never skip the minimum checklist to save tool calls.
- Token efficiency directive: low-materiality cases do not over-query.
