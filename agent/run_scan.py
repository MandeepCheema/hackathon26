"""Drive the Penny agent over each duty. `client` exposes run_sql + call(submit_*)."""
import pathlib, yaml

from agent.context.loader import (
    build_mandatory_preamble,
    build_system_prompt_injection,
    build_duty_prompt_block,
)

# Duty IDs in context layer use underscores; SKILL.md dirs use hyphens (v1 only)
_SKILL_DIR_MAP = {
    "cash_over_short": "cash-over-short",
    "loss_prevention": "loss-prevention",
}

# v1 duties (skills live in agent/skills/<hyphen-name>/SKILL.md)
V1_DUTIES = list(_SKILL_DIR_MAP.keys())

# v2+ duties (skills live as flat agent/skills/skill_<id>.md files)
V2_DUTIES = [
    "settlement_reconciliation",
    "three_way_match",
    "duplicate_payment",
    "cogs_leakage",
]


def _skill(duty_id: str) -> str:
    """Load the primary SKILL.md for a duty."""
    if duty_id in _SKILL_DIR_MAP:
        return pathlib.Path(f"agent/skills/{_SKILL_DIR_MAP[duty_id]}/SKILL.md").read_text()
    return pathlib.Path(f"agent/skills/skill_{duty_id}.md").read_text()


def _base_system() -> str:
    return yaml.safe_load(open("agent/agent.yaml"))["system"]


def _full_system(duty_id: str) -> str:
    """Build the complete system prompt for a duty: preamble → base persona → context layer → duty block."""
    base = _base_system()
    parts = [
        build_mandatory_preamble(),
        "",
        base,
        "",
        build_system_prompt_injection(),
        "",
        build_duty_prompt_block(duty_id),
    ]
    return "\n".join(parts)


def scan_all(client, runner=None, duties=None, v1_only=False, v2_only=False):
    """
    Run Penny across selected duties.

    Args:
        client:    MCPClient (or mock) with run_sql / call interface.
        runner:    callable(system, task, client) — defaults to sdk_loop.run_agent.
        duties:    explicit list of duty IDs to run; overrides v1_only/v2_only.
        v1_only:   run only the two v1 duties (cash + loss-prevention).
        v2_only:   run only v2 duties.
    """
    if runner is None:
        from agent.sdk_loop import run_agent
        runner = run_agent

    if duties is not None:
        run_list = duties
    elif v1_only:
        run_list = V1_DUTIES
    elif v2_only:
        run_list = V2_DUTIES
    else:
        run_list = V1_DUTIES + V2_DUTIES

    for duty_id in run_list:
        system = _full_system(duty_id)
        task = _skill(duty_id)
        runner(system, task, client)
