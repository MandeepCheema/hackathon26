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
