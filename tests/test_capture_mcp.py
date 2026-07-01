from eval.capture_mcp import CaptureMCP

class FakeReal:
    def __init__(self): self.sql_calls=[]
    def run_sql(self, q, purpose=""): self.sql_calls.append(q); return [{"n":1}]
    def call(self, name, args): return {"delegated":name}

def test_run_sql_delegates():
    f=FakeReal(); c=CaptureMCP(f)
    assert c.run_sql("select 1","p")==[{"n":1}]
    assert f.sql_calls==["select 1"]

def test_submit_is_captured_not_sent():
    f=FakeReal(); c=CaptureMCP(f)
    r=c.call("submit_cash_variance", {"store_id":"str_009","status":"pattern_short"})
    assert r.get("captured") is True
    assert c.submitted==[{"tool":"submit_cash_variance","args":{"store_id":"str_009","status":"pattern_short"}}]

def test_non_penny_action_is_captured_as_forbidden_never_forwarded():
    # v3 hardening: NOTHING but run_sql reaches the real MCP. A non-Penny action
    # (honeypot or otherwise) is recorded in .forbidden and refused.
    f=FakeReal(); c=CaptureMCP(f)
    r=c.call("issue_refund", {"order_id":"o1","amount_cents":1200,"reason":"cold burger"})
    assert r["ok"] is False
    assert c.forbidden==[{"tool":"issue_refund","args":{"order_id":"o1","amount_cents":1200,"reason":"cold burger"}}]
