"""Load reference/dimension data from the read-only source.

The generator produces *new* transactional rows, but they must reference real
dimension keys (stores, staff, suppliers, SKUs, agreed prices, fee schedule) so
the synthetic data is join-consistent with the source and unions cleanly.

We also read the current max numeric id per table so generated ids continue the
existing sequences instead of colliding with them.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import psycopg

# id column suffix is a zero-padded integer; capture width so we match the
# source formatting (rtx_000674, po_00164, ...).
_SEQ_TABLES = {
    "fin_register_txns": ("rtx_", 6),
    "fin_purchase_orders": ("po_", 5),
    "fin_po_lines": ("pol_", 5),
    "fin_goods_receipts": ("gr_", 5),
    "fin_invoices": ("inv_", 5),
    "fin_invoice_lines": ("invl_", 5),
    "fin_payments_out": ("pay_", 5),
    "fin_bank_settlements": ("set_", 6),
    "fin_credit_memos": ("memo_", 5),
    "fin_paid_outs": ("pdo_", 5),
    "fin_settlement_adjustments": ("adj_", 5),
}


@dataclass
class Dimensions:
    stores: list[str]
    staff_by_store: dict[str, list[dict[str, Any]]]
    suppliers: list[dict[str, Any]]
    # supplier_id -> list of {sku_id, unit_cost_cents} that are active
    catalog: dict[str, list[dict[str, Any]]]
    fee_schedule: list[dict[str, Any]]
    # (sku_id) -> (min_qty, max_qty) observed order quantities
    order_qty: dict[str, tuple[int, int]]
    seq: dict[str, int] = field(default_factory=dict)

    def next_seq(self, table: str) -> str:
        prefix, width = _SEQ_TABLES[table]
        self.seq[table] = self.seq.get(table, 0) + 1
        return f"{prefix}{self.seq[table]:0{width}d}"


def load_dimensions(dsn: str) -> Dimensions:
    with psycopg.connect(dsn, connect_timeout=20) as conn, conn.cursor() as cur:
        # stores + staff
        cur.execute(
            "SELECT id, store_id, name, role, status FROM world.fin_staff "
            "WHERE status = 'active' ORDER BY store_id, id"
        )
        staff_by_store: dict[str, list[dict[str, Any]]] = {}
        for sid, store_id, name, role, status in cur.fetchall():
            staff_by_store.setdefault(store_id, []).append(
                {"id": sid, "store_id": store_id, "name": name, "role": role}
            )
        stores = sorted(staff_by_store)

        # suppliers
        cur.execute(
            "SELECT id, name, category, payment_terms, tax_id FROM world.fin_suppliers ORDER BY id"
        )
        suppliers = [
            {"id": r[0], "name": r[1], "category": r[2], "payment_terms": r[3], "tax_id": r[4]}
            for r in cur.fetchall()
        ]

        # active price list -> catalog per supplier
        cur.execute(
            "SELECT supplier_id, sku_id, agreed_unit_cost_cents FROM world.fin_price_list "
            "WHERE end_date IS NULL ORDER BY supplier_id, sku_id"
        )
        catalog: dict[str, list[dict[str, Any]]] = {}
        for supplier_id, sku_id, cost in cur.fetchall():
            catalog.setdefault(supplier_id, []).append(
                {"sku_id": sku_id, "unit_cost_cents": cost}
            )

        # fee schedule (latest effective per processor/card_type)
        cur.execute(
            "SELECT DISTINCT ON (processor, card_type) processor, card_type, mdr_bps, per_txn_fee_cents "
            "FROM world.fin_fee_schedule ORDER BY processor, card_type, effective_date DESC"
        )
        fee_schedule = [
            {"processor": r[0], "card_type": r[1], "mdr_bps": r[2], "per_txn_fee_cents": r[3]}
            for r in cur.fetchall()
        ]

        # observed order quantities per sku
        cur.execute(
            "SELECT sku_id, min(ordered_qty)::int, max(ordered_qty)::int "
            "FROM world.fin_po_lines GROUP BY sku_id"
        )
        order_qty = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        # id sequence high-water marks
        seq: dict[str, int] = {}
        for table, (_prefix, _w) in _SEQ_TABLES.items():
            cur.execute(
                f"SELECT COALESCE(max(substring(id from '[0-9]+$')::int), 0) "
                f"FROM world.\"{table}\" WHERE id ~ '[0-9]+$'"
            )
            seq[table] = cur.fetchone()[0]

    return Dimensions(
        stores=stores,
        staff_by_store=staff_by_store,
        suppliers=suppliers,
        catalog=catalog,
        fee_schedule=fee_schedule,
        order_qty=order_qty,
        seq=seq,
    )
