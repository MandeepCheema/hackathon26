"""Schema helpers.

Loads the exact column layout of the ``world.fin_*`` tables (captured from the
read-only source into ``_schema.json``) and produces:

  * CREATE TABLE DDL for a local mirror (SQLite or Postgres) with an identical
    column order and compatible types, so synthetic rows can be UNION ALL'd
    against the real tables.
  * value coercion so Python objects land in the right column type.

The whole point is *union compatibility*: a synthetic ``fin_invoices`` row has
exactly the same columns, in the same order, as ``world.fin_invoices``.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from decimal import Decimal
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_HERE, "_schema.json")

# Every finance table, in dependency order (parents before children). The
# stream writes children only after their parents exist, so this order also
# works for a straight replay/load.
TABLES: list[str] = [
    # dimensions / lookups
    "fin_suppliers",
    "fin_staff",
    "fin_fee_schedule",
    "fin_price_list",
    "fin_policy",
    # accounts payable chain
    "fin_purchase_orders",
    "fin_po_lines",
    "fin_goods_receipts",
    "fin_invoices",
    "fin_invoice_lines",
    "fin_payments_out",
    "fin_credit_memos",
    # POS / cash
    "fin_register_txns",
    "fin_register_totals",
    "fin_card_mix",
    "fin_cash_counts",
    "fin_paid_outs",
    # settlement
    "fin_bank_settlements",
    "fin_settlement_adjustments",
]


def load_schema() -> dict[str, Any]:
    with open(_SCHEMA_PATH) as fh:
        return json.load(fh)


_SCHEMA = load_schema()


def columns(table: str) -> list[dict[str, Any]]:
    """Ordered column metadata for a table."""
    return _SCHEMA[table]


def column_names(table: str) -> list[str]:
    return [c["name"] for c in _SCHEMA[table]]


def primary_key(table: str) -> list[str]:
    return _SCHEMA.get(f"{table}__pk", [])


# --- type mapping -----------------------------------------------------------

_PG_TO_SQLITE = {
    "integer": "INTEGER",
    "text": "TEXT",
    "numeric": "NUMERIC",
    "date": "TEXT",  # ISO-8601 string; sorts/compares correctly
    "timestamp with time zone": "TEXT",
    "boolean": "INTEGER",
}


def _sqlite_type(col: dict[str, Any]) -> str:
    return _PG_TO_SQLITE.get(col["type"], "TEXT")


def _pg_type(col: dict[str, Any]) -> str:
    t = col["type"]
    if t == "numeric" and col.get("num_prec"):
        scale = col.get("num_scale") or 0
        return f"numeric({col['num_prec']},{scale})"
    return t


def create_table_sql(table: str, *, dialect: str, name_override: str | None = None) -> str:
    """Return a CREATE TABLE IF NOT EXISTS statement mirroring the source."""
    tname = name_override or table
    cols = _SCHEMA[table]
    type_fn = _sqlite_type if dialect == "sqlite" else _pg_type
    lines = []
    for c in cols:
        piece = f'  "{c["name"]}" {type_fn(c)}'
        if c["nullable"] == "NO":
            piece += " NOT NULL"
        lines.append(piece)
    pk = primary_key(table)
    if pk:
        lines.append("  PRIMARY KEY (" + ", ".join(f'"{p}"' for p in pk) + ")")
    inner = ",\n".join(lines)
    return f'CREATE TABLE IF NOT EXISTS "{tname}" (\n{inner}\n);'


# --- value coercion ---------------------------------------------------------

def coerce(table: str, row: dict[str, Any], *, dialect: str) -> dict[str, Any]:
    """Coerce a generated row into DB-ready values for the given dialect.

    For sqlite/JSON, dates and timestamps become ISO strings and Decimals
    become float/int. For postgres, native python objects pass straight
    through to psycopg.
    """
    out: dict[str, Any] = {}
    by_name = {c["name"]: c for c in _SCHEMA[table]}
    for name in column_names(table):
        v = row.get(name)
        col = by_name[name]
        if v is None:
            out[name] = None
            continue
        if dialect == "postgres":
            out[name] = v
            continue
        # sqlite / json: normalise to primitives
        if isinstance(v, (dt.datetime,)):
            out[name] = v.isoformat()
        elif isinstance(v, (dt.date,)):
            out[name] = v.isoformat()
        elif isinstance(v, Decimal):
            out[name] = float(v) if col["type"] == "numeric" else int(v)
        else:
            out[name] = v
    return out
