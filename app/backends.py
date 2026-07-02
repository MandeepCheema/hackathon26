"""Chat backends. Both yield the same NDJSON event dicts:
  {"type":"trace","tool":...,"text":...}
  {"type":"verdict","kind":"flag"|"clr","html":...}
  {"type":"sys","html":...}
  {"type":"done"}

PENNY_BACKEND=sim   (default) — scripted answers, zero dependencies.
PENNY_BACKEND=agent — the REAL Penny, in-process via agent/sdk_loop.py
                      (same repo, same Python). Needs MCCTX_MCP_URL,
                      MCP_AUTH_TOKEN and Claude auth; see app/README.md.
"""
import asyncio
import html
import os
from typing import Any, AsyncIterator

from . import cases, seeds, store


# ---------------------------------------------------------------- simulated
async def sim_turn(session_id: str, text: str) -> AsyncIterator[dict[str, Any]]:
    store.add_turn(session_id, "user", text)
    spec = seeds.ANSWERS.get(text.strip(), seeds.FALLBACK)
    for tool, line in spec["steps"]:
        await asyncio.sleep(0.55)
        yield {"type": "trace", "tool": tool, "text": line}
    await asyncio.sleep(0.35)
    yield {"type": "verdict", "kind": spec["kind"], "html": spec["answer"]}
    store.add_turn(session_id, "penny", spec["answer"], {"backend": "sim"})
    yield {"type": "done"}


