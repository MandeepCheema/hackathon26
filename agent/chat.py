"""Local conversational REPL for Penny — the same agent the bench talks to.

Multi-turn: one SDK session, context carries across turns. run_sql hits the live
world (read-only); every action is captured by CaptureMCP, never sent — captured
submits print after each turn so you can see exactly what the bench would grade.

Usage:  set -a && . ./.env && set +a && python -m agent.chat
"""
import asyncio
import os

import yaml


async def _repl():
    from agent.mcp_client import MCPClient
    from agent.sdk_loop import _build_options, _drive
    from claude_agent_sdk import ClaudeSDKClient
    from eval.capture_mcp import CaptureMCP

    system = yaml.safe_load(open("agent/agent.yaml"))["system"]
    capture = CaptureMCP(MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"]))
    sdk_client = ClaudeSDKClient(options=_build_options(system, capture))
    await sdk_client.connect()
    print("Penny (local, captured) — ask anything; Ctrl-D to exit.\n")
    try:
        while True:
            try:
                msg = input("you> ").strip()
            except EOFError:
                break
            if not msg:
                continue
            n_before = len(capture.submitted)
            await _drive(sdk_client, msg, echo=True)
            for s in capture.submitted[n_before:]:
                print(f"[captured] {s['tool']}({s['args']})")
            if capture.forbidden:
                print(f"[SCOPE-FENCE VIOLATION] {capture.forbidden}")
    finally:
        await sdk_client.disconnect()


def main():
    from agent.auth import ensure_subscription_auth
    ensure_subscription_auth()
    asyncio.run(_repl())


if __name__ == "__main__":
    main()
