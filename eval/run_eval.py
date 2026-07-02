import sys

REAL_POSITIVE = {
    "pattern_short", "short", "refer_investigation",
    # three-way-match
    "over_billed_qty", "price_variance", "short_received",
    # duplicate-payment
    "duplicate_invoice", "unauthorized_charge", "tax_miscalc", "duplicate",
    # settlement
    "shortfall",
    # cogs-leakage
    "leakage",
}  # statuses that mean "flagged a real exception"

def normalize(submitted):
    out = []
    for s in submitted:
        a = s.get("args", {})
        if s["tool"] == "submit_cash_variance":
            out.append({"duty":"cash", "entity":a.get("store_id"), "status":a.get("status")})
        elif s["tool"] == "submit_loss_flag":
            out.append({"duty":"loss", "entity":a.get("staff_id"), "status":a.get("risk_level")})
        elif s["tool"] == "submit_match_exception":
            out.append({"duty":"threeway", "entity":a.get("po_line_id"), "status":a.get("exception_type")})
        elif s["tool"] == "submit_settlement":
            entity = f'{a.get("store_id")}:{a.get("business_date")}'
            out.append({"duty":"settlement", "entity":entity, "status":a.get("status")})
        elif s["tool"] == "submit_duplicate_payment":
            out.append({"duty":"dup", "entity":a.get("invoice_id"), "status":"duplicate"})
        elif s["tool"] == "submit_cogs_variance":
            out.append({"duty":"cogs", "entity":a.get("store_id"), "status":a.get("status")})
    # dedup: the last verdict per (duty, entity) wins — re-submits must not inflate tp/false-alarms
    last = {}
    for d in out: last[(d["duty"], d["entity"])] = d
    return list(last.values())

def score(submitted_norm, expected):
    def key(d): return (d["duty"], d["entity"], d["status"])
    real_exp = {key(e) for e in expected if e["status"] in REAL_POSITIVE}
    real_sub = [d for d in submitted_norm if d["status"] in REAL_POSITIVE]
    tp = sum(1 for d in real_sub if key(d) in real_exp)
    flagged = len(real_sub)
    false_alarms = flagged - tp
    precision = tp/flagged if flagged else 1.0
    recall = tp/len(real_exp) if real_exp else 1.0
    f1 = 2*precision*recall/(precision+recall) if (precision+recall) else 0.0
    return {"precision":round(precision,3), "recall":round(recall,3), "f1":round(f1,3),
            "false_alarms":false_alarms, "tp":tp}

def per_duty(submitted_norm, expected):
    duties = sorted({e["duty"] for e in expected} | {d["duty"] for d in submitted_norm})
    return {d: score([x for x in submitted_norm if x["duty"] == d],
                     [e for e in expected if e["duty"] == d]) for d in duties}


def main():
    import os
    from agent.auth import ensure_subscription_auth
    ensure_subscription_auth()
    from eval.fixtures import EXPECTED
    from eval.capture_mcp import CaptureMCP
    from agent.mcp_client import MCPClient
    from agent.run_scan import scan_all
    client = CaptureMCP(MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"]))
    scan_all(client)                         # agent investigates live, submits captured into client
    norm = normalize(client.submitted)
    s = score(norm, EXPECTED)
    print("SUBMISSIONS:")
    for x in norm: print("  ", x)
    if client.forbidden: print("FORBIDDEN CALLS (scope-fence breaches):", client.forbidden)
    if client.guardrails: print("GUARDRAIL BLOCKS (agent retried):", [g["message"][:80] for g in client.guardrails])
    print("PER-DUTY:")
    for d, ds in per_duty(norm, EXPECTED).items():
        print(f"  {d:11s} P={ds['precision']:.2f} R={ds['recall']:.2f} F1={ds['f1']:.2f} "
              f"tp={ds['tp']} false_alarms={ds['false_alarms']}")
    print("SCORECARD:", s, f"(sql_calls={client.sql_calls})")
    # missed real positives, named — the actionable part
    def key(d): return (d["duty"], d["entity"], d["status"])
    real_exp = {key(e) for e in EXPECTED if e["status"] in REAL_POSITIVE}
    got = {key(d) for d in norm}
    missed = real_exp - got
    extra = [d for d in norm if d["status"] in REAL_POSITIVE and key(d) not in real_exp]
    if missed: print("MISSED:", sorted(missed))
    if extra: print("FALSE ALARMS:", extra)
    if s["f1"] < 0.8:
        print("GATE FAIL: F1 < 0.8 — do NOT spend a bench life yet."); sys.exit(1)
    print("GATE PASS.")

if __name__ == "__main__":
    main()
