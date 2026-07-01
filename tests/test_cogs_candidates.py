# tests/test_cogs_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/cogs_leakage.sql").read_text() if pathlib.Path("agent/duties/cogs_leakage.sql").exists() else ""
@pytest.mark.integration
def test_purchasing_coverage_is_sparse():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows={r["store_id"]:r for r in c.run_sql(SQL,"cogs")}
    # cogs% is implausibly low because purchasing/receipts data is too sparse to be a real ratio
    assert all(r["cogs_pct"] < 20 for r in rows.values())
