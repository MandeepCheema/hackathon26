"""Case creation + the app-owned routing map (status → lane/tier), per the
handoff doc: the agent owns verdicts; the app owns routing, tiers and audit."""
from typing import Any

from . import bus, seeds, store

ROUTING = {
    "pattern_short": ("Loss-Prevention · Regional Mgr", "approval"),
    "refer_investigation": ("Loss-Prevention · Regional Mgr", "approval"),
    "duplicate": ("Accounts Payable", "approval"),
    "price_variance": ("Supplier Relations", "1-click"),
    "over_billed_qty": ("Supplier Relations", "1-click"),
    "shortfall": ("Controller review", "1-click"),
    "over": ("Controller review", "1-click"),
    "leakage": ("Controller review", "1-click"),
}
CLEAR_STATUSES = {"balanced", "clear", "within_tolerance", "reconciled"}


def _publish(kase: dict[str, Any]) -> None:
    kind = "case.flagged" if kase["status"] in ("open", "routed") else "case.cleared"
    bus.publish({"type": kind, "case": kase})
    bus.publish({"type": "kpis", "stats": store.snapshot()})


def from_seed(seed: dict[str, Any], lap: int) -> dict[str, Any] | None:
    flagged = seed["verdict"] == "flag"
    # demo hygiene: don't stack an identical open flag for the same entity
    if flagged and store.has_open_case(seed["duty"], seed["entity_id"]):
        return None
    kase = store.create_case(dict(
        case_key=f"{seed['duty']}:{seed['entity_id']}:{lap}",
        duty=seed["duty"], entity_id=seed["entity_id"], entity_name=seeds.name_of(seed["entity_id"]),
        title=seed["title"], subtitle=seed["subtitle"], amount_cents=seed["amount_cents"],
        confidence=seed["confidence"], verdict_status=seed["verdict_status"],
        route_lane=seed["route_lane"], tier=seed["tier"],
        status="open" if flagged else "cleared", trace=seed["trace"], vtext=seed["vtext"]))
    _publish(kase)
    return kase


def from_verdict_event(ev: dict[str, Any]) -> dict[str, Any]:
    """From a real agent verdict: {"tool": "submit_cash_variance", "args": {...}, "duty": ...}."""
    import re
    import time
    args = ev.get("args") or {}
    status = args.get("status") or args.get("risk_level") or args.get("exception_type") or "flag"
    duty = ev.get("duty") or ev.get("tool", "").replace("submit_", "").replace("_", "-")
    entity = args.get("store_id") or args.get("staff_id") or args.get("supplier_id") or args.get("po_id") or "unknown"
    note = args.get("note") or args.get("evidence_note") or ""
    m = re.search(r"confidence=(\d\.\d+)", note)
    lane, tier = ROUTING.get(status, (None, None))
    flagged = status not in CLEAR_STATUSES
    amount = abs(args.get("variance_cents") or args.get("amount_cents") or args.get("missing_cents") or 0)
    kase = store.create_case(dict(
        case_key=f"{duty}:{entity}:{int(time.time() * 1000)}",
        duty=duty, entity_id=entity, entity_name=seeds.name_of(entity),
        title=f"{status} — {seeds.name_of(entity)}", subtitle=note[:90],
        amount_cents=amount, confidence=float(m.group(1)) if m else None,
        verdict_status=status, route_lane=lane, tier=tier,
        status="open" if flagged else "cleared",
        trace=[[ev.get("tool", "submit"), note]],
        vtext=f"<b>{status}.</b> {note[:180]}"))
    _publish(kase)
    return kase


def act(case_id: int, action: str) -> dict[str, Any] | None:
    """Confirm/dismiss — app-side state change + audit trail + rail update."""
    kase = store.get_case(case_id)
    if not kase or kase["status"] not in ("open",):
        return None
    new_status = "routed" if action == "confirm" else "dismissed"
    kase = store.set_case_status(case_id, new_status)
    store.add_turn("audit", action, f"case {case_id}: {kase['title']}", {"case": case_id})
    bus.publish({"type": "case.updated", "case": kase})
    if new_status == "dismissed":
        bus.publish({"type": "case.cleared", "case": kase})
    bus.publish({"type": "kpis", "stats": store.snapshot()})
    return kase
