"""Background rail feed: ticker transactions + seeded cases through the funnel.

Case cadence is time-based (SIM_CASE_INTERVAL seconds, default 20 — busy demo
tempo) and **eligibility-aware**: a candidate is only announced when it will
visibly resolve — flag seeds are skipped while an identical case is still open
(process or dismiss it in chat and the pattern becomes eligible to re-flag);
clear seeds always run (each pass is a fresh "checked & cleared" event).
So the funnel never announces an investigation that silently dedupes to nothing.

Runs as an asyncio task inside the web process (SIMULATOR=0 disables).
"""
import asyncio
import os
import random
import time

from . import bus, cases, seeds, store

TX_TYPES = [("sale", 60), ("card sale", 22), ("cash sale", 10), ("refund", 4), ("void", 3), ("no_sale", 1)]
STORES = list(seeds.BRANCHES)
CASE_INTERVAL = float(os.environ.get("SIM_CASE_INTERVAL", "20"))


def _pick_type() -> str:
    r, acc = random.random() * 100, 0
    for t, w in TX_TYPES:
        acc += w
        if r < acc:
            return t
    return "sale"


def pick_eligible(start_idx: int) -> tuple[int, dict | None]:
    """Next seed (round-robin from start_idx) that will visibly resolve."""
    n = len(seeds.CASES)
    for off in range(n):
        i = (start_idx + off) % n
        seed = seeds.CASES[i]
        if seed["verdict"] == "clear" or not store.has_open_case(seed["duty"], seed["entity_id"]):
            return i, seed
    return start_idx, None  # every flag open and… no clears exist (can't happen with current seeds)


async def run(inject_event: asyncio.Event, ticker: bool = True) -> None:
    idx, last_case = 0, 0.0
    while True:
        await asyncio.sleep(1.1)
        if ticker:
            sid = random.choice(STORES)
            bus.publish({"type": "ticker", "ts": time.time(), "branch": seeds.BRANCHES[sid],
                         "store_id": sid, "txn": _pick_type(),
                         "amount_cents": random.randint(800, 3500)})
            store.bump(scanned=1)
            bus.publish({"type": "kpis", "stats": store.snapshot()})
        now = time.monotonic()
        if inject_event.is_set() or now - last_case >= CASE_INTERVAL:
            inject_event.clear()
            i, seed = pick_eligible(idx)
            if seed is None:
                continue
            idx, last_case = i + 1, now
            bus.publish({"type": "ticker", "ts": time.time(), "cand": True,
                         "label": f"candidate: {seed['duty']} @ {seeds.name_of(seed['entity_id'])}"})
            store.bump(investigating=1)
            bus.publish({"type": "kpis", "stats": store.snapshot()})
            asyncio.get_event_loop().call_later(2.2, _resolve, seed)


def _resolve(seed: dict) -> None:
    store.bump(investigating=-1)
    cases.from_seed(seed, lap=int(time.time() * 1000))
