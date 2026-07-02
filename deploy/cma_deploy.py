"""Assemble and deploy Penny as a Claude Managed Agent (CMA) — ant CLI v1.13 flags.

Requires (gitignored .env): ANTHROPIC_API_KEY (PARTICIPANT workspace key),
MCCTX_MCP_URL, MCP_AUTH_TOKEN.

Usage:
  python -m deploy.cma_deploy --dry-run
  python -m deploy.cma_deploy
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
DUTIES_DIR = ROOT / "agent" / "duties"


def skills():
    out = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        md = skill_dir / "SKILL.md"
        if not md.exists():
            continue
        content = md.read_text()
        for sql_path in sorted(DUTIES_DIR.glob("*.sql")):
            ref = f"agent/duties/{sql_path.name}"
            if ref in content:
                content += (f"\n\n## Candidate SQL ({sql_path.name}) — run this VERBATIM via run_sql\n"
                            f"```sql\n{sql_path.read_text()}\n```\n")
        out.append({"type": "custom", "name": skill_dir.name, "content": content})
    return out


def build_cmd():
    cfg = yaml.safe_load((ROOT / "agent" / "agent.yaml").read_text())
    mcp = {"type": "url", "name": "mccontext", "url": os.environ["MCCTX_MCP_URL"],
           "authorization": {"type": "bearer", "token": os.environ["MCP_AUTH_TOKEN"]}}
    tool = {"type": "mcp_toolset", "mcp_server": "mccontext"}
    cmd = ["ant", "beta:agents", "create",
           "--name", "Penny — Controls Copilot",
           "--description", "McContext finance-controls agent: six duties, conversational + autonomous, evidence-first.",
           "--model", json.dumps({"id": cfg["model"]}),
           "--system", cfg["system"],
           "--mcp-server", json.dumps(mcp),
           "--tool", json.dumps(tool)]
    for sk in skills():
        cmd += ["--skill", json.dumps(sk)]
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cmd = build_cmd()
    if args.dry_run:
        shown = [c if os.environ.get("MCP_AUTH_TOKEN", "\x00") not in c else c.replace(os.environ["MCP_AUTH_TOKEN"], "***") for c in cmd]
        for c in shown[:12]: print(repr(c)[:160])
        print(f"... +{len(cmd)-12} args, {len(skills())} skills")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY (participant workspace key) not set — load .env first.")
    out = subprocess.run(cmd, capture_output=True, text=True)
    print(out.stdout)
    if out.returncode != 0:
        sys.exit(f"ant failed (rc={out.returncode}):\n{out.stderr}")


if __name__ == "__main__":
    main()
