---
name: skill_confidence_gating
capability: B3
applies_to: all_duties
build_priority: 5
status: ready
---

# Skill: Confidence Gating (B3)

**One-line purpose:** Requires BOTH a confidence score AND an evidence sufficiency score to meet threshold before any verdict commits. Failing either score routes to ABSTAIN, not flag.

This is a **new capability** not in the original agent design. The original design had a single "confidence gate" — this skill separates two orthogonal dimensions that both must pass.

## The two dimensions

**Confidence score** (0.0–1.0): How certain are you that the classification is correct given the evidence you have?
- 1.0 = the math unambiguously points to one outcome
- 0.7 = the evidence is consistent with the outcome but has noise
- 0.5 = genuinely uncertain between two outcomes
- < 0.5 = evidence is ambiguous or contradictory

**Evidence sufficiency score** (0.0–1.0): Have you gathered enough evidence to reach a verdict — independent of which verdict it is?
- 1.0 = all required known-cause checks run, all source tables queried, no missing data
- 0.7 = minor gaps (one optional check not runnable) but core evidence is solid
- 0.5 = key evidence missing but case can be partially assessed
- < 0.5 = insufficient data to reach any verdict

**Critical distinction:** You can have high confidence in a wrong conclusion (confident but undersupported). Both scores must pass.

## Procedure

### Step 1 — Score confidence
After completing known-cause checks and evidence gathering, score your confidence:
- Start at 1.0
- Deduct 0.2 for each: ambiguous pattern, conflicting data points, only one data source corroborates
- Deduct 0.3 for: evidence contradicts itself, alternative explanation not ruled out, t-stat/z-score borderline
- Floor: 0.0

### Step 2 — Score evidence sufficiency
- Start at 1.0
- Deduct 0.1 for each: optional check not run (table missing)
- Deduct 0.2 for each: required known-cause check not run (table missing)
- Deduct 0.3 for: fewer than minimum data points (< 7 days for cash, < 20 transactions for loss)
- Floor: 0.0

### Step 3 — Apply the gate

| Confidence | Evidence Sufficiency | Outcome |
|---|---|---|
| ≥ 0.7 | ≥ 0.7 | ✅ Proceed to outcome_classification |
| ≥ 0.7 | < 0.7 | ⛔ Route to ABSTAIN: "Sufficient confidence but insufficient evidence. Missing: [specific data]." |
| < 0.7 | ≥ 0.7 | ⛔ Route to ABSTAIN: "Evidence gathered but verdict uncertain. Ambiguity: [specific reason]." |
| < 0.7 | < 0.7 | ⛔ Route to ABSTAIN: "Both confidence and evidence insufficient. [details]." |

Thresholds (0.7 / 0.7) are starting defaults. They are tunable via the escalation config in agent.yaml.

### Step 4 — Model escalation check
If confidence is 0.5–0.7 AND dollar impact > $500 (50,000 cents):
→ Do not silently apply 0.7 threshold. Note the borderline case.
→ The escalation_config in agent.yaml may trigger a more capable model for this turn.

### Step 5 — Record scores in the evidence trail
Every verdict must include:
```
confidence_score: 0.85
evidence_sufficiency_score: 1.00
gate: passed
```
Or:
```
confidence_score: 0.65
evidence_sufficiency_score: 0.90
gate: failed — confidence below 0.7; routed to abstain
abstain_reason: "t-stat of -2.8 is below the -3.0 threshold; pattern borderline"
```

## Guardrails enforced
- **GR4**: No action-tool call without a completed confidence gate.
- **GR2**: An uncertain case is ABSTAINED, never marked clear to fill a gap.
