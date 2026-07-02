"""Seed cases + scripted answers for the simulated backend — the real cases
from the world-DB probes, mirroring mock/penny-console-v2.html."""

# Real names from world.stores (verified 2 Jul; "McContext " prefix dropped for UI)
BRANCHES = {
    "str_001": "Lincoln Park", "str_002": "Midtown", "str_003": "Wicker Park",
    "str_004": "River North", "str_005": "SoMa", "str_006": "Capitol Hill",
    "str_007": "Buckhead", "str_008": "Galleria", "str_009": "Back Bay", "str_010": "LoDo",
}
SUPPLIERS = {
    "sup_bev": "FizzWorks Beverages", "sup_meat": "Prime Meats Co", "sup_dairy": "DairyBest",
    "sup_produce": "Green Valley Produce", "sup_bake": "Crust & Co", "sup_pkg": "BoxCo Packaging",
}


def name_of(entity_id: str) -> str:
    return BRANCHES.get(entity_id) or SUPPLIERS.get(entity_id) or entity_id


CASES = [
    dict(duty="cash-over-short", entity_id="str_009", title="Cash pattern-short — Back Bay",
         subtitle="pattern_short · 14 days · tight +$43/day", amount_cents=61_000, confidence=0.91,
         verdict="flag", verdict_status="pattern_short", tier="approval",
         route_lane="Loss-Prevention · Regional Mgr",
         trace=[["run_sql(cash bias)", "+$43.57/day, sd $11, 14d, net $610, t=−3.8"],
                [None, "one-directional & tight — not counting noise"],
                [None, "corroborates high-void cashier stf_009_6, same store"]],
         vtext="<b>pattern_short.</b> Persistent one-till bias at Back Bay; recorded via submit_cash_variance."),
    dict(duty="loss-prevention", entity_id="stf_009_6", title="High-void cashier — stf_009_6",
         subtitle="void_rate 0.61 vs 0.17 peer · Back Bay", amount_cents=0, confidence=0.86,
         verdict="flag", verdict_status="refer_investigation", tier="approval",
         route_lane="Loss-Prevention · Regional Mgr",
         trace=[["run_sql(void rates)", "0.61 vs 0.17 peer baseline (z=3.6)"],
                [None, "not a trainee/manager; one shift"],
                [None, "chains to the Back Bay cash short"]],
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
    dict(duty="settlement", entity_id="str_007", title="Deposit shortfall — Buckhead",
         subtitle="missing $184 after fees · Jun 28", amount_cents=18_400, confidence=0.78,
         verdict="flag", verdict_status="shortfall", tier="1-click", route_lane="Controller review",
         trace=[["run_sql(settlement)", "card $2,612 − expected fee $59 = $2,553; deposited $2,369"],
                [None, "no refund/chargeback/timing explains the gap"],
                [None, "recorded via submit_settlement"]],
         vtext="<b>shortfall.</b> $184 unexplained after fee model; one store-day."),
    dict(duty="loss-prevention", entity_id="str_004", title="Store-wide voids — River North",
         subtitle="spike across ALL cashiers", amount_cents=0, confidence=0.90,
         verdict="clear", verdict_status="clear", tier=None, route_lane=None,
         trace=[["run_sql(void rates)", "spike across every cashier, not one person"],
                [None, "store-level POS outage — a decoy"]],
         vtext="<b>clear.</b> Not a person; stated in answer, not submitted (rubric: non-clear only)."),
    dict(duty="cogs-leakage", entity_id="str_002", title="Food-cost drift — Midtown",
         subtitle="within tolerance vs target %", amount_cents=0, confidence=0.84,
         verdict="clear", verdict_status="within_tolerance", tier=None, route_lane=None,
         trace=[["run_sql(cogs)", "actual vs theoretical within materiality"],
                [None, "explained by contracted price change (cheese +3.7%)"]],
         vtext="<b>within_tolerance.</b> Contracted price move, not leakage; recorded."),
    dict(duty="settlement", entity_id="str_008", title="Deposit shortfall — Galleria",
         subtitle="missing $97 after fees · Jun 30", amount_cents=9_700, confidence=0.71,
         verdict="flag", verdict_status="shortfall", tier="1-click", route_lane="Controller review",
         trace=[["run_sql(settlement)", "card $1,988 − fee $45 = $1,943; deposited $1,846"],
                [None, "no refund/chargeback logged for the gap"]],
         vtext="<b>shortfall.</b> $97 unexplained after the fee model; one store-day."),
    dict(duty="three-way-match", entity_id="po_00274", title="Over-billed qty — Green Valley",
         subtitle="billed 60, received 54 · lettuce", amount_cents=9_600, confidence=0.83,
         verdict="flag", verdict_status="over_billed_qty", tier="1-click", route_lane="Supplier Relations",
         trace=[["run_sql(3-way match)", "billed_qty 60 vs received 54 @ $1.60"],
                [None, "no credit memo covers the 6-unit gap"]],
         vtext="<b>over_billed_qty.</b> Billed above goods receipt; recoverable."),
    dict(duty="duplicate-payment", entity_id="sup_dairy", title="Possible duplicate — DairyBest",
         subtitle="$88 twice · 3 days apart · same PO", amount_cents=8_800, confidence=0.58,
         verdict="flag", verdict_status="duplicate", tier="approval", route_lane="Accounts Payable",
         trace=[["run_sql(payments)", "two $88 ACH refs, 3 days apart, one invoice"],
                [None, "low confidence — could be a re-issued transfer; human confirm"]],
         vtext="<b>duplicate (low confidence).</b> Uncovered repeat pending AP review."),
    dict(duty="loss-prevention", entity_id="stf_006_4", title="Discount pattern — stf_006_4",
         subtitle="discount rate 2.4× peers · Capitol Hill", amount_cents=0, confidence=0.66,
         verdict="flag", verdict_status="refer_investigation", tier="approval", route_lane="Loss-Prevention · Regional Mgr",
         trace=[["run_sql(discounts)", "2.4× peer discount rate, single till"],
                [None, "not explained by promos active that week"]],
         vtext="<b>refer_investigation.</b> Outlier discounting, one operator."),
    dict(duty="cogs-leakage", entity_id="str_010", title="Margin drift — LoDo",
         subtitle="food cost 2.1pt over target · June", amount_cents=31_000, confidence=0.69,
         verdict="flag", verdict_status="leakage", tier="1-click", route_lane="Controller review",
         trace=[["run_sql(cogs)", "actual 31.1% vs theoretical 29.0%"],
                [None, "not explained by contracted price moves"]],
         vtext="<b>leakage.</b> Unexplained 2.1pt margin drift at LoDo."),
    dict(duty="settlement", entity_id="str_001", title="Deposit reconciled — Lincoln Park",
         subtitle="T+2 timing, fees match model", amount_cents=0, confidence=0.94,
         verdict="clear", verdict_status="reconciled", tier=None, route_lane=None,
         trace=[["run_sql(settlement)", "gap fully explained by weekend T+2 timing"]],
         vtext="<b>reconciled.</b> Timing, not money — cleared."),
    dict(duty="duplicate-payment", entity_id="sup_pkg", title="Recurring payments — BoxCo",
         subtitle="monthly same-amount lease look-alikes", amount_cents=0, confidence=0.92,
         verdict="clear", verdict_status="clear", tier=None, route_lane=None,
         trace=[["run_sql(payments)", "distinct invoices, monthly cadence — contract billing"]],
         vtext="<b>clear.</b> Contracted recurring charge, not a duplicate."),
    dict(duty="loss-prevention", entity_id="stf_003_7", title="New-hire voids — stf_003_7",
         subtitle="high voids · 2nd week · Wicker Park", amount_cents=0, confidence=0.88,
         verdict="clear", verdict_status="clear", tier=None, route_lane=None,
         trace=[["run_sql(void rates)", "voids high but small-$, decline by day — training curve"],
                [None, "honest outlier per rubric: do NOT refer trainees"]],
         vtext="<b>clear.</b> Trainee learning curve, not skimming."),
    dict(duty="cash-over-short", entity_id="str_003", title="Balanced tills — Wicker Park",
         subtitle="92 days, no directional bias", amount_cents=0, confidence=0.95,
         verdict="clear", verdict_status="balanced", tier=None, route_lane=None,
         trace=[["run_sql(cash bias)", "net −$4 over 92 days, sd $11 — noise"]],
         vtext="<b>balanced.</b> Rounding-level noise; nothing to chase."),
    dict(duty="duplicate-payment", entity_id="sup_meat", title="Recurring payments — Prime Meats",
         subtitle="55 same-amount look-alikes", amount_cents=0, confidence=0.93,
         verdict="clear", verdict_status="clear", tier=None, route_lane=None,
         trace=[["run_sql(payments)", "55 same-amount payments, distinct invoices, weekly cadence"],
                [None, "legitimate recurring order"]],
         vtext="<b>clear.</b> Distinct invoices + cadence — flagging = crying wolf."),
]

ANSWERS = {
    "Why is Back Bay short on cash?": dict(
        steps=[["read_skill(cash-over-short)", "loading the duty playbook"],
               ["run_sql(cash bias)", "expected = cash sales − paid-outs, per day, 92 days"],
               [None, "Back Bay: +$43.57/day over 14 days, sd $11 — tight, one-directional"],
               [None, "cross-check: cashier stf_009_6 voids at 0.61 vs 0.17 peer — same store, same shifts"]],
        kind="flag",
        answer="<b>Back Bay is pattern-short: ~$610 over 14 days, and it isn’t noise.</b> The bias is tight "
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
               [None, "3 real: Back Bay cash short, FizzWorks duplicate, Buckhead deposit shortfall"],
               [None, "2 decoys cleared: River North store-wide voids (POS outage), Prime Meats recurring payments"]],
        kind="clr",
        answer="<b>Three real issues, two decoys cleared.</b> Exposure ≈ $1,214: Back Bay pattern-short ($610, "
               "corroborated by a high-void cashier), the FizzWorks duplicate ($420), and a Buckhead settlement "
               "shortfall ($184). Both look-alike patterns were cleared with reasons — no false alarms. All three "
               "flags are in the rail, ready to process."),
}

FALLBACK = dict(
    steps=[["run_sql(explore)", "this build is on the simulated backend (PENNY_BACKEND=sim)"],
           [None, "set PENNY_BACKEND=agent to answer anything via the real Penny agent"]],
    kind="clr",
    answer="<b>Simulated backend.</b> The three suggested questions and the flagged cases are fully scripted — "
           "the real agent runs behind the same interface with PENNY_BACKEND=agent (see app/README.md).")
