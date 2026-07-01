---
name: skill_outcome_classification
capability: B3
applies_to: all_duties
build_priority: 5
status: ready
---

# Skill: Outcome Classification (B3)

**One-line purpose:** Routes every investigated case to exactly one of FLAG / CLEAR / ABSTAIN. Never silent. Never fabricated. One outcome, always explicit.

## The three outcomes

**FLAG** — Submit the positive finding status (pattern_short, refer_investigation, shortfall, exception, duplicate, leakage).
- Requires: known-cause gate passed (UNCOVERED) + confidence gate passed
- Action: call the duty's `submit_*` tool with the finding status

**CLEAR** — Submit the cleared/balanced/within_tolerance status.
- Requires: known-cause gate found a matching cause (CLEARED), OR statistical test shows within-tolerance
- Action: call the duty's `submit_*` tool with the cleared status
- Do NOT stay silent. Cleared decoys are scored.

**ABSTAIN** — Record that the case cannot be decided and name exactly what is missing.
- Requires: confidence gate failed, OR evidence sufficiency gate failed, OR required data unavailable
- Action: do NOT call submit_*. Instead record the abstention in your evidence trail and note the specific gap.
- GR2: An uncertain case is ABSTAINED, not CLEARED. Fabricating a clearance to fill a gap violates GR2.

## Decision tree

```
After B2 evidence gathering and B3 known-cause gate:
│
├── Known cause found?
│   ├── YES → CLEAR (submit cleared status, cite the cause)
│   └── NO → continue
│
├── Evidence sufficiency score ≥ 0.7?
│   ├── NO → ABSTAIN (name the missing data)
│   └── YES → continue
│
├── Confidence score ≥ 0.7?
│   ├── NO → ABSTAIN (name the ambiguity)
│   └── YES → continue
│
└── Anomaly confirmed (tstat ≤ -3, z ≥ 2.5, gap > $0, etc.)?
    ├── YES → FLAG (submit finding status)
    └── NO → CLEAR (submit balanced/within_tolerance)
```

## Per-duty outcome mapping

| Duty | FLAG status | CLEAR status | Abstain: do NOT call submit |
|------|------------|--------------|---|
| cash_over_short | pattern_short | balanced | (abstain, no submit) |
| loss_prevention | refer_investigation | clear | (abstain, no submit) |
| settlement_reconciliation | shortfall | reconciled | (abstain, no submit) |
| three_way_match | any exception_type | (silence = within tolerance) | (abstain, no submit) |
| duplicate_payment | (submit duplicate) | (silence = no dup) | (abstain, no submit) |
| cogs_leakage | leakage | within_tolerance | (abstain, no submit) |

Note: three_way_match and duplicate_payment do NOT have a positive "cleared" submit — silence is correct for those when no exception is found. For the other four duties, submit the cleared status explicitly.

## Procedure

### Step 1 — Gather all inputs
- Known-cause gate result: CLEARED(cause) | UNCOVERED | ABSTAIN(missing)
- Confidence score + evidence sufficiency score from skill_confidence_gating
- Statistical test result (tstat, z-score, gap amount)

### Step 2 — Apply decision tree
Follow the tree above. One and only one outcome.

### Step 3 — Compose the verdict
Use the structure from skill_evidence_trail:
```
VERDICT: [FLAG|CLEAR|ABSTAIN]
OUTCOME_STATUS: [exact status value to submit]
ENTITY: [store_id / staff_id / po_id / etc.]
```

### Step 4 — Hand off to skill_evidence_trail and skill_structured_writeup
Before calling submit_*, write the full evidence trail. The writeup is the record.

## Guardrails enforced
- **GR1**: No FLAG without completed known-cause check.
- **GR2**: No fabricated CLEAR — uncertain = ABSTAIN.
- **GR4**: No submit_* call without confidence gate passed.
