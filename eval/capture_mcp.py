from agent.sdk_loop import PENNY_ACTION_TOOLS

PENNY_TOOL_NAMES = {n for n, _, _ in PENNY_ACTION_TOOLS}


class CaptureMCP:
    """Delegate run_sql to a real MCPClient (live, read-only); capture EVERY action call.

    Nothing but run_sql is ever forwarded: Penny submits land in .submitted (graded),
    any non-Penny action (issue_refund, create_ticket, submit_reorder, …) lands in
    .forbidden — a scope-fence violation the probes assert against. Forwarding a
    forbidden action to the real MCP is never acceptable in dev/eval, so we don't.
    """
    def __init__(self, real):
        self.real = real
        self.submitted = []
        self.forbidden = []
        self.guardrails = []   # GR1/GR5 pre-submit refusals (recorded by sdk_loop)
        self.sql_calls = 0

    def record_guardrail(self, tool, message):
        self.guardrails.append({"tool": tool, "message": message})

    def run_sql(self, query, purpose=""):
        self.sql_calls += 1
        return self.real.run_sql(query, purpose)

    def call(self, name, args):
        if name in PENNY_TOOL_NAMES:
            self.submitted.append({"tool": name, "args": args})
            return {"ok": True, "captured": True}
        self.forbidden.append({"tool": name, "args": args})
        return {"ok": False, "error": f"'{name}' is outside Penny's duties and was NOT executed."}
