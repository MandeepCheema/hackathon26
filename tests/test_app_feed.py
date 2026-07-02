"""app.feed — finance_stream row → ticker event mapping, command assembly, enable logic."""
from app import feed


def test_register_txn_maps_to_ticker():
    ev = feed._event("fin_register_txns", {
        "store_id": "str_009", "txn_type": "sale", "amount_cents": 1234,
        "ts": "2026-07-02T14:03:22+00:00"})
    from app import seeds
    assert ev["type"] == "ticker" and ev["branch"] == seeds.BRANCHES["str_009"]
    assert ev["txn"] == "sale" and ev["amount_cents"] == 1234
    assert isinstance(ev["ts"], float)


def test_supplier_rows_map_with_real_names():
    inv = feed._event("fin_invoices", {"supplier_id": "sup_bev", "status": "approved",
                                       "total_cents": 42000, "invoiced_at": "2026-07-02T10:00:00+00:00"})
    assert inv["branch"] == "FizzWorks Beverages" and "invoice" in inv["txn"]
    pay = feed._event("fin_payments_out", {"supplier_id": "sup_meat", "amount_cents": 9900,
                                           "paid_at": "2026-07-02T10:00:00+00:00"})
    assert pay["branch"] == "Prime Meats Co"


def test_noisy_tables_are_skipped():
    assert feed._event("fin_po_lines", {"id": "pol_1"}) is None
    assert feed._event("fin_register_totals", {"store_id": "str_001"}) is None


def test_bad_timestamp_falls_back_to_now():
    ev = feed._event("fin_register_txns", {"store_id": "str_001", "txn_type": "sale",
                                           "amount_cents": 1, "ts": "not-a-date"})
    assert isinstance(ev["ts"], float)


def test_cmd_includes_leak_injection_and_stdout_sink():
    cmd = " ".join(feed._cmd())
    assert "--sink stdout" in cmd and "--inject-leak all" in cmd and "--leak-log" in cmd


def test_enabled_logic(monkeypatch):
    monkeypatch.delenv("WORLD_PG_URI", raising=False)
    monkeypatch.setenv("FEED", "auto")
    assert not feed.enabled()
    monkeypatch.setenv("WORLD_PG_URI", "postgresql://x")
    assert feed.enabled()
    monkeypatch.setenv("FEED", "sim")
    assert not feed.enabled()                       # explicit off wins
    monkeypatch.delenv("WORLD_PG_URI", raising=False)
    monkeypatch.setenv("FEED", "stream")
    assert feed.enabled()                           # explicit on wins
