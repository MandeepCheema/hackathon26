"""
agent/context/loader.py

Loads penny_context_layer.json once at session start and provides
runtime access to guardrails, duty configs, skill lazy-loading,
and the trusted-tables cache populated by skill_tool_discovery.

Token efficiency rule: this module is the always-loaded routing layer.
Skill .md files are loaded lazily — only the skills for the current duty,
only when that duty runs. Never preload the full skill library.
"""

from __future__ import annotations

import json
import pathlib
from typing import Optional

_HERE = pathlib.Path(__file__).parent
_CTX_PATH = _HERE / "penny_context_layer.json"
_SKILLS_DIR = _HERE.parent / "skills"

# Module-level singletons (populated on first access)
_ctx: Optional[dict] = None
_trusted_tables_cache: dict[str, dict] = {}
_skill_text_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load() -> dict:
    """Load and cache the full context layer JSON."""
    global _ctx
    if _ctx is None:
        with open(_CTX_PATH) as f:
            _ctx = json.load(f)["context_layer"]
    return _ctx


# ---------------------------------------------------------------------------
# Guardrails & norms
# ---------------------------------------------------------------------------

def get_guardrails() -> str:
    """Return all 10 guardrails as a formatted system-prompt block."""
    ctx = _load()
    lines = ["## GUARDRAILS (all are mandatory; on-violation routing is listed)\n"]
    for gr in ctx["norms"]["guardrails"]:
        eb = gr.get("enforced_by", [])
        enforced_by = eb if isinstance(eb, str) else ", ".join(eb)
        pd = gr.get("protects_judging_dimension", [])
        dims = pd if isinstance(pd, str) else ", ".join(pd)
        lines.append(f"**{gr['id']}**: {gr['rule']}")
        lines.append(f"  → On violation: {gr['on_violation']}")
        lines.append(f"  → Enforced by: {enforced_by}")
        lines.append(f"  → Protects: {dims}\n")
    return "\n".join(lines)


def get_anti_hallucination_directives() -> str:
    ctx = _load()
    items = ctx["norms"]["anti_hallucination_directives"]
    lines = ["## ANTI-HALLUCINATION DIRECTIVES (hard rules; no exceptions)\n"]
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def get_token_efficiency_directives() -> str:
    ctx = _load()
    items = ctx["norms"]["token_efficiency_directives"]
    lines = ["## TOKEN EFFICIENCY RULES\n"]
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def get_response_guidelines() -> str:
    ctx = _load()
    rg = ctx["norms"]["response_guidelines"]
    order = " → ".join(rg["fixed_order"])
    lines = [
        "## RESPONSE GUIDELINES\n",
        f"Fixed output order: {order}",
        f"Tone: {rg['tone']}",
        f"Length: {rg['length_discipline']}",
        f"Abstain requirements: {rg['abstain_requirements']}",
    ]
    return "\n".join(lines)


