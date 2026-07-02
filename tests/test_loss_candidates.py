import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL = pathlib.Path("agent/duties/loss_prevention.sql").read_text() if pathlib.Path("agent/duties/loss_prevention.sql").exists() else ""

@pytest.mark.integration
def test_stf009_6_is_high_void_outlier():
    c = MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"])
    rows = {r["staff_id"]: r for r in c.run_sql(SQL, "loss candidates")}
    assert rows["stf_009_6"]["void_rate"] > 0.5
    assert rows["stf_009_6"]["z_void"] > 1.5  # well above peer mean

@pytest.mark.integration
def test_str004_reads_as_store_wide():
    c = MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"])
    rows = [r for r in c.run_sql(SQL, "loss candidates") if r["store_id"]=="str_004"]
    # more than one str_004 staffer is a high-void outlier → store-wide signal, not one bad actor
    highs = [r for r in rows if r["void_rate"] > 0.45]
    assert len(highs) >= 3

@pytest.mark.integration
def test_all_five_signals_have_zscores():
    c = MCPClient(os.environ["MCCTX_MCP_URLD".replace("D","")], os.environ["MCP_AUTH_TOKEN"])
    rows = {r["staff_id"]: r for r in c.run_sql(SQL, "loss candidates")}
    for col in ("z_void", "z_refund_card", "z_no_sale", "z_discount"):
        assert col in rows["stf_009_6"]
    assert rows["stf_007_4"]["z_no_sale"] > 2.5        # no-sale opener
    assert rows["stf_007_8"]["z_refund_card"] > 2.5    # manager refund decoy (surfaced, then cleared by role+cards)
    assert rows["stf_008_2"]["z_discount"] > 2.5       # discount abuser
