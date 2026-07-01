"""Wall-clock real-time scheduler for the finance simulation.

A single event heap drives everything. Each event carries a *sim time* (epoch
seconds). The loop sleeps ``(next_sim - now_sim) / speed`` real seconds, fires
the event, and lets it reschedule itself. With ``--speed 1`` (default) sim time
== real time and timestamps are the actual wall clock; larger speeds compress
time so you can watch whole days of rollups and settlements go by.

Recurring generators:
  * POS transactions per open store (exponential inter-arrival = Poisson flow)
  * End-of-day rollup per store at closing time
  * Purchase-order creation (Poisson), each spawning a receipt/invoice/payment
    chain of one-shot follow-up events
"""
from __future__ import annotations

import argparse
import datetime as dt
import heapq
import itertools
import os
import signal
import sys
import time
from typing import Any, Callable

from . import sinks
from .dims import load_dimensions
from .generator import CLOSE_HOUR, OPEN_HOUR, FinanceSimulator

UTC = dt.timezone.utc
# Read-only source for dimensions. NEVER hardcode the DSN (this repo is public);
# take it from the WORLD_PG_URI env var, the same convention as .env.example.
SOURCE_DSN = os.environ.get("WORLD_PG_URI")


class Clock:
    """Maps real elapsed time to sim time via a speed multiplier."""

    def __init__(self, sim_start: dt.datetime, speed: float):
        self.sim_start = sim_start.timestamp()
        self.real_start = time.time()
        self.speed = speed

    def now(self) -> float:
        return self.sim_start + (time.time() - self.real_start) * self.speed

    def now_dt(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.now(), tz=UTC)

    def sleep_until(self, sim_ts: float) -> None:
        real_wait = (sim_ts - self.now()) / self.speed
        if real_wait > 0:
            time.sleep(real_wait)


class Scheduler:
    def __init__(self, clock: Clock):
        self.clock = clock
        self._heap: list[tuple[float, int, Callable[[], None]]] = []
        self._counter = itertools.count()
        self._stop = False

    def at(self, sim_ts: float, fn: Callable[[], None]) -> None:
        heapq.heappush(self._heap, (sim_ts, next(self._counter), fn))

    def after(self, seconds: float, fn: Callable[[], None]) -> None:
        self.at(self.clock.now() + seconds, fn)

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        while self._heap and not self._stop:
            sim_ts, _, fn = heapq.heappop(self._heap)
            self.clock.sleep_until(sim_ts)
            if self._stop:
                break
            fn()
            # push the fired event's reschedules; heap order handles the rest


def _next_open_ts(now: dt.datetime) -> dt.datetime:
    """The next moment a store is open (>= now)."""
    d = now
    if d.hour >= CLOSE_HOUR:
        d = (d + dt.timedelta(days=1)).replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
    elif d.hour < OPEN_HOUR:
        d = d.replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
    return d


