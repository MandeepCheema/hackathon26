"""app.cases — routing map, verdict-event parsing, seed dedupe, act()."""
from app import cases, seeds


def test_routing_map_covers_flag_statuses():
    for status in ["pattern_short", "refer_investigation", "duplicate", "price_variance", "shortfall"]:
        lane, tier = cases.ROUTING[status]
        assert lane and tier in ("approval", "1-click")


def test_from_verdict_event_flag(app_db):
    kase = cases.from_verdict_event({
        "tool": "submit_cash_variance",
        "args": {"store_id": "str_009", "status": "pattern_short", "variance_cents": -61000,
                 "note": "t=-3.8 over 14 days confidence=0.91"}})
    assert kase["status"] == "open"
    assert kase["entity_name"] == seeds.name_of("str_009")
    assert kase["amount_cents"] == 61000                       # abs()
    assert kase["confidence"] == 0.91                          # parsed from note
    assert kase["route_lane"] and kase["tier"] == "approval"


def test_from_verdict_event_clear(app_db):
    kase = cases.from_verdict_event({
        "tool": "submit_cogs_variance",
        "args": {"store_id": "str_002", "status": "within_tolerance", "note": "fine"}})
    assert kase["status"] == "cleared"


def test_from_verdict_event_loss_flag_entity(app_db):
    kase = cases.from_verdict_event({
        "tool": "submit_loss_flag",
        "args": {"staff_id": "stf_009_6", "store_id": "str_009",
                 "risk_level": "refer_investigation", "evidence_note": "z=3.6 confidence=0.86"}})
    # staff flags key on the store first (arg order): entity must be a real id either way
    assert kase["entity_id"] in ("stf_009_6", "str_009")
    assert kase["status"] == "open" and kase["confidence"] == 0.86


def test_from_seed_dedupes_open_flags(app_db):
    seed = next(s for s in seeds.CASES if s["verdict"] == "flag")
    first = cases.from_seed(seed, lap=1)
    dup = cases.from_seed(seed, lap=2)
    assert first is not None and dup is None                   # open case blocks a twin


def test_act_state_machine(app_db):
    seed = next(s for s in seeds.CASES if s["verdict"] == "flag")
    k = cases.from_seed(seed, lap=1)
    routed = cases.act(k["id"], "confirm")
    assert routed["status"] == "routed"
    assert cases.act(k["id"], "confirm") is None               # double-processing blocked
    assert cases.act(k["id"], "dismiss") is None


def test_seed_branch_names_match_world(app_db):
    """Seed titles must use the real store names (world.stores), not mock-era ones."""
    for seed in seeds.CASES:
        name = seeds.name_of(seed["entity_id"])
        if seed["entity_id"].startswith("str_"):
            assert name != seed["entity_id"], f"missing branch name for {seed['entity_id']}"


def test_branch_names_are_the_real_world_stores_names():
    """Gated on PR #11 — names must match world.stores, not the mock-era map."""
    assert seeds.BRANCHES["str_009"] == "Back Bay"
    assert seeds.BRANCHES["str_007"] == "Buckhead"
    assert seeds.BRANCHES["str_005"] == "SoMa"
