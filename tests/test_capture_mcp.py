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

def test_non_submit_delegates():
    f=FakeReal(); c=CaptureMCP(f)
    assert c.call("run_sql", {"query":"x"})=={"delegated":"run_sql"}