def build_sink(args: argparse.Namespace) -> sinks.Sink:
    chosen: list[sinks.Sink] = []
    if args.sink in ("stdout", "both"):
        chosen.append(sinks.JsonlSink())
    if args.sink in ("sqlite", "both"):
        seed = args.source_dsn if args.seed_source else None
        chosen.append(sinks.SqliteSink(args.sqlite_path, seed_from=seed))
    if args.sink == "postgres":
        chosen.append(sinks.PostgresSink(args.target_dsn or os.environ["TARGET_DATABASE_URL"]))
    if not chosen:
        raise SystemExit(f"unknown sink: {args.sink}")
    return chosen[0] if len(chosen) == 1 else sinks.MultiSink(chosen)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="finance_stream",
        description="Stream synthetic, union-compatible finance data (POS + AP).",
    )
    p.add_argument("--sink", choices=["stdout", "sqlite", "postgres", "both"], default="stdout",
                   help="where to write (default: stdout JSONL). 'both' = stdout + sqlite.")
    p.add_argument("--sqlite-path", default="finance_synth.db",
                   help="sqlite file for sqlite/both sinks (default: finance_synth.db)")
    p.add_argument("--seed-source", action="store_true",
                   help="copy the live world.fin_* tables into the sqlite file as "
                        "world_<table> so you can UNION ALL real+synthetic in one file")
    p.add_argument("--target-dsn", default=None,
                   help="target Postgres DSN for the postgres sink "
                        "(else env TARGET_DATABASE_URL); writes to schema 'synth'")
    p.add_argument("--speed", type=float, default=1.0,
                   help="sim-time multiplier. 1.0 = wall-clock real time (default). "
                        "e.g. 3600 = 1 real second per sim hour")
    p.add_argument("--rate", type=float, default=6.0,
                   help="POS transactions per store per sim-hour (default: 6)")
    p.add_argument("--po-rate", type=float, default=1.5,
                   help="purchase orders created per sim-hour, all stores (default: 1.5)")
    p.add_argument("--sim-start", default=None,
                   help="ISO datetime to start the sim clock (default: now, UTC). "
                        "Set a past date + high --speed to backfill forward.")
    p.add_argument("--seed", type=int, default=0, help="RNG seed for reproducibility")
    p.add_argument("--source-dsn", default=SOURCE_DSN,
                   help="read-only source for dimensions (default: env WORLD_PG_URI)")
    args = p.parse_args(argv)

    if not args.source_dsn:
        p.error("no source DSN — set WORLD_PG_URI in your environment (.env) or pass --source-dsn")

    sim_start = (dt.datetime.fromisoformat(args.sim_start).replace(tzinfo=UTC)
                 if args.sim_start else dt.datetime.now(UTC))
    clock = Clock(sim_start, args.speed)
    sched = Scheduler(clock)

    print(f"[finance_stream] loading dimensions from source ...", file=sys.stderr)
    dims = load_dimensions(args.source_dsn)
    sink = build_sink(args)
    sim = FinanceSimulator(dims, sink.emit, seed=args.seed)
    rng = sim.rng
    print(f"[finance_stream] {len(dims.stores)} stores, {len(dims.suppliers)} suppliers; "
          f"speed={args.speed}x sink={args.sink} start={sim_start.isoformat()}",
          file=sys.stderr)

    HOUR = 3600.0
    open_stores: set[str] = set()

    # --- POS: one self-rescheduling arrival stream per store ---------------
    def schedule_pos(store: str) -> None:
        def fire() -> None:
            now = clock.now_dt()
            if OPEN_HOUR <= now.hour < CLOSE_HOUR:
                sim.register_txn(store, now)
            gap = rng.expovariate(args.rate / HOUR) if args.rate > 0 else HOUR
            # if closed, jump to next open time
            nxt = clock.now() + gap
            nxt_dt = dt.datetime.fromtimestamp(nxt, tz=UTC)
            if not (OPEN_HOUR <= nxt_dt.hour < CLOSE_HOUR):
                nxt = _next_open_ts(nxt_dt).timestamp() + rng.uniform(0, gap)
            sched.at(nxt, fire)
        sched.at(_next_open_ts(clock.now_dt()).timestamp(), fire)

    # --- POS: end-of-day rollup per store ----------------------------------
    def schedule_eod(store: str) -> None:
        def fire() -> None:
            now = clock.now_dt()
            business_date = (now - dt.timedelta(hours=CLOSE_HOUR + 1)).date()
            sim.close_day(store, business_date)
            nxt = now.replace(hour=CLOSE_HOUR, minute=5, second=0, microsecond=0)
            if nxt <= now:
                nxt = nxt + dt.timedelta(days=1)
            sched.at(nxt.timestamp(), fire)
        first = clock.now_dt().replace(hour=CLOSE_HOUR, minute=5, second=0, microsecond=0)
        if first <= clock.now_dt():
            first = first + dt.timedelta(days=1)
        sched.at(first.timestamp(), fire)

    for s in dims.stores:
        schedule_pos(s)
        schedule_eod(s)

    # --- AP: purchase orders and their follow-up chains --------------------
    def spawn_ap_chain(po: dict[str, Any], order_dt: dt.datetime) -> None:
        recv_dt = order_dt + dt.timedelta(days=rng.randint(1, 3), hours=rng.randint(0, 6))
        sched.at(recv_dt.timestamp(), lambda: _receive(po, recv_dt))

    def _receive(po: dict[str, Any], recv_dt: dt.datetime) -> None:
        sim.receive_po(po, recv_dt)
        inv_dt = recv_dt + dt.timedelta(days=rng.randint(0, 2), hours=rng.randint(1, 8))
        sched.at(inv_dt.timestamp(), lambda: _invoice(po, inv_dt))

    def _invoice(po: dict[str, Any], inv_dt: dt.datetime) -> None:
        inv = sim.invoice_po(po, inv_dt)
        terms = po["supplier"].get("payment_terms", "net30")
        days = {"net15": 15, "net30": 30, "net45": 45}.get(terms, 30)
        pay_dt = inv_dt + dt.timedelta(days=max(1, days + rng.randint(-3, 3)),
                                       hours=rng.randint(0, 6))
        sched.at(pay_dt.timestamp(), lambda: sim.pay_invoice(inv, pay_dt))

    def schedule_po() -> None:
        def fire() -> None:
            now = clock.now_dt()
            if OPEN_HOUR <= now.hour < CLOSE_HOUR:
                po = sim.create_purchase_order(now)
                if po:
                    spawn_ap_chain(po, now)
            gap = rng.expovariate(args.po_rate / HOUR) if args.po_rate > 0 else HOUR
            sched.at(clock.now() + gap, fire)
        sched.at(_next_open_ts(clock.now_dt()).timestamp(), fire)

    schedule_po()

    # --- graceful shutdown: flush partial-day rollups ----------------------
    def shutdown(*_a: Any) -> None:
        print("\n[finance_stream] flushing open days and stopping ...", file=sys.stderr)
        for (store, d) in list(sim.day.keys()):
            sim.close_day(store, d)
        sched.stop()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        sched.run()
    except BrokenPipeError:
        # downstream consumer (e.g. `head`) closed the pipe — exit quietly
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    finally:
        sink.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