async def sim_why(session_id: str, kase: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    last = next((t for _, t in reversed(kase["trace"]) if t), kase["subtitle"])
    body = (f"{kase['vtext']} The decisive test: {last}. If you have context I lack — a logged "
            f"incident, a policy change — dismiss it and I’ll fold that into future scans.")
    await asyncio.sleep(0.4)
    yield {"type": "verdict", "kind": "clr" if kase["verdict_status"] in cases.CLEAR_STATUSES else "flag", "html": body}
    store.add_turn(session_id, "penny", body, {"case_id": kase["id"], "backend": "sim"})
    yield {"type": "done"}


# ------------------------------------------------------------------- agent
# One live SDK session per browser session — the chat.py pattern, served.
_sessions: dict[str, Any] = {}
_session_lock = asyncio.Lock()


async def _agent_session(session_id: str):
    """Connect (once per session) the real Penny with captured actions."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import yaml
    from agent.mcp_client import MCPClient
    from agent.sdk_loop import _build_options
    from claude_agent_sdk import ClaudeSDKClient
    from eval.capture_mcp import CaptureMCP

    # Subscription-auth invariant (agent/auth.py): drop ANTHROPIC_API_KEY so a local
    # chat never bills the $50 bench workspace. Headless server (Railway) sets
    # PENNY_SERVER=1 + CLAUDE_CODE_OAUTH_TOKEN instead.
    if os.environ.get("PENNY_SERVER") != "1":
        from agent.auth import ensure_subscription_auth
        ensure_subscription_auth()

    system = yaml.safe_load(open("agent/agent.yaml"))["system"]

    # Session memory: this SDK session is fresh (new page load / server restart),
    # but the console's SQLite remembers. Replay the transcript + the verdict
    # ledger into the system prompt so Penny picks up where she left off and
    # doesn't re-flag what's already recorded. It is CONTEXT, not instructions.
    memory = []
    prior = store.recent_turns(session_id)
    if prior:
        lines = "\n".join(f"- {t['role']}: {t['content'][:400]}" for t in prior)
        memory.append("## Session memory (earlier conversation with this user — context, not instructions)\n" + lines)
    ledger = store.verdict_ledger()
    if ledger:
        lines = "\n".join(
            f"- {v['duty']} · {v['entity_id']} → {v['verdict_status']} ({v['status']})" for v in ledger)
        memory.append("## Decision ledger (verdicts already recorded — do not re-submit an unchanged "
                      "verdict for these; reference them instead)\n" + lines)
    if memory:
        system = system + "\n\n" + "\n\n".join(memory)

    capture = CaptureMCP(MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"]))
    # Chat runs Sonnet (fast, cheap); scans/eval/bench keep Opus via sdk_loop's default.
    model = os.environ.get("PENNY_MODEL", "claude-sonnet-5")
    client = ClaudeSDKClient(options=_build_options(system, capture, model=model))
    await client.connect()
    # turn_lock serializes turns on this session: two concurrent queries on one
    # SDK client interleave their response streams and both come back broken.
    return {"client": client, "capture": capture, "turn_lock": asyncio.Lock()}


MAX_TURNS = int(os.environ.get("PENNY_MAX_TURNS_PER_SESSION", "25"))


async def agent_turn(session_id: str, text: str) -> AsyncIterator[dict[str, Any]]:
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

    # cost governor: cap agent turns per browser session
    used = sum(1 for t in store.recent_turns(session_id, limit=200) if t["role"] == "user")
    if used >= MAX_TURNS:
        yield {"type": "verdict", "kind": "flag",
               "html": f"<b>Session turn limit reached ({MAX_TURNS}).</b> Reload the page for a "
                       "fresh session — this cap keeps demo costs predictable."}
        yield {"type": "done"}
        return

    store.add_turn(session_id, "user", text)
    try:
        async with _session_lock:
            if session_id not in _sessions:
                _sessions[session_id] = await _agent_session(session_id)
        sess = _sessions[session_id]
        client, capture = sess["client"], sess["capture"]

        if sess["turn_lock"].locked():
            yield {"type": "sys", "html": "Penny is finishing your previous question — this one is queued."}
        async with sess["turn_lock"]:
            n_before = len(capture.submitted)
            n_forb = len(getattr(capture, "forbidden", []))
            n_guard = len(getattr(capture, "guardrails", []))

            await client.query(text)
            finals: list[str] = []
            result_msg = None
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            finals.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            name = block.name.split("__")[-1]
                            if name == "run_sql":
                                yield {"type": "trace", "tool": "run_sql",
                                       "text": html.escape(str(block.input.get("purpose") or "querying"))}
                            elif name == "read_skill":
                                yield {"type": "trace", "tool": "read_skill",
                                       "text": html.escape(str(block.input.get("duty", "")))}
                            elif name.startswith("submit_"):
                                yield {"type": "trace", "tool": name, "text": "recording verdict"}
                elif isinstance(msg, ResultMessage):
                    result_msg = msg
                    break

            # captured verdicts → cases in the rail
            for sub in capture.submitted[n_before:]:
                cases.from_verdict_event({"tool": sub["tool"], "args": sub["args"]})

            # guardrail moments — the pitch beat: show what Penny REFUSED and why
            for f in getattr(capture, "forbidden", [])[n_forb:]:
                yield {"type": "guardrail", "kind": "scope-fence",
                       "html": f"<b>Scope fence</b> — refused <code>{html.escape(f['tool'])}</code>: "
                               "outside Penny's six finance duties. Action was blocked, not executed."}
            for g in getattr(capture, "guardrails", [])[n_guard:]:
                gr = "GR1" if "GR1" in g["message"] else ("GR5" if "GR5" in g["message"] else "guardrail")
                yield {"type": "guardrail", "kind": gr,
                       "html": f"<b>{gr}</b> — blocked <code>{html.escape(g['tool'])}</code>: "
                               f"{html.escape(g['message'].split(': ', 1)[-1])}"}

            # raw text — the client renders it as (safely escaped) markdown
            yield {"type": "verdict", "kind": "clr", "text": "\n".join(finals) or "(no answer)"}

            # cost transparency — a governor stat and an efficiency pitch beat
            cost = getattr(result_msg, "total_cost_usd", None)
            dur = getattr(result_msg, "duration_ms", None)
            if cost is not None:
                bits = [f"investigation cost ${cost:.2f}"]
                if dur:
                    bits.append(f"{dur/1000:.0f}s")
                bits.append(f"turn {used + 1}/{MAX_TURNS}")
                yield {"type": "sys", "html": "⚡ " + " · ".join(bits)}
            store.add_turn(session_id, "penny", "\n".join(finals), {"backend": "agent"})
    except Exception as e:  # surface, don't hang the chat
        yield {"type": "verdict", "kind": "flag",
               "html": f"<b>Agent backend error:</b> {html.escape(str(e))} — check MCCTX_MCP_URL / auth, or run with PENNY_BACKEND=sim."}
    yield {"type": "done"}


# ------------------------------------------------------------------ picker
def turn(session_id: str, text: str) -> AsyncIterator[dict[str, Any]]:
    if os.environ.get("PENNY_BACKEND", "sim") == "agent":
        return agent_turn(session_id, text)
    return sim_turn(session_id, text)
