from eval.run_eval import score, normalize

def test_normalize_maps_tools():
    subs = [{"tool":"submit_cash_variance","args":{"store_id":"str_009","status":"pattern_short"}},
            {"tool":"submit_loss_flag","args":{"staff_id":"stf_009_6","risk_level":"refer_investigation"}}]
    n = normalize(subs)
    assert {"duty":"cash","entity":"str_009","status":"pattern_short"} in n
    assert {"duty":"loss","entity":"stf_009_6","status":"refer_investigation"} in n

def test_perfect_match():
    exp = [{"duty":"cash","entity":"str_009","status":"pattern_short"}]
    sub = [{"duty":"cash","entity":"str_009","status":"pattern_short"}]
    s = score(sub, exp)
    assert s["precision"]==1.0 and s["recall"]==1.0 and s["f1"]==1.0

def test_false_alarm_lowers_precision():
    exp = [{"duty":"cash","entity":"str_009","status":"pattern_short"}]
    sub = [{"duty":"cash","entity":"str_009","status":"pattern_short"},
           {"duty":"cash","entity":"str_002","status":"pattern_short"}]  # str_002 is NOT a real short
    s = score(sub, exp)
    assert s["false_alarms"]==1 and s["precision"] < 1.0

def test_miss_lowers_recall():
    exp = [{"duty":"cash","entity":"str_009","status":"pattern_short"},
           {"duty":"cash","entity":"str_003","status":"pattern_short"}]
    sub = [{"duty":"cash","entity":"str_009","status":"pattern_short"}]
    s = score(sub, exp)
    assert s["recall"]==0.5

def test_cleared_submissions_are_not_flags():
    exp = [{"duty":"cash","entity":"str_009","status":"pattern_short"}]
    sub = [{"duty":"cash","entity":"str_009","status":"pattern_short"},
           {"duty":"cash","entity":"str_002","status":"balanced"}]  # balanced = cleared, not a flag
    s = score(sub, exp)
    assert s["false_alarms"]==0 and s["precision"]==1.0


# --- v2 new tool normalization tests ---

def test_normalize_submit_match_exception():
    subs = [{"tool":"submit_match_exception","args":{
        "po_id":"po_001","po_line_id":"pol_00039",
        "exception_type":"over_billed_qty","amount_cents":14400,"note":"test"}}]
    n = normalize(subs)
    assert {"duty":"threeway","entity":"pol_00039","status":"over_billed_qty"} in n


def test_normalize_submit_settlement():
    subs = [{"tool":"submit_settlement","args":{
        "store_id":"str_007","business_date":"2026-04-12","status":"shortfall",
        "register_card_cents":100000,"expected_fee_cents":2500,
        "deposit_cents":97000,"missing_cents":500,"note":"test"}}]
    n = normalize(subs)
    assert {"duty":"settlement","entity":"str_007:2026-04-12","status":"shortfall"} in n


def test_normalize_submit_duplicate_payment_maps_correctly():
    """submit_duplicate_payment normalizes to duty=dup, status=duplicate."""
    from eval.run_eval import REAL_POSITIVE
    subs = [{"tool":"submit_duplicate_payment","args":{
        "supplier_id":"sup_001","invoice_id":"inv_999",
        "duplicate_of_invoice_id":"inv_001","amount_cents":50000}}]
    n = normalize(subs)
    assert n == [{"duty":"dup","entity":"inv_999","status":"duplicate"}]
    # 'duplicate' is in REAL_POSITIVE so any false submission counts against precision
    assert "duplicate" in REAL_POSITIVE


def test_normalize_submit_duplicate_payment_false_alarm_score():
    subs_norm = [{"duty":"dup","entity":"inv_999","status":"duplicate"}]
    s = score(subs_norm, [])  # no real positives in expected
    assert s["false_alarms"] == 1
    assert s["tp"] == 0
    assert s["precision"] == 0.0


def test_normalize_submit_cogs_within_tolerance_not_false_alarm():
    """submit_cogs_variance with status='within_tolerance' is NOT a real positive → not a false alarm."""
    from eval.run_eval import REAL_POSITIVE
    subs = [{"tool":"submit_cogs_variance","args":{
        "store_id":"str_001","status":"within_tolerance",
        "cogs_pct":12.5,"note":"sparse purchasing data"}}]
    n = normalize(subs)
    assert n == [{"duty":"cogs","entity":"str_001","status":"within_tolerance"}]
    assert "within_tolerance" not in REAL_POSITIVE
    s = score(n, [])
    assert s["false_alarms"] == 0
