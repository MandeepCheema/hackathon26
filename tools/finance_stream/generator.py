"""The finance simulation.

Produces *new* rows for the whole finance model with referential integrity and
distributions learned from the source:

  POS side:  fin_register_txns  ->  (end of day)  fin_register_totals,
             fin_card_mix, fin_cash_counts, fin_paid_outs
             ->  fin_bank_settlements, fin_settlement_adjustments
  AP side:   fin_purchase_orders -> fin_po_lines -> fin_goods_receipts
             -> fin_invoices -> fin_invoice_lines -> fin_payments_out
             -> fin_credit_memos

Generation is pure/stateful; *when* each thing happens is decided by the
scheduler in ``stream.py``. All timestamps are supplied by the caller (the sim
clock), so the same code works in wall-clock real time or time-compressed.
"""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from .dims import Dimensions

OPEN_HOUR = 9
CLOSE_HOUR = 21

# txn_type mix, from source counts
TXN_TYPES = ["sale", "void", "discount", "refund", "no_sale"]
TXN_WEIGHTS = [1896, 479, 81, 70, 15]

# card type mix, from fin_card_mix average txn_count
CARD_TYPES = ["credit", "debit", "amex"]
CARD_WEIGHTS = [131, 79, 21]

CASH_PROB = 0.30          # share of sales paid in cash
SETTLEMENT_FEE_BPS = 226  # blended, from fin_bank_settlements
PROCESSOR = "cardnet"

EmitFn = Callable[[str, dict[str, Any]], None]
LeakFn = Callable[[dict[str, Any]], None]

# Injectable leak scenarios (ground truth for scoring a detector like Penny).
LEAK_TYPES = ["skim", "overcharge", "duplicate_payment"]


@dataclass
class DayState:
    cash_cents: int = 0
    card_cents: int = 0
    txn_count: int = 0
    card_txn_count: int = 0
    paid_out_cents: int = 0
    refund_cents: int = 0
    card_mix: dict[str, dict[str, int]] = field(default_factory=dict)


