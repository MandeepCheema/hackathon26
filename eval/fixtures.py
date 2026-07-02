# Ground-truth verdicts — VERIFIED against world.* data (not hand-guessed).
# Corrected after the v1 eval: the agent's reasoning beat the original naive labels, and a direct
# DB check (world.fin_staff.role + a clean peer baseline excluding str_004's store-wide outage)
# confirmed the agent, not the original fixtures. Corrections are data-verified, NOT massaged to pass.
EXPECTED = [
    # Cash — persistent directional short (t <= -3), expected = cash_sales - paid_outs:
    {"duty":"cash", "entity":"str_009",   "status":"pattern_short"},   # net -$610, t=-3.8
    {"duty":"cash", "entity":"str_003",   "status":"pattern_short"},   # net -$569, t=-3.8

    # Loss prevention — individual skimmer vs peer baseline, honest outliers cleared:
    {"duty":"loss", "entity":"stf_006_3", "status":"refer_investigation"},  # role=cashier, z=3.62, 2-of-8 at store = individual
    {"duty":"loss", "entity":"stf_006_5", "status":"refer_investigation"},  # role=cashier, z=2.94, individual
    {"duty":"loss", "entity":"stf_007_4", "status":"refer_investigation"},  # 15/15 of store's no_sale opens = individual (no_sale_opens)
    {"duty":"loss", "entity":"stf_008_2", "status":"refer_investigation"},  # 24 discounts vs peers <=1 (discount_abuse)
    {"duty":"loss", "entity":"stf_009_6", "status":"clear"},                # role=TRAINEE (hired 2026-06-18) -> honest outlier, do-not-flag
    {"duty":"loss", "entity":"stf_007_8", "status":"clear"},                # MANAGER, 18 refunds to 18 DISTINCT cards = refund desk duty (decoy)
    {"duty":"loss", "entity":"str_004",   "status":"store_wide_clear"},     # 8/8 staff elevated -> store-wide POS outage, not theft

    # three-way-match (6 real exceptions — pol_00150 is a TRAP: its $64.80 over-billing is
    # exactly covered by credit memo memo_00001 on inv_00150 → explained, do NOT flag):
    {"duty":"threeway","entity":"pol_00039","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00092","status":"price_variance"},
    {"duty":"threeway","entity":"pol_00222","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00221","status":"price_variance"},
    {"duty":"threeway","entity":"pol_00151","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00220","status":"over_billed_qty"},
    # settlement (7 real shortfalls — three TRAPS excluded, fully explained by logged
    # fin_settlement_adjustments: str_008 03-02 terminal_reset $180, str_010 03-16 refund
    # batch $220, str_010 03-17 chargeback $150 → residual 0, do NOT flag):
    {"duty":"settlement","entity":"str_007:2026-04-12","status":"shortfall"},
    {"duty":"settlement","entity":"str_004:2026-03-27","status":"shortfall"},
    {"duty":"settlement","entity":"str_008:2026-03-05","status":"shortfall"},
    {"duty":"settlement","entity":"str_005:2026-05-02","status":"shortfall"},
    {"duty":"settlement","entity":"str_007:2026-04-10","status":"shortfall"},
    {"duty":"settlement","entity":"str_010:2026-03-19","status":"shortfall"},
    {"duty":"settlement","entity":"str_007:2026-04-08","status":"shortfall"},
    # duplicate-payment: NO positive fixtures — precision test (agent must flag none;
    # inv_00295 'voided — corrected & re-issued' + memo_00002 is the engineered decoy).
    # cogs-leakage: NO positive fixtures — abstention test (agent must submit within_tolerance).
]
