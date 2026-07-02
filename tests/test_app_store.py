"""app.store — case state machine, KPI snapshot math, turns, ledger."""


def _mk(store, **over):
    fields = dict(case_key=over.pop("case_key", "d:e:1"), duty="cash-over-short",
                  entity_id="str_009", entity_name="Back Bay", title="t", subtitle="s",
                  amount_cents=61_000, confidence=0.9, verdict_status="pattern_short",
                  route_lane="LP", tier="approval", status="open", trace=[["run_sql", "x"]],
                  vtext="v")
    fields.update(over)
    return store.create_case(fields)


def test_case_lifecycle_and_snapshot(app_db):
    store = app_db
    k = _mk(store)
    assert k["status"] == "open" and k["trace"] == [["run_sql", "x"]]

    s = store.snapshot()
    assert s["flagged"] == 1 and s["exposure_cents"] == 61_000 and s["cleared"] == 0

    store.set_case_status(k["id"], "routed")
    assert store.snapshot()["flagged"] == 1          # routed still counts as flagged/exposure

    store.set_case_status(k["id"], "dismissed")
    s = store.snapshot()
    assert s["flagged"] == 0 and s["exposure_cents"] == 0 and s["cleared"] == 1


def test_open_case_dedupe_guard(app_db):
    store = app_db
    _mk(store)
    assert store.has_open_case("cash-over-short", "str_009")
    assert not store.has_open_case("cash-over-short", "str_001")


def test_turns_and_ledger(app_db):
    store = app_db
    store.add_turn("s1", "user", "q1")
    store.add_turn("s1", "penny", "a1")
    store.add_turn("s2", "user", "other session")
    turns = store.recent_turns("s1")
    assert [t["role"] for t in turns] == ["user", "penny"]

    _mk(store, case_key="d:e:2")
    ledger = store.verdict_ledger()
    assert ledger and ledger[0]["verdict_status"] == "pattern_short"


def test_stats_bump_floor(app_db):
    store = app_db
    store.bump(scanned=3, investigating=1)
    store.bump(investigating=-5)                      # must clamp at 0, not go negative
    s = store.snapshot()
    assert s["scanned"] == 3 and s["investigating"] == 0
