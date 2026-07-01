import os, pathlib, pytest
from agent.mcp_client import MCPClient

SQL = pathlib.Path("agent/duties/cash_over_short.sql").read_text() if pathlib.Path("agent/duties/cash_over_short.sql").exists() else ""

@pytest.mark.integration
def test_str009_and_str003_are_persistent_shorts():
    c = MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"])
    rows = {r["store_id"]: r for r in c.run_sql(SQL, "cash candidates")}
    # both real shorts: negative net and strongly significant (t <= -3)
    assert rows["str_009"]["net_cents"] < 0 and rows["str_009"]["tstat"] <= -3
    assert rows["str_003"]["net_cents"] < 0 and rows["str_003"]["tstat"] <= -3

@pytest.mark.integration
def test_noise_store_not_significant():
    c = MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"])
    rows = {r["store_id"]: r for r in c.run_sql(SQL, "cash candidates")}
    # str_002 is ~$0 net rounding noise → |t| small
    assert abs(rows["str_002"]["tstat"]) < 2
