"""Claude Agent SDK loop for Penny. Registers three tools wired to `client`,
then runs a single-turn agent that investigates and submits verdicts.

Auth: Claude subscription (no ANTHROPIC_API_KEY — caller must unset it).
"""
import asyncio
import json

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


def _build_options(system: str, task: str, client) -> ClaudeAgentOptions:
    @tool(
        "run_sql",
        "Execute a read-only SQL query against McContext finance data.",
        {
            "query": str,
            "purpose": str,
        },
    )
    async def run_sql(args: dict):
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
        result = client.call("submit_loss_flag", args)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    sdk_server = create_sdk_mcp_server(
        name="penny_tools",
        version="1.0.0",
        tools=[run_sql, submit_cash_variance, submit_loss_flag],
    )

    return ClaudeAgentOptions(
        model="claude-opus-4-8",
        system_prompt=system,
        mcp_servers={"penny_tools": sdk_server},
        allowed_tools=["mcp__penny_tools"],
        tools=[],
        setting_sources=[],
    )


async def _run_async(system: str, task: str, client) -> None:
    options = _build_options(system, task, client)
    sdk_client = ClaudeSDKClient(options=options)
    await sdk_client.connect()
    prompt = TASK_PREFIX + task
    await sdk_client.query(prompt)
    async for msg in sdk_client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}({block.input})")
        elif isinstance(msg, ResultMessage):
            break
    await sdk_client.disconnect()


def run_agent(system: str, task: str, client) -> None:
    """Run the Penny agent for one duty (blocking). Mirrors the reference runner pattern."""
    asyncio.run(_run_async(system, task, client))
