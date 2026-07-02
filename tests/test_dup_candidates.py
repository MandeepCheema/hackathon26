# tests/test_dup_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/duplicate_payment.sql").read_text() if pathlib.Path("agent/duties/duplicate_payment.sql").exists() else ""
@pytest.mark.integration
def test_finds_reused_number_dup_excludes_recurring_and_diff_amount():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"dup")
    invs={r["invoice_id"] for r in rows}
    # the ONE real dup: INV-4493 reused number, same $40, both paid
    assert "inv_00093" in invs
    # decoys stay out: 55 recurring same-amount distinct-number payments; meat INV-4471 diff amounts
    assert "inv_00285" not in invs and "inv_00071" not in invs
    assert len(rows)==1
