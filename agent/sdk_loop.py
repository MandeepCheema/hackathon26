"""Claude Agent SDK loop for Penny. Registers tools wired to `client`,
then runs a single-turn agent that investigates and submits verdicts.

Auth: Claude subscription (no ANTHROPIC_API_KEY — caller must unset it).

Guardrail enforcement:
  GR1 — at least one run_sql must precede any submit_* call.
  GR4 — flag verdicts must include confidence_score in the note.
  GR5 — accusatory language about named individuals is blocked in notes.
  GR9 — threshold tools must cite a finpol_* policy ID in the note.
"""
import asyncio
import json
import re
from dataclasses import dataclass, field

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)

TASK_PREFIX = (
    "You are on a scan. Follow this skill exactly, investigate with run_sql, "
    "and submit your verdicts. Skill:\n\n"
)

# Submit tools that are always a "flag" (no status field to check)
_ALWAYS_FLAG_TOOLS = frozenset({"submit_match_exception", "submit_duplicate_payment"})

# Submit tools that require a finpol_* citation (GR9)
_FINPOL_REQUIRED_TOOLS = frozenset(
    {"submit_match_exception", "submit_settlement", "submit_cogs_variance"}
)

# Statuses that are NOT flags (no confidence/policy required)
_CLEARED_STATUSES = frozenset(
    {"clear", "balanced", "reconciled", "no_exception", "cleared"}
)

# GR5 accusatory patterns
_ACCUSATORY = re.compile(
    r"\b(stealing|theft|is stealing|is a thief|fraud(?:ulent(?: activity)?)?|dishonest|corrupt)\b",
    re.IGNORECASE,
)


@dataclass
class _SessionState:
    sql_calls: int = 0
    recent_text: str = ""          # last 4 000 chars of assistant output
    violations: list = field(default_factory=list)

    def record_sql(self):
        self.sql_calls += 1

    def record_text(self, text: str):
        self.recent_text = (self.recent_text + " " + text)[-4000:]


def _note_from(args: dict) -> str:
    return args.get("note", args.get("evidence_note", ""))


def _validate_pre_commit(tool_name: str, args: dict, state: _SessionState):
    """
    Programmatic enforcement of GR1, GR4, GR5, GR9.
    Returns (allowed: bool, violation_message: str | None).
    """
    note = _note_from(args)
    status = args.get("status", args.get("risk_level", "")).lower()

    is_flag = (
        tool_name in _ALWAYS_FLAG_TOOLS
        or (status != "" and status not in _CLEARED_STATUSES)
    )

    # GR1: must have run at least one SQL query
    if state.sql_calls == 0:
        msg = (
            f"GUARDRAIL_VIOLATION GR1: no run_sql call recorded before {tool_name}. "
            "Run the duty SQL query first, then re-submit."
        )
        state.violations.append(msg)
        return False, msg

    # GR4: flag verdicts must include confidence_score
    if is_flag:
        has_conf = "confidence_score" in note or "confidence_score" in state.recent_text
        if not has_conf:
            msg = (
                f"GUARDRAIL_VIOLATION GR4: note for {tool_name} does not contain "
                "'confidence_score: X.XX'. Run skill_confidence_gating and add the score."
            )
            state.violations.append(msg)
            return False, msg

    # GR5: no accusatory language
    if _ACCUSATORY.search(note):
        match = _ACCUSATORY.search(note).group(0)
        msg = (
            f"GUARDRAIL_VIOLATION GR5: accusatory term '{match}' found in note for "
            f"{tool_name}. Describe the pattern, not the person's intent."
        )
        state.violations.append(msg)
        return False, msg

    # GR9: threshold tools must cite a finpol_* policy ID
    if tool_name in _FINPOL_REQUIRED_TOOLS and is_flag:
        if "finpol_" not in note:
            msg = (
                f"GUARDRAIL_VIOLATION GR9: {tool_name} requires a finpol_* policy citation "
                "in the note when applying any threshold. Add the policy ID and retry."
            )
            state.violations.append(msg)
            return False, msg

    return True, None


def _guardrail_error(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}], "isError": True}


