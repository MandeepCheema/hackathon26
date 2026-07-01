class CaptureMCP:
    """Delegate run_sql to a real MCPClient (live, read-only); capture submit_* instead of sending."""
    def __init__(self, real):
        self.real = real
        self.submitted = []
    def run_sql(self, query, purpose=""):
        return self.real.run_sql(query, purpose)
    def call(self, name, args):
        if name.startswith("submit_"):
            self.submitted.append({"tool": name, "args": args})
            return {"ok": True, "captured": True}
        return self.real.call(name, args)
