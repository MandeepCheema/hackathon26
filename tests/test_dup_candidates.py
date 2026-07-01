# tests/test_dup_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/duplicate_payment.sql").read_text() if pathlib.Path("agent/duties/duplicate_payment.sql").exists() else ""
@pytest.mark.integration
def test_no_real_duplicates_in_data():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"dup")
    assert rows==[]   # the 55 recurring same-amount payments are decoys, not dups
