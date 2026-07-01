# tests/test_threeway_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/three_way_match.sql").read_text() if pathlib.Path("agent/duties/three_way_match.sql").exists() else ""
@pytest.mark.integration
def test_finds_exactly_the_seven_exceptions():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"3way")
    by={r["po_line_id"]:r["exception_type"] for r in rows}
    assert by.get("pol_00039")=="over_billed_qty"
    assert by.get("pol_00092")=="price_variance"
    assert len(rows)==7
