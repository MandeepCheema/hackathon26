"""SQLite persistence: cases, turns, stats. Std-lib only, thread-safe enough
for one uvicorn worker (Railway default). Swap for Postgres later if needed.
"""
import json
import os
import sqlite3
import threading
import time
from typing import Any

_DB_PATH = os.environ.get("APP_DB", "penny_console.db")
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS cases(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          case_key TEXT UNIQUE, duty TEXT, entity_id TEXT, entity_name TEXT,
          title TEXT, subtitle TEXT, amount_cents INTEGER DEFAULT 0,
          confidence REAL, verdict_status TEXT, route_lane TEXT, tier TEXT,
          status TEXT DEFAULT 'open',           -- open | routed | dismissed | cleared
          trace TEXT DEFAULT '[]', vtext TEXT DEFAULT '',
          flagged_at REAL);
        CREATE TABLE IF NOT EXISTS turns(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT, role TEXT, content TEXT, meta TEXT DEFAULT '{}', at REAL);
        CREATE TABLE IF NOT EXISTS stats(
          id INTEGER PRIMARY KEY CHECK (id=1), scanned INTEGER DEFAULT 0, investigating INTEGER DEFAULT 0);
        INSERT OR IGNORE INTO stats(id) VALUES (1);
        """)
    return _conn


def case_row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["trace"] = json.loads(d.pop("trace") or "[]")
    return d


def create_case(fields: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        cur = conn().execute(
            """INSERT INTO cases(case_key,duty,entity_id,entity_name,title,subtitle,amount_cents,
               confidence,verdict_status,route_lane,tier,status,trace,vtext,flagged_at)
               VALUES(:case_key,:duty,:entity_id,:entity_name,:title,:subtitle,:amount_cents,
               :confidence,:verdict_status,:route_lane,:tier,:status,:trace,:vtext,:flagged_at)""",
            {**fields, "trace": json.dumps(fields.get("trace", [])), "flagged_at": time.time()})
        conn().commit()
        return get_case(cur.lastrowid)


def get_case(case_id: int) -> dict[str, Any] | None:
    r = conn().execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    return case_row(r) if r else None


def set_case_status(case_id: int, status: str) -> dict[str, Any] | None:
    with _lock:
        conn().execute("UPDATE cases SET status=? WHERE id=?", (status, case_id))
        conn().commit()
    return get_case(case_id)


def has_open_case(duty: str, entity_id: str) -> bool:
    r = conn().execute(
        "SELECT 1 FROM cases WHERE duty=? AND entity_id=? AND status IN ('open','routed') LIMIT 1",
        (duty, entity_id)).fetchone()
    return r is not None


def open_flags() -> list[dict[str, Any]]:
    rs = conn().execute(
        "SELECT * FROM cases WHERE status IN ('open','routed') ORDER BY id DESC LIMIT 20").fetchall()
    return [case_row(r) for r in rs]


def cleared() -> list[dict[str, Any]]:
    rs = conn().execute(
        "SELECT * FROM cases WHERE status IN ('cleared','dismissed') ORDER BY id DESC LIMIT 6").fetchall()
    return [case_row(r) for r in rs]


def add_turn(session_id: str, role: str, content: str, meta: dict | None = None) -> None:
    with _lock:
        conn().execute("INSERT INTO turns(session_id,role,content,meta,at) VALUES(?,?,?,?,?)",
                       (session_id, role, content, json.dumps(meta or {}), time.time()))
        conn().commit()


def bump(scanned: int = 0, investigating: int = 0) -> None:
    with _lock:
        conn().execute("UPDATE stats SET scanned=scanned+?, investigating=MAX(0,investigating+?) WHERE id=1",
                       (scanned, investigating))
        conn().commit()


def snapshot() -> dict[str, Any]:
    s = conn().execute("SELECT * FROM stats WHERE id=1").fetchone()
    f = conn().execute(
        "SELECT COUNT(*) n, COALESCE(SUM(amount_cents),0) x FROM cases WHERE status IN ('open','routed')").fetchone()
    c = conn().execute("SELECT COUNT(*) n FROM cases WHERE status IN ('cleared','dismissed')").fetchone()
    return {"scanned": s["scanned"], "investigating": s["investigating"],
            "flagged": f["n"], "exposure_cents": f["x"], "cleared": c["n"]}


def recent_turns(session_id: str, limit: int = 24) -> list[dict[str, Any]]:
    rs = conn().execute(
        "SELECT role, content FROM turns WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit)).fetchall()
    return [dict(r) for r in reversed(rs)]


def verdict_ledger(limit: int = 20) -> list[dict[str, Any]]:
    """Decision memory: what Penny already flagged/cleared — dedup + continuity across sessions."""
    rs = conn().execute(
        "SELECT duty, entity_id, verdict_status, status, amount_cents FROM cases ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    return [dict(r) for r in rs]