class FinanceSimulator:
    def __init__(
        self,
        dims: Dimensions,
        emit: EmitFn,
        *,
        seed: int = 0,
        leaks: set[str] | None = None,
        leak_rate: float = 0.0,
        on_leak: LeakFn | None = None,
    ):
        self.dims = dims
        self.emit = emit
        self.rng = random.Random(seed)
        self.day: dict[tuple[str, dt.date], DayState] = {}
        # leak injection: enabled types, per-opportunity probability, and a sink
        # for the ground-truth record (so a detector can be scored on it)
        self.leaks = leaks or set()
        self.leak_rate = leak_rate
        self._on_leak = on_leak
        self.leak_count = 0

    def _fire_leak(self, kind: str) -> bool:
        return kind in self.leaks and self.rng.random() < self.leak_rate

    def _record_leak(self, rec: dict[str, Any]) -> None:
        self.leak_count += 1
        if self._on_leak:
            self._on_leak(rec)

    # ------------------------------------------------------------------ POS

    def _day(self, store: str, d: dt.date) -> DayState:
        return self.day.setdefault((store, d), DayState())

    def _amount_for(self, txn_type: str) -> int:
        r = self.rng
        if txn_type == "no_sale":
            return 0
        if txn_type == "discount":
            return r.randint(200, 880)
        if txn_type == "sale":
            return int(min(3498, max(800, r.gauss(2155, 550))))
        # void / refund resemble a sale amount
        return int(min(2998, max(800, r.gauss(1930, 500))))

    def register_txn(self, store: str, ts: dt.datetime) -> None:
        """Emit one POS transaction and fold it into the day's accumulators."""
        r = self.rng
        staff = r.choice(self.dims.staff_by_store[store])
        txn_type = r.choices(TXN_TYPES, TXN_WEIGHTS)[0]
        amount = self._amount_for(txn_type)
        d = ts.date()
        st = self._day(store, d)

        is_card = txn_type == "sale" and r.random() > CASH_PROB
        card_last4 = f"{r.randint(0, 9999):04d}" if (txn_type in ("sale", "refund", "void") and is_card) else None

        if txn_type == "sale":
            st.txn_count += 1
            if is_card:
                st.card_cents += amount
                st.card_txn_count += 1
                ct = r.choices(CARD_TYPES, CARD_WEIGHTS)[0]
                m = st.card_mix.setdefault(ct, {"gross": 0, "txn": 0})
                m["gross"] += amount
                m["txn"] += 1
            else:
                st.cash_cents += amount
        elif txn_type == "refund":
            st.refund_cents += amount

        self.emit("fin_register_txns", {
            "id": self.dims.next_seq("fin_register_txns"),
            "store_id": store,
            "staff_id": staff["id"],
            "business_date": d,
            "ts": ts,
            "txn_type": txn_type,
            "amount_cents": amount,
            "card_last4": card_last4,
            "note": "",
        })

    def close_day(self, store: str, d: dt.date, *, deposit_ts: dt.datetime | None = None) -> None:
        """End-of-day rollups + settlement for one store/day."""
        st = self.day.pop((store, d), None)
        if st is None or st.txn_count == 0:
            return
        r = self.rng

        # occasional petty-cash / change-order paid_out (rare in source)
        if r.random() < 0.02:
            reason, note = r.choice([
                ("petty_cash", "register supplies, manager approved"),
                ("change_order", "bank change order for tills"),
            ])
            st.paid_out_cents = r.choice([10000, 20000, 30000])
            self.emit("fin_paid_outs", {
                "id": self.dims.next_seq("fin_paid_outs"),
                "store_id": store, "business_date": d,
                "amount_cents": st.paid_out_cents, "reason": reason, "note": note,
            })

        self.emit("fin_register_totals", {
            "store_id": store, "business_date": d,
            "cash_cents": st.cash_cents, "card_cents": st.card_cents,
            "txn_count": st.txn_count, "card_txn_count": st.card_txn_count,
        })
        for ct, m in st.card_mix.items():
            self.emit("fin_card_mix", {
                "store_id": store, "business_date": d, "card_type": ct,
                "gross_cents": m["gross"], "txn_count": m["txn"],
            })

        # counted cash = opening float + cash sales - paid outs + small variance
        variance = r.randint(-400, 200)
        counted = 15000 + st.cash_cents - st.paid_out_cents + variance
        # LEAK: skim — cash quietly removed, so the drawer counts short
        if st.cash_cents > 0 and self._fire_leak("skim"):
            skim = min(st.cash_cents, r.randint(2000, 15000))
            counted -= skim
            self._record_leak({
                "leak_type": "skim", "detect_via": "cash_over_short",
                "table": "fin_cash_counts", "store_id": store, "business_date": d,
                "amount_cents": skim,
                "note": f"drawer short ${skim/100:.2f} vs expected cash",
            })
        self.emit("fin_cash_counts", {
            "store_id": store, "business_date": d,
            "counted_cash_cents": max(0, counted),
        })

        # settlement of the day's card gross, deposited T+1/T+2
        if st.card_cents > 0:
            lag = r.choice([1, 1, 2])
            deposit_date = d + dt.timedelta(days=lag)
            fee = round(st.card_cents * SETTLEMENT_FEE_BPS / 10000)
            self.emit("fin_bank_settlements", {
                "id": self.dims.next_seq("fin_bank_settlements"),
                "store_id": store, "processor": PROCESSOR,
                "deposit_date": deposit_date, "covers_date": d,
                "gross_cents": st.card_cents, "fee_cents": fee,
                "net_deposit_cents": st.card_cents - fee,
            })

        # refunds settle as an adjustment batch (rare)
        if st.refund_cents > 0 and r.random() < 0.5:
            self.emit("fin_settlement_adjustments", {
                "id": self.dims.next_seq("fin_settlement_adjustments"),
                "store_id": store, "business_date": d,
                "kind": "refund", "amount_cents": st.refund_cents,
                "note": "daily refund batch",
            })

    # ------------------------------------------------------------------- AP

    def create_purchase_order(self, ts: dt.datetime) -> dict[str, Any] | None:
        """Place a PO (status 'ordered') with 1-3 lines. Returns AP state for
        the scheduler to drive receipt/invoice/payment follow-ups."""
        r = self.rng
        # only suppliers with a real catalog can be ordered from
        supplier = r.choice([s for s in self.dims.suppliers if self.dims.catalog.get(s["id"])])
        store = r.choice(self.dims.stores)
        po_id = self.dims.next_seq("fin_purchase_orders")

        self.emit("fin_purchase_orders", {
            "id": po_id, "supplier_id": supplier["id"], "store_id": store,
            "ordered_at": ts, "status": "ordered",
        })

        skus = self.dims.catalog[supplier["id"]]
        k = min(len(skus), r.randint(1, 3))
        chosen = r.sample(skus, k)
        lines = []
        for item in chosen:
            lo, hi = self.dims.order_qty.get(item["sku_id"], (20, 300))
            qty = r.randint(lo, hi) if hi > lo else lo
            line_id = self.dims.next_seq("fin_po_lines")
            self.emit("fin_po_lines", {
                "id": line_id, "po_id": po_id, "sku_id": item["sku_id"],
                "ordered_qty": qty, "agreed_unit_cost_cents": item["unit_cost_cents"],
            })
            lines.append({"line_id": line_id, "sku_id": item["sku_id"],
                          "qty": qty, "unit_cost": item["unit_cost_cents"]})

        return {"po_id": po_id, "supplier": supplier, "store": store, "lines": lines}

    def receive_po(self, po: dict[str, Any], ts: dt.datetime) -> None:
        """Record goods receipts and flip the PO to 'received'."""
        r = self.rng
        for ln in po["lines"]:
            # occasionally short-ship
            recv = ln["qty"] if r.random() > 0.1 else round(ln["qty"] * r.uniform(0.8, 0.99))
            ln["received_qty"] = recv
            self.emit("fin_goods_receipts", {
                "id": self.dims.next_seq("fin_goods_receipts"),
                "po_id": po["po_id"], "po_line_id": ln["line_id"],
                "sku_id": ln["sku_id"], "received_qty": recv, "received_at": ts,
            })
        self.emit("fin_purchase_orders", {
            "id": po["po_id"], "supplier_id": po["supplier"]["id"],
            "store_id": po["store"], "ordered_at": ts, "status": "received",
        })

    def invoice_po(self, po: dict[str, Any], ts: dt.datetime) -> dict[str, Any]:
        """Supplier invoices the received goods (status 'approved')."""
        r = self.rng
        inv_id = self.dims.next_seq("fin_invoices")
        # LEAK: overcharge — bill one line above the agreed unit cost (or over the
        # received qty), so the three-way match (PO vs receipt vs invoice) breaks
        overcharge_ix = r.randrange(len(po["lines"])) if (po["lines"] and self._fire_leak("overcharge")) else -1
        subtotal = 0
        for i, ln in enumerate(po["lines"]):
            qty = ln.get("received_qty", ln["qty"])
            unit_cost = ln["unit_cost"]
            if i == overcharge_ix:
                mode = r.choice(["price", "qty"])
                if mode == "price":
                    unit_cost = int(round(ln["unit_cost"] * r.uniform(1.15, 1.45)))
                else:
                    qty = qty + r.randint(int(qty * 0.15) + 1, int(qty * 0.5) + 2)
            invl_id = self.dims.next_seq("fin_invoice_lines")
            line_total = int(qty * unit_cost)
            subtotal += line_total
            self.emit("fin_invoice_lines", {
                "id": invl_id, "invoice_id": inv_id, "po_line_id": ln["line_id"],
                "sku_id": ln["sku_id"], "billed_qty": qty,
                "billed_unit_cost_cents": unit_cost,
                "description": f'{ln["sku_id"]} delivery',
            })
            if i == overcharge_ix:
                fair = int(ln.get("received_qty", ln["qty"]) * ln["unit_cost"])
                self._record_leak({
                    "leak_type": "overcharge", "detect_via": "three_way_match",
                    "table": "fin_invoice_lines", "ref_id": invl_id,
                    "invoice_id": inv_id, "supplier_id": po["supplier"]["id"],
                    "amount_cents": line_total - fair,
                    "note": f'billed {mode} above agreed on {ln["sku_id"]} '
                            f'(agreed {ln["unit_cost"]}c x {ln.get("received_qty", ln["qty"])})',
                })
        seq_num = int(self.dims.seq["fin_invoices"])
        invoice_number = f"INV-{4200 + seq_num}"
        self.emit("fin_invoices", {
            "id": inv_id, "supplier_id": po["supplier"]["id"], "po_id": po["po_id"],
            "invoice_number": invoice_number, "invoiced_at": ts,
            "subtotal_cents": subtotal, "tax_cents": 0, "freight_cents": 0,
            "total_cents": subtotal, "status": "approved",
        })
        return {"invoice_id": inv_id, "supplier": po["supplier"], "po_id": po["po_id"],
                "invoice_number": invoice_number, "total": subtotal, "invoiced_at": ts}

    def pay_invoice(self, inv: dict[str, Any], ts: dt.datetime) -> None:
        """Pay the invoice and flip it to 'paid'; occasionally issue a credit memo."""
        r = self.rng
        seq_num = self.dims.seq["fin_payments_out"] + 1
        first_pay_id = self.dims.next_seq("fin_payments_out")
        self.emit("fin_payments_out", {
            "id": first_pay_id,
            "supplier_id": inv["supplier"]["id"], "invoice_id": inv["invoice_id"],
            "paid_at": ts, "amount_cents": inv["total"], "method": "ach",
            "reference": f"ACH-{8000 + seq_num}",
        })
        # LEAK: duplicate payment — the SAME invoice is paid a second time
        if self._fire_leak("duplicate_payment"):
            seq2 = self.dims.seq["fin_payments_out"] + 1
            dup_id = self.dims.next_seq("fin_payments_out")
            dup_ts = ts + dt.timedelta(days=r.randint(1, 6))
            self.emit("fin_payments_out", {
                "id": dup_id,
                "supplier_id": inv["supplier"]["id"], "invoice_id": inv["invoice_id"],
                "paid_at": dup_ts, "amount_cents": inv["total"], "method": "ach",
                "reference": f"ACH-{8000 + seq2}",
            })
            self._record_leak({
                "leak_type": "duplicate_payment", "detect_via": "duplicate_payment",
                "table": "fin_payments_out", "ref_id": dup_id,
                "invoice_id": inv["invoice_id"], "supplier_id": inv["supplier"]["id"],
                "amount_cents": inv["total"],
                "note": f"invoice {inv['invoice_id']} paid twice ({first_pay_id} + {dup_id})",
            })
        self.emit("fin_invoices", {
            "id": inv["invoice_id"], "supplier_id": inv["supplier"]["id"],
            "po_id": inv["po_id"], "invoice_number": inv["invoice_number"],
            "invoiced_at": inv["invoiced_at"],
            "subtotal_cents": inv["total"], "tax_cents": 0, "freight_cents": 0,
            "total_cents": inv["total"], "status": "paid",
        })
        if r.random() < 0.03:
            self.emit("fin_credit_memos", {
                "id": self.dims.next_seq("fin_credit_memos"),
                "supplier_id": inv["supplier"]["id"], "invoice_id": inv["invoice_id"],
                "amount_cents": round(inv["total"] * r.uniform(0.02, 0.1)),
                "reason": "supplier credit — short/over-billed resolved",
                "issued_at": ts,
            })

    # NB: the AP lifecycle re-emits fin_purchase_orders and fin_invoices as their
    # status advances (ordered->received, approved->paid). Sinks upsert on the
    # primary key, so DB targets show the latest state while a JSONL consumer sees
    # each transition as a separate event — i.e. a CDC-style change stream.
