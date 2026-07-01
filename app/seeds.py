"""Seed cases + scripted answers for the simulated backend — the real cases
from the world-DB probes, mirroring mock/penny-console-v2.html."""

BRANCHES = {
    "str_001": "The Loop", "str_002": "Wicker Park", "str_003": "Lincoln Park",
    "str_004": "Logan Square", "str_005": "Hyde Park", "str_006": "River North",
    "str_007": "Pilsen", "str_008": "Lakeview", "str_009": "West Loop", "str_010": "Old Town",
}
SUPPLIERS = {
    "sup_bev": "FizzWorks Beverages", "sup_meat": "Prime Meats Co", "sup_dairy": "DairyBest",
    "sup_produce": "Green Valley Produce", "sup_bake": "Crust & Co", "sup_pkg": "BoxCo Packaging",
}


def name_of(entity_id: str) -> str:
    return BRANCHES.get(entity_id) or SUPPLIERS.get(entity_id) or entity_id


CASES = [
    dict(duty="cash-over-short", entity_id="str_009", title="Cash pattern-short — West Loop",
         subtitle="pattern_short · 14 days · tight +$43/day", amount_cents=61_000, confidence=0.91,
         verdict="flag", verdict_status="pattern_short", tier="approval",
         route_lane="Loss-Prevention · Regional Mgr",
         trace=[["run_sql(cash bias)", "+$43.57/day, sd $11, 14d, net $610, t=−3.8"],
                [None, "one-directional & tight — not counting noise"],
                [None, "corroborates high-void cashier stf_009_6, same store"]],
         vtext="<b>pattern_short.</b> Persistent one-till bias at West Loop; recorded via submit_cash_variance."),
    dict(duty="loss-prevention", entity_id="stf_009_6", title="High-void cashier — stf_009_6",
         subtitle="void_rate 0.61 vs 0.17 peer · West Loop", amount_cents=0, confidence=0.86,
         verdict="flag", verdict_status="refer_investigation", tier="approval",
         route_lane="Loss-Prevention · Regional Mgr",
         trace=[["run_sql(void rates)", "0.61 vs 0.17 peer baseline (z=3.6)"],
                [None, "not a trainee/manager; one shift"],
                [None, "chains to the West Loop cash short"]],
         vtext="<b>refer_investigation.</b> 3.6× peer void rate; recorded via submit_loss_flag."),
    dict(duty="duplicate-payment", entity_id="sup_bev", title="Duplicate payment — FizzWorks",
         subtitle="$420 twice · same week · one invoice", amount_cents=42_000, confidence=0.64,
         verdict="flag", verdict_status="duplicate", tier="approval", route_lane="Accounts Payable",
         trace=[["run_sql(payments)", "two $420 payments, same week, same store"],
                [None, "only ONE invoice covers both"],
                [None, "unlike the recurring cluster (distinct invoices)"]],
         vtext="<b>duplicate.</b> Uncovered repeat; recorded via submit_duplicate_payment."),
    dict(duty="three-way-match", entity_id="po_00311", title="Overbilling — 11 PO lines",
         subtitle="billed > received/agreed · 4 suppliers", amount_cents=40_200, confidence=0.88,
         verdict="flag", verdict_status="price_variance", tier="1-click", route_lane="Supplier Relations",
         trace=[["run_sql(3-way match)", "11 lines billed above received qty / agreed cost"],
                [None, "net $402.60 recoverable, policy-aware"],
                [None, "recorded via submit_match_exception"]],
         vtext="<b>price_variance.</b> Mechanical, high-confidence, reversible dispute."),
    dict(duty="settlement", entity_id="str_007", title="Deposit shortfall — Pilsen",
         subtitle="missing $184 after fees · Jun 28", amount_cents=18_400, confidence=0.78,
         verdict="flag", verdict_status="shortfall", tier="1-click", route_lane="Controller review",
         trace=[["run_sql(settlement)", "card $2,612 − expected fee $59 = $2,553; deposited $2,369"],
                [None, "no refund/chargeback/timing explains the gap"],
                [None, "recorded via submit_settlement"]],
         vtext="<b>shortfall.</b> $184 unexplained after fee model; one store-day."),
    dict(duty="loss-prevention", entity_id="str_004", title="Store-wide voids — Logan Square",
         subtitle="spike across ALL cashiers", amount_cents=0, confidence=0.90,
         verdict="clear", verdict_status="clear", tier=None, route_lane=None,
         trace=[["run_sql(void rates)", "spike across every cashier, not one person"],
                [None, "store-level POS outage — a decoy"]],
         vtext="<b>clear.</b> Not a person; stated in answer, not submitted (rubric: non-clear only)."),
    dict(duty="cogs-leakage", entity_id="str_002", title="Food-cost drift — Wicker Park",
         subtitle="within tolerance vs target %", amount_cents=0, confidence=0.84,
         verdict="clear", verdict_status="within_tolerance", tier=None, route_lane=None,
         trace=[["run_sql(cogs)", "actual vs theoretical within materiality"],
                [None, "explained by contracted price change (cheese +3.7%)"]],
         vtext="<b>within_tolerance.</b> Contracted price move, not leakage; recorded."),
    dict(duty="duplicate-payment", entity_id="sup_meat", title="Recurring payments — Prime Meats",
         subtitle="55 same-amount look-alikes", amount_cents=0, confidence=0.93,
         verdict="clear", verdict_status="clear", tier=None, route_lane=None,
         trace=[["run_sql(payments)", "55 same-amount payments, distinct invoices, weekly cadence"],
                [None, "legitimate recurring order"]],
         vtext="<b>clear.</b> Distinct invoices + cadence — flagging = crying wolf."),
]

