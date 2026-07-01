import os, pytest
from agent.mcp_client import MCPClient

@pytest.mark.integration
def test_lists_expected_tools():
    c = MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"])
    names = {t["name"] for t in c.list_tools()}
    assert {"run_sql", "submit_cash_variance", "submit_loss_flag"} <= names

@pytest.mark.integration
def test_run_sql_reads_stores():
    c = MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"])
    rows = c.run_sql("select count(*) as n from world.stores", "count stores")
    assert rows[0]["n"] >= 10
