# tests/test_settlement_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/settlement.sql").read_text() if pathlib.Path("agent/duties/settlement.sql").exists() else ""
@pytest.mark.integration
def test_finds_the_seven_unexplained_shortfalls():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"settle")
    keys={(r["store_id"],r["business_date"]) for r in rows}
    assert ("str_007","2026-04-12") in keys
    assert len(rows)==7
    # the three adjustment-explained decoys must be EXCLUDED
    for decoy in (("str_008","2026-03-02"),("str_010","2026-03-16"),("str_010","2026-03-17")):
        assert decoy not in keys