def get_communication_style() -> str:
    ctx = _load()
    cs = ctx["norms"]["communication_style"]
    lines = [f"## COMMUNICATION STYLE\nAudience: {cs['audience']}\n"]
    for rule in cs["rules"]:
        lines.append(f"- {rule}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Capability flow & workflow shapes
# ---------------------------------------------------------------------------

def get_incident_basis() -> str:
    """Returns the real-world incident basis block — calibrates judgment on borderline cases."""
    ctx = _load()
    basis = ctx["knowledge"].get("incident_basis", {})
    if not basis:
        return ""
    lines = [
        "## INCIDENT BASIS — Real patterns this agent is designed to catch\n",
        basis.get("note", ""),
        "",
    ]
    for duty, desc in basis.get("incidents", {}).items():
        lines.append(f"**{duty}**: {desc}")
    return "\n".join(lines)


def get_escalation_routing() -> str:
    """Returns the per-duty escalation routing table."""
    ctx = _load()
    routing = ctx["norms"]["policy_layer"].get("escalation_routing", {})
    if not routing:
        return ""
    lines = ["## ESCALATION ROUTING (include reviewer role in every flag note)\n"]
    for duty, reviewer in routing.get("routes", {}).items():
        lines.append(f"- **{duty}**: {reviewer}")
    lines.append(f"\n{routing.get('conflict_of_interest_rule', '')}")
    return "\n".join(lines)


def get_capability_flow() -> str:
    """Return the B1→B2→B3→B5 capability flow stages as a formatted block."""
    ctx = _load()
    stages = ctx["knowledge"]["ontology"]["capability_flow_stages"]
    lines = ["## CAPABILITY FLOW (follow this order for every duty)\n"]
    for stage in stages:
        nxt = stage.get("next")
        if isinstance(nxt, list):
            nxt = " | ".join(nxt)
        elif nxt is None:
            nxt = "(terminal — runs after all duty verdicts)"
        status = f"  [{stage['status']}]" if "status" in stage else ""
        runs = f"  ({stage['runs']})" if "runs" in stage else ""
        lines.append(f"- **{stage['stage']}** → {nxt}{status}{runs}")
    return "\n".join(lines)


def get_workflow_shape_description(duty_id: str) -> str:
    ctx = _load()
    duty = get_duty_config(duty_id)
    shape_id = duty["workflow_shape"]
    shape = ctx["knowledge"]["ontology"]["workflow_shapes"][shape_id]
    return (
        f"Workflow shape: **{shape_id}**\n"
        f"Duties using this shape: {', '.join(shape['duties'])}\n"
        f"Loop pattern: {shape['loop']}"
    )


# ---------------------------------------------------------------------------
# Duty config
# ---------------------------------------------------------------------------

def get_duty_config(duty_id: str) -> dict:
    """Return full duty config: workflow_shape, skills_used, known_cause_checks, metrics_used."""
    ctx = _load()
    for duty in ctx["duties"]:
        if duty["id"] == duty_id:
            return duty
    raise KeyError(f"Duty '{duty_id}' not found in context layer")


def get_all_duties() -> list[dict]:
    return _load()["duties"]


def get_duty_ids() -> list[str]:
    return [d["id"] for d in get_all_duties()]


def get_known_cause_checks(duty_id: str) -> list[str]:
    return get_duty_config(duty_id).get("known_cause_checks", [])


def get_metrics_for_duty(duty_id: str) -> list[dict]:
    ctx = _load()
    duty_metrics = []
    for m in ctx["knowledge"]["metrics"]["business_metrics"]:
        if m.get("duty") == duty_id:
            duty_metrics.append(m)
    return duty_metrics


# ---------------------------------------------------------------------------
# Skill lazy-loading
# ---------------------------------------------------------------------------

def get_skill_metadata(skill_id: str) -> dict:
    ctx = _load()
    for skill in ctx["expertise"]["skills"]:
        if skill["id"] == skill_id:
            return skill
    raise KeyError(f"Skill '{skill_id}' not found in context layer")


def get_skill_text(skill_id: str) -> str:
    """
    Lazy-load a skill .md file. Cached after first load.
    Returns a stub message for BLOCKED or NOT_BUILT skills.
    """
    if skill_id in _skill_text_cache:
        return _skill_text_cache[skill_id]

    try:
        skill_meta = get_skill_metadata(skill_id)
    except KeyError:
        return f"# {skill_id}\nSkill not found in context layer."

    status = skill_meta.get("status", "")
    if status in ("BLOCKED", "NOT_BUILT_PENDING_SCOPE_DECISION"):
        return (
            f"# {skill_id}\n"
            f"Status: {status}\n"
            f"Reason: {skill_meta.get('one_line', 'See open_items in context layer.')}\n"
            "Do not invoke this skill. Note the status in your evidence trail."
        )

    skill_file = skill_meta.get("file")
    if not skill_file:
        return f"# {skill_id}\nNo file path defined. Status: {status}"

    skill_path = _HERE.parent / skill_file
    if not skill_path.exists():
        return (
            f"# {skill_id}\n"
            f"Skill file not found at {skill_path}.\n"
            "Surface this as a silent-failure per GR6 and route to abstain."
        )

    text = skill_path.read_text()
    _skill_text_cache[skill_id] = text
    return text


def get_skills_for_duty(duty_id: str) -> list[str]:
    """Return skill texts for all skills used by a duty (lazy-loaded)."""
    duty = get_duty_config(duty_id)
    return [get_skill_text(sid) for sid in duty.get("skills_used", [])]


# ---------------------------------------------------------------------------
# Trusted-tables cache (populated by skill_tool_discovery at runtime)
# ---------------------------------------------------------------------------

def set_trusted_tables(
    duty_id: str,
    tables: list[str],
    join_keys: dict | None = None,
    known_cause_sources: list[str] | None = None,
) -> None:
    """
    Called by skill_tool_discovery after enumerating the live MCP schema.
    Persists per-duty trusted table lists for the remainder of the session.
    """
    _trusted_tables_cache[duty_id] = {
        "trusted_tables": tables,
        "join_keys": join_keys or {},
        "known_cause_sources": known_cause_sources or [],
    }


def get_trusted_tables(duty_id: str) -> dict:
    """Return cached trusted tables for a duty. Empty dict if not yet discovered."""
    return _trusted_tables_cache.get(
        duty_id,
        {"trusted_tables": None, "join_keys": None, "known_cause_sources": None},
    )


def is_table_trusted(duty_id: str, table_name: str) -> bool:
    """Returns False (not trusted) if discovery has not run yet — forces GR6 compliance."""
    entry = get_trusted_tables(duty_id)
    tables = entry.get("trusted_tables")
    if tables is None:
        return False  # discovery not run — treat as untrusted
    return table_name in tables


# ---------------------------------------------------------------------------
# Mandatory preamble (goes FIRST in every system prompt — before the persona)
# ---------------------------------------------------------------------------

def build_mandatory_preamble() -> str:
    """
    Short, unmissable block placed at the very top of every system prompt.
    Tells the agent explicitly which guardrails are programmatically enforced
    at the tool-call level (not just instructions). This prevents the model
    from reasoning its way past them.
    """
    return """\
╔══════════════════════════════════════════════════════════════════════╗
║  PENNY RUNTIME GUARDRAIL ENFORCEMENT — READ BEFORE ANY TOOL CALL    ║
╚══════════════════════════════════════════════════════════════════════╝

The following rules are checked IN CODE before every submit_* call.
Violations return a GUARDRAIL_VIOLATION error instead of executing.
You must fix the violation and retry. There is no bypass.

  GR1 [enforced]: You MUST call run_sql at least once before any submit_*.
       No evidence gathered → submit blocked.

  GR4 [enforced]: Your note field MUST contain "confidence_score: X.XX"
       for any flag verdict (non-clear, non-balanced, non-reconciled status).
       Run skill_confidence_gating. No confidence score → submit blocked.

  GR5 [enforced]: Your note MUST NOT contain accusatory language about named
       individuals: "stealing", "theft", "is stealing", "is a thief", "fraud",
       "fraudulent activity", "dishonest", "corrupt".
       Describe the pattern; never characterize intent. Violation → blocked.

  GR9 [enforced]: For settlement, three-way match, and COGS duties, your note
       MUST cite a finpol_* policy ID when applying any threshold.
       No policy citation on a flag → submit blocked.

All other guardrails (GR2, GR3, GR6, GR7, GR8, GR10) are in the context
layer below and are enforced as model instructions (not code checks).

Policy layer: ALL threshold values come from world.fin_policy. Never invent
a number. If a threshold is not configured, surface it and route to ABSTAIN.
══════════════════════════════════════════════════════════════════════════"""


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt_injection() -> str:
    """
    Build the context layer injection block added to the system prompt at agent startup.
    Contains: guardrails, anti-hallucination directives, token efficiency rules,
    response guidelines, communication style, and capability flow.

    This is loaded ONCE per session (not per duty). Duty-specific skill texts
    are added per duty in run_scan.py via get_skills_for_duty().
    """
    ctx = _load()
    meta = ctx["meta"]

    parts = [
        "---",
        f"# PENNY CONTEXT LAYER v{meta['context_layer_version']}",
        f"# Design principle: {meta['design_principle']}",
        "",
        get_guardrails(),
        "",
        get_escalation_routing(),
        "",
        get_incident_basis(),
        "",
        get_anti_hallucination_directives(),
        "",
        get_token_efficiency_directives(),
        "",
        get_response_guidelines(),
        "",
        get_communication_style(),
        "",
        get_capability_flow(),
        "---",
    ]
    return "\n".join(parts)


def build_duty_prompt_block(duty_id: str) -> str:
    """
    Build the duty-specific prompt block injected when that duty runs.
    Includes: workflow shape, known-cause checks, metrics, and all skill texts.
    """
    duty = get_duty_config(duty_id)

    skill_blocks = []
    for skill_id in duty.get("skills_used", []):
        skill_text = get_skill_text(skill_id)
        skill_blocks.append(f"\n### SKILL PLAYBOOK: {skill_id}\n{skill_text}")

    metrics_lines = [
        f"- **{m['id']}**: {m['definition']}"
        + (f" (value: {m['value']})" if m.get("value") else "")
        + (f" ← *{m.get('value_type', '')}*" if m.get("value_type") else "")
        for m in get_metrics_for_duty(duty_id)
    ]

    known_cause_lines = [f"- {c}" for c in duty.get("known_cause_checks", [])]

    guardrail_emphasis = duty.get("special_guardrail_emphasis", [])
    emphasis_note = (
        f"\nSpecial guardrail emphasis for this duty: {', '.join(guardrail_emphasis)}"
        if guardrail_emphasis
        else ""
    )

    parts = [
        f"## DUTY: {duty_id.upper().replace('_', ' ')}",
        f"Cadence: {duty.get('cadence', 'unspecified')}",
        get_workflow_shape_description(duty_id),
        emphasis_note,
        "",
        "### METRICS FOR THIS DUTY",
        "\n".join(metrics_lines) if metrics_lines else "— none defined —",
        "",
        "### KNOWN-CAUSE CHECKS (run ALL before any flag; GR1)",
        "\n".join(known_cause_lines) if known_cause_lines else "— none defined —",
        "",
        *skill_blocks,
    ]
    return "\n".join(parts)
