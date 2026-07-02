"""app.main HTTP surface — TestClient, sim backend, no background tasks
(conftest sets SIMULATOR=0 / FEED=sim / PENNY_BACKEND=sim before import)."""
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(app_db, monkeypatch):
    import app.backends as backends
    async def instant(_):
        return None
    monkeypatch.setattr(backends.asyncio, "sleep", instant)   # no demo pacing in tests
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_healthz_shape(client):
    h = client.get("/healthz").json()
    assert h["ok"] is True and h["backend"] == "sim" and h["feed"] == "sim"
    assert "agent_ready" in h


def test_turn_streams_ndjson_sim(client):
    with client.stream("POST", "/turn", json={"session_id": "t1", "text": "hello"}) as r:
        assert r.status_code == 200
        events = [json.loads(l) for l in r.iter_lines() if l]
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "verdict" for e in events)


def test_turn_requires_text(client):
    assert client.post("/turn", json={"session_id": "t1"}).status_code == 400


def test_case_processing_flow(client, app_db):
    from app import cases, seeds
    seed = next(s for s in seeds.CASES if s["verdict"] == "flag")
    k = cases.from_seed(seed, lap=99)

    opened = client.post(f"/cases/{k['id']}/open")
    assert opened.status_code == 200 and opened.json()["status"] == "open"

    confirmed = client.post(f"/cases/{k['id']}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "routed"

    assert client.post(f"/cases/{k['id']}/confirm").status_code == 409   # double-processing
    assert client.post(f"/cases/{k['id']}/dismiss").status_code == 409

    assert client.post("/cases/999999/open").status_code == 404


def test_why_uses_sim_backend(client, app_db):
    from app import cases, seeds
    seed = next(s for s in seeds.CASES if s["verdict"] == "flag")
    k = cases.from_seed(seed, lap=98)
    with client.stream("POST", f"/cases/{k['id']}/why", json={"session_id": "t1"}) as r:
        events = [json.loads(l) for l in r.iter_lines() if l]
    assert events[-1]["type"] == "done" and events[0]["type"] == "verdict"


def test_index_serves_console(client):
    r = client.get("/")
    assert r.status_code == 200 and "Penny" in r.text
