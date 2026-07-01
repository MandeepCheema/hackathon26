---
name: skill_cross_domain_correlation
capability: B4
applies_to: all_duties
build_priority: null
status: NOT_BUILT_PENDING_SCOPE_DECISION
---

# Skill: Cross-Domain Correlation (B4)

**Status: NOT_BUILT_PENDING_SCOPE_DECISION**

The in/out decision for this skill has not been made. See `open_items` in the context layer.

## What this skill would do (if scoped in)
After all duties have independently reached verdicts (B5 complete for all duties), this skill:
1. Groups findings by store_id, staff_id, and time window.
2. Identifies entities that appear in multiple duty findings.
3. Notes the correlation in the evidence trail — for the controller's situational awareness.
4. Does NOT modify any duty's verdict.

## Example output (if built)
```
CROSS-DOMAIN CORRELATION NOTE
str_009 appears in 2 independent duty findings:
  - cash_over_short: pattern_short, -$610 over 14 days (confidence 0.92)
  - loss_prevention: refer_investigation for stf_009_6, z_void = 2.9 (confidence 0.88)
These verdicts were reached independently. This note is for controller context only.
```

## Scope decision criteria
Scope IN if:
- The bench rubric awards points for cross-duty correlation notes.
- The correlation note meaningfully helps the controller prioritize investigations.

Scope OUT if:
- The bench rubric only scores individual duty verdicts, not correlation notes.
- Cross-duty correlation risk of contaminating verdicts (GR3) outweighs the benefit.

## Constraint (always applies regardless of scope decision)
Cross-domain correlation runs AFTER B5 for all duties. It NEVER feeds back into a duty's B2, B3, or verdict. Skill_duty_isolation (GR3) applies unconditionally.
