# tests/test_policy_sql.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL = pathlib.Path("agent/duties/policy_lookup.sql").read_text() if pathlib.Path("agent/duties/policy_lookup.sql").exists() else ""
@pytest.mark.integration
def test_returns_active_policies_only():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"policies")
    ids={r["id"] for r in rows}
    assert "finpol_materiality" in ids and "pol_refund_v3" in ids   # active
    assert "pol_refund_v2" not in ids                                # retired excluded
