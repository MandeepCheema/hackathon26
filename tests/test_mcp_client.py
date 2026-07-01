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


def test_run_sql_surfaces_errors_not_empty():
    """A failed query must return a visible sql_error, never a silent [] (probe-1 regression)."""
    c = MCPClient.__new__(MCPClient)  # skip network init
    c.call = lambda name, args: {"content": [{"type": "text",
        "text": '{"ok": false, "error": "relation \\"stores\\" does not exist"}'}]}
    out = c.run_sql("select count(*) from stores")
    assert "sql_error" in out and "world" in out["hint"]
