"""Output sinks for the synthetic stream.

Every sink receives ``(table, row)`` events where ``row`` has exactly the source
column layout, so the target is always union-compatible with ``world.fin_*``.

Sinks:
  * JsonlSink   — one JSON object per line to stdout (or a file): stream it.
  * SqliteSink  — mirror tables in a local .db. With ``seed_from`` it also copies
                  the real finance tables into the same file as ``world_fin_*`` so
                  you can UNION ALL real + synthetic entirely in SQLite.
  * PostgresSink— mirror tables in a target Postgres ``synth`` schema.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any

import psycopg

from . import schema


class Sink:
    def emit(self, table: str, row: dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:
        pass


class JsonlSink(Sink):
    """Newline-delimited JSON. Pipe it: ``... | jq`` / ``... | kcat -P``."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout

    def emit(self, table: str, row: dict[str, Any]) -> None:
        payload = {"table": table, "row": schema.coerce(table, row, dialect="json")}
        self.stream.write(json.dumps(payload, default=str) + "\n")
        self.stream.flush()


class SqliteSink(Sink):
    def __init__(self, path: str, *, synth_prefix: str = "synth_", seed_from: str | None = None):
        self.synth_prefix = synth_prefix
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        for t in schema.TABLES:
            self.conn.execute(
                schema.create_table_sql(t, dialect="sqlite", name_override=f"{synth_prefix}{t}")
            )
        if seed_from:
            self._seed_real_tables(seed_from)
        self.conn.commit()

    def _seed_real_tables(self, dsn: str) -> None:
        """Copy the live finance tables into world_<table> for in-file unions."""
        with psycopg.connect(dsn, connect_timeout=20) as pg, pg.cursor() as cur:
            for t in schema.TABLES:
                real_name = f"world_{t}"
                self.conn.execute(f'DROP TABLE IF EXISTS "{real_name}"')
                self.conn.execute(
                    schema.create_table_sql(t, dialect="sqlite", name_override=real_name)
                )
                cols = schema.column_names(t)
                cur.execute(f'SELECT {", ".join(cols)} FROM world."{t}"')
                placeholders = ",".join("?" * len(cols))
                rows = [
                    tuple(
                        schema.coerce(t, dict(zip(cols, r)), dialect="sqlite")[c] for c in cols
                    )
                    for r in cur.fetchall()
                ]
                if rows:
                    self.conn.executemany(
                        f'INSERT INTO "{real_name}" ({",".join(cols)}) VALUES ({placeholders})',
                        rows,
                    )
        self.conn.commit()

    def emit(self, table: str, row: dict[str, Any]) -> None:
        cols = schema.column_names(table)
        vals = schema.coerce(table, row, dialect="sqlite")
        placeholders = ",".join("?" * len(cols))
        self.conn.execute(
            f'INSERT OR REPLACE INTO "{self.synth_prefix}{table}" '
            f'({",".join(cols)}) VALUES ({placeholders})',
            [vals[c] for c in cols],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


class PostgresSink(Sink):
    def __init__(self, dsn: str, *, schema_name: str = "synth"):
        self.schema_name = schema_name
        self.conn = psycopg.connect(dsn, connect_timeout=20, autocommit=True)
        with self.conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            for t in schema.TABLES:
                ddl = schema.create_table_sql(t, dialect="postgres")
                ddl = ddl.replace(
                    f'CREATE TABLE IF NOT EXISTS "{t}"',
                    f'CREATE TABLE IF NOT EXISTS "{schema_name}"."{t}"',
                    1,
                )
                cur.execute(ddl)

    def emit(self, table: str, row: dict[str, Any]) -> None:
        cols = schema.column_names(table)
        vals = schema.coerce(table, row, dialect="postgres")
        placeholders = ",".join(["%s"] * len(cols))
        pk = schema.primary_key(table)
        if pk:
            updatable = [c for c in cols if c not in pk]
            if updatable:
                sets = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in updatable)
                conflict = f' ON CONFLICT ({",".join(pk)}) DO UPDATE SET {sets}'
            else:
                conflict = f' ON CONFLICT ({",".join(pk)}) DO NOTHING'
        else:
            conflict = ""
        with self.conn.cursor() as cur:
            cur.execute(
                f'INSERT INTO "{self.schema_name}"."{table}" '
                f'({",".join(cols)}) VALUES ({placeholders}){conflict}',
                [vals[c] for c in cols],
            )

    def close(self) -> None:
        self.conn.close()


class MultiSink(Sink):
    def __init__(self, sinks: list[Sink]):
        self.sinks = sinks

    def emit(self, table: str, row: dict[str, Any]) -> None:
        for s in self.sinks:
            s.emit(table, row)

    def close(self) -> None:
        for s in self.sinks:
            s.close()
