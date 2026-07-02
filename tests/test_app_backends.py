"""app.backends — sim event contract + the agent turn cap (no LLM, no network)."""
import asyncio

import pytest

from app import backends, seeds


async def _collect(agen):
    return [ev async for ev in agen]


def test_sim_turn_event_contract(app_db, monkeypatch):
    async def instant(_):  # collapse the demo pacing
        return None
    monkeypatch.setattr(backends.asyncio, "sleep", instant)

    q = next(iter(seeds.ANSWERS))
    events = asyncio.run(_collect(backends.sim_turn("s1", q)))
    kinds = [e["type"] for e in events]
    assert kinds[-1] == "done"
    assert "verdict" in kinds and kinds.index("verdict") == len(kinds) - 2
    assert all(k in ("trace", "verdict", "done") for k in kinds)
    # both turns persisted
    assert [t["role"] for t in app_db.recent_turns("s1")] == ["user", "penny"]


def test_sim_fallback_for_unknown_question(app_db, monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr(backends.asyncio, "sleep", instant)
    events = asyncio.run(_collect(backends.sim_turn("s1", "something unscripted")))
    verdict = next(e for e in events if e["type"] == "verdict")
    assert "Simulated backend" in verdict["html"]


def test_agent_turn_cap_blocks_before_any_llm_work(app_db, monkeypatch):
    monkeypatch.setattr(backends, "MAX_TURNS", 2)
    for i in range(2):
        app_db.add_turn("s9", "user", f"q{i}")

    events = asyncio.run(_collect(backends.agent_turn("s9", "one more?")))
    kinds = [e["type"] for e in events]
    assert kinds == ["verdict", "done"]
    assert "turn limit" in events[0]["html"].lower()
    # the over-cap question was NOT recorded (no llm call, no turn row)
    assert len([t for t in app_db.recent_turns("s9") if t["role"] == "user"]) == 2


def test_backend_picker(monkeypatch):
    monkeypatch.setenv("PENNY_BACKEND", "sim")
    gen = backends.turn("s1", "hi")
    assert gen.__name__ == "sim_turn"
