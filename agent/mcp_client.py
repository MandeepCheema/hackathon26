import json, urllib.request

class MCPClient:
    def __init__(self, url, token):
        self.url, self.token, self.sid = url, token, None
        self._init()
    def _post(self, method, params=None):
        body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or {}}).encode()
        h = {"Content-Type":"application/json","Accept":"application/json, text/event-stream",
             "Authorization":"Bearer "+self.token}
        if self.sid: h["mcp-session-id"] = self.sid
        r = urllib.request.urlopen(urllib.request.Request(self.url, data=body, headers=h, method="POST"), timeout=45)
        raw = r.read().decode()
        if "data:" in raw:
            for ln in raw.splitlines():
                if ln.startswith("data:"): raw = ln[5:].strip(); break
        if not self.sid: self.sid = r.headers.get("mcp-session-id")
        return json.loads(raw)
    def _init(self):
        self._post("initialize", {"protocolVersion":"2024-11-05","capabilities":{},
                                  "clientInfo":{"name":"penny","version":"0.1"}})
    def list_tools(self):
        return self._post("tools/list", {}).get("result", {}).get("tools", [])
    def call(self, name, args):
        return self._post("tools/call", {"name":name, "arguments":args}).get("result", {})
    def run_sql(self, query, purpose=""):
        res = self.call("run_sql", {"query":query, "purpose":purpose})
        content = res.get("content", [])
        text = content[0].get("text","[]") if content else "[]"
        parsed = json.loads(text) if text.strip().startswith(("[","{")) else text
        # Server returns {"ok": true, "row_count": N, "rows": [...]} — unwrap,
        # but NEVER swallow a failure: an error shown to the agent is fixable
        # (e.g. missing `world.` schema prefix); a silent [] reads as "no data".
        if isinstance(parsed, dict):
            if parsed.get("ok") is False or "error" in parsed:
                return {"sql_error": parsed.get("error", parsed),
                        "hint": "Tables live in the `world` schema — e.g. world.stores, world.fin_cash_counts."}
            if "rows" in parsed:
                return parsed["rows"]
        return parsed
