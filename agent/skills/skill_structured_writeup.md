---
name: skill_structured_writeup
capability: B5
applies_to: all_duties
build_priority: 5
status: ready
---

# Skill: Structured Writeup (B5)

**One-line purpose:** Renders the evidence-trail object into a human-facing write-up for the controller, in a fixed order with consistent voice across all 6 duties.

## Fixed output order (mandatory — do not reorder)

1. **Verdict** — one line: `[STATUS]: [entity] — [dollar impact]`
2. **Evidence trail** — the full evidence trail object from skill_evidence_trail
3. **Checks performed including cleared** — explicit list of what was investigated and dismissed
4. **Confidence score** — numeric scores + gate result
5. **Dollar / operational impact** — estimated amount at risk or recovered

## Format templates

### FLAG writeup
```
FLAG — pattern_short: str_009 — estimated $610 short over 14 days

EVIDENCE
  Period: 2026-02-01 → 2026-02-14 (14 store-days)
  net_cents: -61,000  |  avg_var_cents: -4,357  |  tstat: -3.80
  Source: fin_register_totals + fin_cash_counts, 14 rows each.

CHECKS PERFORMED
  ✓ float_change_log — no float-change entries for str_009 in window (0 rows, fin_paid_outs)
  ✓ manager_correction_log — no correction entries (0 rows, fin_paid_outs)
  ✓ same_cashier_shift — stf_009_6 worked 11 of 14 variance days (fin_register_txns)
  Note: loss_prevention verdict for stf_009_6 is an independent finding (skill_duty_isolation applies).

CONFIDENCE
  confidence_score: 0.92  |  evidence_sufficiency_score: 1.00  |  gate: passed

DOLLAR IMPACT
  Estimated short: $610.00 over 14 days ($43.57/day average)
```

### CLEAR writeup
```
CLEAR — balanced: str_002 — within normal variance

EVIDENCE
  Period: 2026-01-01 → 2026-01-31 (31 store-days)
  net_cents: +1,200  |  avg_var_cents: +39  |  tstat: +0.82
  Source: fin_register_totals + fin_cash_counts, 31 rows each.

CHECKS PERFORMED
  Not required (|tstat| = 0.82 < 3.0 — within-noise threshold)

CONFIDENCE
  confidence_score: 1.00  |  evidence_sufficiency_score: 1.00  |  gate: passed

DOLLAR IMPACT
  None — variance is within expected statistical noise range.
```

### ABSTAIN writeup
```
ABSTAIN — cash_over_short: str_007 — cannot reach verdict

REASON
  Cannot complete known-cause check 'manager_correction_log':
  world.fin_manager_corrections not present in live schema (confirmed via skill_tool_discovery).
  Without this table, the known-cause gate is incomplete (GR1 requires all checks before flagging).
  The tstat is -3.2 (borderline above threshold), which makes the missing check material.

CHECKS PERFORMED
  ✓ float_change_log — no entries (0 rows, fin_paid_outs)
  ⚠ manager_correction_log — NOT RUN (table absent from schema)

CONFIDENCE
  confidence_score: 0.60  |  evidence_sufficiency_score: 0.55  |  gate: failed

RECOMMENDATION
  Provide access to manager correction records for str_007 and re-run this duty.
```

## Tone rules
- Lead with the verdict, not the journey.
- "str_009 is short $610 over 14 days (t = -3.8)" not "After running various queries, it appears that..."
- Numbers over adjectives at all times.
- Consistent voice across all 6 duties — a controller should recognize Penny's format regardless of duty.
- No hedging theater. Replace "it's possible that..." with a confidence score.

## Length discipline
- Simple clear (|tstat| well below threshold, 1 entity): 3–5 lines
- Moderate case (threshold borderline, multiple checks): 10–15 lines
- Complex flag (multi-week pattern, corroborating evidence): up to 25 lines
- Do not pad a thin case to appear thorough. Padding is penalized.

## Guardrails enforced
- **GR5**: Non-accusatory language. Never name an individual as a suspect — describe the pattern.
- Response guidelines: fixed order, factual tone, length scales with complexity.
