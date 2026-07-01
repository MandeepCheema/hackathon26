---
name: skill_action_commit
capability: B5
applies_to: all_duties
build_priority: null
status: BLOCKED
---

# Skill: Action Commit (B5)

**Status: BLOCKED**

This skill cannot be fully written until skill_tool_discovery has confirmed the live MCP action-tool schema.

## What this skill does (when unblocked)
Maps the verdict from skill_outcome_classification to the exact `submit_*` tool call payload, with correct field names and enum values from the live MCP schema.

## Current state
The tool definitions in `agent/sdk_loop.py` (`_mock_tool_definitions()`) provide the expected schema based on the design docs. These should be verified against the live MCP at bench time:

| Tool | Required fields (per design) |
|------|------------------------------|
| submit_cash_variance | store_id, business_date, status (balanced\|short\|over\|pattern_short), expected_cash_cents, counted_cash_cents, variance_cents, note |
| submit_loss_flag | staff_id, store_id, risk_level (refer_investigation\|monitor\|clear), primary_signal, evidence_note |
| submit_settlement | store_id, business_date, status (reconciled\|shortfall\|over_deposit\|timing_pending), register_card_cents, expected_fee_cents, deposit_cents, missing_cents, note |
| submit_match_exception | po_id, po_line_id, exception_type, amount_cents, note |
| submit_duplicate_payment | supplier_id, invoice_id, duplicate_of_invoice_id, amount_cents, note |
| submit_cogs_variance | store_id, period, status (within_tolerance\|leakage\|favorable), theoretical_cents, actual_cents, variance_pct, note |

## Action before bench
Run skill_tool_discovery. If the live MCP returns different field names or enum values for any submit_* tool, use those exact values — not the ones above. Update this file with the confirmed schema.

## Guardrails enforced (pre-commit checklist)
Before calling ANY submit_* tool:
1. ✅ skill_known_cause_gate completed (GR1)
2. ✅ skill_confidence_gating passed (GR4)
3. ✅ skill_evidence_trail written
4. ✅ Entity confirmed by skill_entity_resolution
5. ✅ Policy cited in note field (GR9)
6. ✅ No accusatory language in note field (GR5)

If any checklist item is not complete: do NOT call submit_*. Route to ABSTAIN or complete the missing item first.
