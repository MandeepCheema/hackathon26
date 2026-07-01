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
    return out

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
    print("SUBMISSIONS:", norm)
    print("SCORECARD:", s)
    if s["f1"] < 0.8:
        print("GATE FAIL: F1 < 0.8 — do NOT spend a bench life yet."); sys.exit(1)
    print("GATE PASS.")

if __name__ == "__main__":
    main()
