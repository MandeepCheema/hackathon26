import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# App tests must never start background tasks, hit the world DB, or call an LLM.
os.environ.setdefault("SIMULATOR", "0")
os.environ.setdefault("FEED", "sim")
os.environ.setdefault("PENNY_BACKEND", "sim")

import pytest


@pytest.fixture()
def app_db(tmp_path, monkeypatch):
    """Fresh SQLite per test — resets the app.store module-level connection."""
    from app import store
    monkeypatch.setattr(store, "_DB_PATH", str(tmp_path / "test.db"))
    store._conn = None
    yield store
    if store._conn is not None:
        store._conn.close()
        store._conn = None