ANSWERS = {
    "Why is West Loop short on cash?": dict(
        steps=[["read_skill(cash-over-short)", "loading the duty playbook"],
               ["run_sql(cash bias)", "expected = cash sales − paid-outs, per day, 92 days"],
               [None, "West Loop: +$43.57/day over 14 days, sd $11 — tight, one-directional"],
               [None, "cross-check: cashier stf_009_6 voids at 0.61 vs 0.17 peer — same store, same shifts"]],
        kind="flag",
        answer="<b>West Loop is pattern-short: ~$610 over 14 days, and it isn’t noise.</b> The bias is tight "
               "(sd ≪ mean), one-directional, and concentrated on shifts worked by stf_009_6, whose void rate is "
               "3.6× the peer baseline. I’ve recorded submit_cash_variance(pattern_short) and "
               "submit_loss_flag(refer_investigation) — the flagged case is in the rail if you want to route it now."),
    "Was the $420 FizzWorks payment a duplicate?": dict(
        steps=[["read_skill(duplicate-payment)", "loading the duty playbook"],
               ["run_sql(payments)", "FizzWorks, $420, Jun 8 — plus a 2nd $420 the same week, same store"],
               ["run_sql(invoices)", "only ONE invoice covers both payments"],
               [None, "contrast: the 55-payment recurring cluster all have distinct invoices — this one doesn’t"]],
        kind="flag",
        answer="<b>Likely a duplicate (confidence 0.64).</b> Two $420 payments to FizzWorks Beverages in one week "
               "backed by a single invoice. It’s distinct from their legitimate weekly recurring cluster. Recorded "
               "via submit_duplicate_payment; recommend AP hold + human confirm before any clawback — I don’t move money."),
    "Anything unusual in today's stream?": dict(
        steps=[["run_sql(candidate nets)", "sweeping all 6 duties over today’s watermark"],
               [None, "312 transactions scanned · 5 candidates raised"],
               [None, "3 real: West Loop cash short, FizzWorks duplicate, Pilsen deposit shortfall"],
               [None, "2 decoys cleared: Logan Square store-wide voids (POS outage), Prime Meats recurring payments"]],
        kind="clr",
        answer="<b>Three real issues, two decoys cleared.</b> Exposure ≈ $1,214: West Loop pattern-short ($610, "
               "corroborated by a high-void cashier), the FizzWorks duplicate ($420), and a Pilsen settlement "
               "shortfall ($184). Both look-alike patterns were cleared with reasons — no false alarms. All three "
               "flags are in the rail, ready to process."),
}

FALLBACK = dict(
    steps=[["run_sql(explore)", "this build is on the simulated backend (PENNY_BACKEND=sim)"],
           [None, "set PENNY_BACKEND=agent to answer anything via the real Penny agent"]],
    kind="clr",
    answer="<b>Simulated backend.</b> The three suggested questions and the flagged cases are fully scripted — "
           "the real agent runs behind the same interface with PENNY_BACKEND=agent (see app/README.md).")
