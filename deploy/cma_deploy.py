"""Assemble and deploy Penny as a Claude Managed Agent (CMA).

Reads agent/agent.yaml + agent/skills/* and emits the `ant beta:agents create`
(or update) invocation. There is no yaml->CMA converter — this script IS ours.

Requires (gitignored .env):
  ANTHROPIC_API_KEY  — the PARTICIPANT workspace key (never the judge key)
  MCCTX_MCP_URL / MCP_AUTH_TOKEN — the company MCP

Usage:
  python -m deploy.cma_deploy --dry-run          # print the payload, deploy nothing
  python -m deploy.cma_deploy                    # create -> prints AGENT_ID + VERSION
  python -m deploy.cma_deploy --update AGENT_ID --version N
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).parent.parent
SKILLS_DIR = ROOT / "agent" / "skills"


def build_payload():
    cfg = yaml.safe_load((ROOT / "agent" / "agent.yaml").read_text())
    mcp_url = os.environ["MCCTX_MCP_URL"]
    mcp_token = os.environ["MCP_AUTH_TOKEN"]

    # Skills: CMA takes name+content; duty SQL is inlined into each skill so the
    # deployed agent needs no filesystem.
    skills = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        md = skill_dir / "SKILL.md"
        if not md.exists():
            continue
        content = md.read_text()
        # Inline any referenced duty SQL (agent/duties/x.sql) so it travels with the skill.
        for sql_path in sorted((ROOT / "agent" / "duties").glob("*.sql")):
            ref = f"agent/duties/{sql_path.name}"
            if ref in content:
                content += f"\n\n## Candidate SQL ({sql_path.name}) — run this via run_sql\n```sql\n{sql_path.read_text()}\n```\n"
        skills.append({"name": skill_dir.name, "content": content})

    return {
        "name": "Penny — Controls Copilot",
        "model": {"id": cfg["model"]},
        "system": cfg["system"],
        "mcp_servers": [{
            "name": "mccontext",
            "url": mcp_url,
            "authorization_token": mcp_token,
        }],
        "skills": skills,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update", metavar="AGENT_ID")
    ap.add_argument("--version", type=int)
    args = ap.parse_args()

    payload = build_payload()
    if args.dry_run:
        redacted = json.loads(json.dumps(payload))
        redacted["mcp_servers"][0]["authorization_token"] = "***"
        print(json.dumps(redacted, indent=2)[:4000])
        print(f"\n[dry-run] system={len(payload['system'])} chars, skills={[s['name'] for s in payload['skills']]}")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY (participant workspace key) not set — load .env first.")

    cmd = ["ant", "beta:agents", "update" if args.update else "create", "--format", "json"]
    if args.update:
        cmd += ["--agent-id", args.update, "--version", str(args.version)]
    cmd += ["--name", payload["name"],
            "--model", json.dumps(payload["model"]),
            "--system", payload["system"],
            "--mcp-servers", json.dumps(payload["mcp_servers"]),
            "--skills", json.dumps(payload["skills"])]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        # ant CLI flag names can drift — print stderr so the operator can adjust fast.
        sys.exit(f"ant failed:\n{out.stderr}")
    res = json.loads(out.stdout)
    print(f"AGENT_ID={res.get('id')}\nAGENT_VERSION={res.get('version')}")
    print("Register this id on the platform Deploy page, then Run (spends a life).")


if __name__ == "__main__":
    main()
