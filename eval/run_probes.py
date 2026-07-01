"""Run the adversarial conversational probes against the live agent.

Each probe = one fresh conversation with a fresh CaptureMCP (run_sql live + read-only;
every action captured, nothing forwarded). Verdicts come from tool-call assertions.

Usage:
    python -m eval.run_probes                # all probes
    python -m eval.run_probes direct_cash …  # only the named probes
"""
import os
import sys


def main():
    from agent.auth import ensure_subscription_auth
    ensure_subscription_auth()
    import yaml
    from agent.mcp_client import MCPClient
    from agent.sdk_loop import run_conversation
    from eval.capture_mcp import CaptureMCP
    from eval.probes import PROBES

    system = yaml.safe_load(open("agent/agent.yaml"))["system"]
    only = set(sys.argv[1:])
    probes = [p for p in PROBES if not only or p["name"] in only]

    results = []
    for probe in probes:
        print(f"\n=== PROBE {probe['name']} ===\nUSER: {probe['message']}")
        capture = CaptureMCP(MCPClient(os.environ["MCCTX_MCP_URL"], os.environ["MCP_AUTH_TOKEN"]))
        reply = run_conversation(system, probe["message"], capture, echo=True)
        ok, why = probe["check"](capture, reply)
        results.append((probe["name"], ok, why))
        print(f"--> {'PASS' if ok else 'FAIL'}: {why}")
        print(f"    tools: sql={capture.sql_calls} submitted={[s['tool'] for s in capture.submitted]} "
              f"forbidden={[f['tool'] for f in capture.forbidden]}")

    print("\n===== PROBE SCORECARD =====")
    for name, ok, why in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {why}")
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} probes passed.")
    if failed:
        print("GATE FAIL: fix before spending a bench life.")
        sys.exit(1)
    print("GATE PASS: conversational guardrails hold.")


if __name__ == "__main__":
    main()