def _build_options(system: str, task: str, client) -> tuple[ClaudeAgentOptions, _SessionState]:
    state = _SessionState()

    @tool(
        "run_sql",
        "Execute a read-only SQL query against McContext finance data.",
        {"query": str, "purpose": str},
    )
    async def run_sql(args: dict):
        state.record_sql()
        result = client.run_sql(args["query"], args.get("purpose", ""))
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "submit_cash_variance",
        "Submit a cash-over/short verdict for a store.",
        {
            "store_id": str,
            "business_date": str,
            "status": str,
            "expected_cash_cents": int,
            "counted_cash_cents": int,
            "variance_cents": int,
            "note": str,
        },
    )
    async def submit_cash_variance(args: dict):
        ok, msg = _validate_pre_commit("submit_cash_variance", args, state)
        if not ok:
            return _guardrail_error(msg)
        result = client.call("submit_cash_variance", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "submit_loss_flag",
        "Submit a loss-prevention verdict for a staffer.",
        {
            "staff_id": str,
            "store_id": str,
            "risk_level": str,
            "primary_signal": str,
            "evidence_note": str,
        },
    )
    async def submit_loss_flag(args: dict):
        ok, msg = _validate_pre_commit("submit_loss_flag", args, state)
        if not ok:
            return _guardrail_error(msg)
        result = client.call("submit_loss_flag", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "submit_settlement",
        "Submit a settlement reconciliation verdict.",
        {
            "store_id": str,
            "settlement_date": str,
            "status": str,
            "expected_cents": int,
            "actual_cents": int,
            "gap_cents": int,
            "note": str,
        },
    )
    async def submit_settlement(args: dict):
        ok, msg = _validate_pre_commit("submit_settlement", args, state)
        if not ok:
            return _guardrail_error(msg)
        result = client.call("submit_settlement", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "submit_match_exception",
        "Submit a three-way match exception.",
        {
            "po_id": str,
            "invoice_id": str,
            "exception_type": str,
            "amount_cents": int,
            "note": str,
        },
    )
    async def submit_match_exception(args: dict):
        ok, msg = _validate_pre_commit("submit_match_exception", args, state)
        if not ok:
            return _guardrail_error(msg)
        result = client.call("submit_match_exception", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "submit_duplicate_payment",
        "Submit a duplicate payment flag.",
        {
            "invoice_id_a": str,
            "invoice_id_b": str,
            "vendor_id": str,
            "amount_cents": int,
            "note": str,
        },
    )
    async def submit_duplicate_payment(args: dict):
        ok, msg = _validate_pre_commit("submit_duplicate_payment", args, state)
        if not ok:
            return _guardrail_error(msg)
        result = client.call("submit_duplicate_payment", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "submit_cogs_variance",
        "Submit a COGS leakage verdict.",
        {
            "store_id": str,
            "period": str,
            "status": str,
            "theoretical_cogs_cents": int,
            "actual_cogs_cents": int,
            "variance_cents": int,
            "note": str,
        },
    )
    async def submit_cogs_variance(args: dict):
        ok, msg = _validate_pre_commit("submit_cogs_variance", args, state)
        if not ok:
            return _guardrail_error(msg)
        result = client.call("submit_cogs_variance", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    sdk_server = create_sdk_mcp_server(
        name="penny_tools",
        version="1.0.0",
        tools=[
            run_sql,
            submit_cash_variance,
            submit_loss_flag,
            submit_settlement,
            submit_match_exception,
            submit_duplicate_payment,
            submit_cogs_variance,
        ],
    )

    options = ClaudeAgentOptions(
        model="claude-opus-4-8",
        system_prompt=system,
        mcp_servers={"penny_tools": sdk_server},
        allowed_tools=["mcp__penny_tools"],
        tools=[],
        setting_sources=[],
    )
    return options, state


async def _run_async(system: str, task: str, client) -> None:
    options, state = _build_options(system, task, client)
    sdk_client = ClaudeSDKClient(options=options)
    await sdk_client.connect()
    prompt = TASK_PREFIX + task
    await sdk_client.query(prompt)
    async for msg in sdk_client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    state.record_text(block.text)
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}({block.input})")
        elif isinstance(msg, ResultMessage):
            break
    if state.violations:
        print(f"\n[penny] {len(state.violations)} guardrail violation(s) this run:")
        for v in state.violations:
            print(f"  {v}")
    await sdk_client.disconnect()


def run_agent(system: str, task: str, client) -> None:
    """Run the Penny agent for one duty (blocking). Mirrors the reference runner pattern."""
    from agent.auth import ensure_subscription_auth
    ensure_subscription_auth()
    asyncio.run(_run_async(system, task, client))
