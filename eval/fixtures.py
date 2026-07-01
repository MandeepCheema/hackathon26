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
    {"duty":"loss", "entity":"stf_009_6", "status":"clear"},                # role=TRAINEE (hired 2026-06-18) -> honest outlier, do-not-flag
    {"duty":"loss", "entity":"str_004",   "status":"store_wide_clear"},     # 8/8 staff elevated -> store-wide POS outage, not theft
]
