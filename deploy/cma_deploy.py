"""Assemble and deploy Penny as a Claude Managed Agent (CMA).

CMA flow (agents are persistent — create once, update to bump versions):
  1. Skills   -> POST /v1/skills (+ /versions on update); agents reference by skill_id
  2. Vault    -> MCP auth lives in a vault credential, NOT on the agent
  3. Agent    -> mcp_servers = {type,name,url} only; tools must include the
                 mcp_toolset entry AND the read tool (skills need it to load)

State (skill ids, vault id, agent id) persists in deploy/cma_state.json so
re-runs update instead of duplicating.

Requires (gitignored .env):
  ANTHROPIC_API_KEY  — the PARTICIPANT workspace key (never the judge key)
  MCCTX_MCP_URL / MCP_AUTH_TOKEN — the company MCP

Usage:
  python -m deploy.cma_deploy --dry-run    # print the plan, deploy nothing
  python -m deploy.cma_deploy              # create or update everything
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).parent.parent
SKILLS_DIR = ROOT / "agent" / "skills"
DUTIES_DIR = ROOT / "agent" / "duties"
BUILD_DIR = pathlib.Path(__file__).parent / ".build" / "skills"
STATE_PATH = pathlib.Path(__file__).parent / "cma_state.json"

VAULT_NAME = "penny-mccontext"
AGENT_NAME = "Penny — Controls Copilot"


def ant(*args, stdin: str | None = None, cwd: pathlib.Path | None = None) -> dict:
    cmd = ["ant", *args, "--format", "json", "--format-error", "json"]
    out = subprocess.run(cmd, input=stdin, capture_output=True, text=True, cwd=cwd)
    if out.returncode != 0:
        sys.exit(f"ant {' '.join(args[:2])} failed:\n{out.stdout}\n{out.stderr}")
    return json.loads(out.stdout)


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"skills": {}, "vault_id": None, "agent_id": None, "agent_version": None}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def stage_skills() -> list[pathlib.Path]:
    """Copy each skill dir to .build/, inlining referenced duty SQL so the
    deployed skill needs no repo filesystem."""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    staged = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        md = skill_dir / "SKILL.md"
        if not md.exists():
            continue
        content = md.read_text()
        for sql_path in sorted(DUTIES_DIR.glob("*.sql")):
            ref = f"agent/duties/{sql_path.name}"
            if ref in content:
                content += (
                    f"\n\n## Candidate SQL ({sql_path.name}) — run this via run_sql\n"
                    f"```sql\n{sql_path.read_text()}\n```\n"
                )
        dest = BUILD_DIR / skill_dir.name
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text(content)
        staged.append(dest)
    return staged


def deploy_skills(staged: list[pathlib.Path], state: dict) -> None:
    for skill_dir in staged:
        name = skill_dir.name
        # curl, not `ant beta:skills create`: the API requires the multipart
        # filename to be "<folder>/SKILL.md" and the CLI strips the folder.
        if name in state["skills"]:
            url = f"https://api.anthropic.com/v1/skills/{state['skills'][name]}/versions"
            form = []
        else:
            url = "https://api.anthropic.com/v1/skills"
            form = ["-F", f"display_title={name}"]
        cmd = ["curl", "-sS", url,
               "-H", f"x-api-key: {os.environ['ANTHROPIC_API_KEY']}",
               "-H", "anthropic-version: 2023-06-01",
               "-H", "anthropic-beta: skills-2025-10-02",
               *form,
               "-F", f"files[]=@SKILL.md;filename={name}/SKILL.md"]
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=skill_dir)
        res = json.loads(out.stdout) if out.stdout else {}
        if out.returncode != 0 or res.get("type") == "error":
            sys.exit(f"skill {name} upload failed:\n{out.stdout}\n{out.stderr}")
        if name not in state["skills"]:
            state["skills"][name] = res["id"]
            print(f"skill {name}: created (id {res['id']})")
        else:
            print(f"skill {name}: new version {res.get('version', '?')}")
        save_state(state)


def deploy_vault(state: dict) -> None:
    mcp_url = os.environ["MCCTX_MCP_URL"]
    mcp_token = os.environ["MCP_AUTH_TOKEN"]
    if not state["vault_id"]:
        res = ant("beta:vaults", "create", "--display-name", VAULT_NAME)
        state["vault_id"] = res["id"]
        save_state(state)
        print(f"vault: created (id {res['id']})")
    # Credentials are write-only; keys immutable -> recreate is archive+create.
    # Only create the credential once per vault.
    if not state.get("credential_id"):
        res = ant("beta:vaults:credentials", "create",
                  "--vault-id", state["vault_id"],
                  "--display-name", "mccontext-bearer",
                  "--auth", json.dumps({
                      "type": "static_bearer",
                      "mcp_server_url": mcp_url,
                      "token": mcp_token,
                  }))
        state["credential_id"] = res["id"]
        save_state(state)
        print(f"vault credential: created (id {res['id']})")


def agent_body(state: dict) -> dict:
    cfg = yaml.safe_load((ROOT / "agent" / "agent.yaml").read_text())
    return {
        "name": AGENT_NAME,
        "model": cfg["model"],
        "system": cfg["system"],
        "mcp_servers": [{
            "type": "url",
            "name": "mccontext",
            "url": os.environ["MCCTX_MCP_URL"],
        }],
        "tools": [
            # Skills load via file tools -> read must be on. Everything else
            # off: Penny investigates through MCP run_sql, not the sandbox.
            {
                "type": "agent_toolset_20260401",
                "default_config": {"enabled": False},
                "configs": [
                    {"name": "read", "enabled": True},
                    {"name": "glob", "enabled": True},
                    {"name": "grep", "enabled": True},
                ],
            },
            {"type": "mcp_toolset", "mcp_server_name": "mccontext"},
        ],
        "skills": [
            {"type": "custom", "skill_id": sid, "version": "latest"}
            for sid in state["skills"].values()
        ],
    }


def deploy_agent(state: dict) -> None:
    body = agent_body(state)
    if state["agent_id"]:
        res = ant("beta:agents", "update", "--agent-id", state["agent_id"],
                  "--version", str(state["agent_version"]), stdin=json.dumps(body))
    else:
        res = ant("beta:agents", "create", stdin=json.dumps(body))
        state["agent_id"] = res["id"]
    state["agent_version"] = res["version"]
    save_state(state)
    print(f"\nAGENT_ID={state['agent_id']}\nAGENT_VERSION={state['agent_version']}")
    print(f"VAULT_ID={state['vault_id']}  (attach via vault_ids when creating a session)")
    print("Register this id+version on the platform Deploy page, then Run (spends a life).")


def load_dotenv() -> None:
    """Fill os.environ from .env for vars that are unset or empty there.
    An empty .env line never clobbers a key already in the environment."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value and not os.environ.get(key):
            os.environ[key] = value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_dotenv()
    for var in ("MCCTX_MCP_URL", "MCP_AUTH_TOKEN"):
        if not os.environ.get(var):
            sys.exit(f"{var} not set — load .env first.")

    state = load_state()
    staged = stage_skills()

    if args.dry_run:
        body = agent_body(state)
        body["skills"] = [f"<{d.name}>" for d in staged]
        print(json.dumps(body, indent=2)[:3000])
        print(f"\n[dry-run] system={len(body['system'])} chars, "
              f"skills={[d.name for d in staged]}, "
              f"state={'update' if state['agent_id'] else 'create'}")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY (participant workspace key) not set — load .env first.")

    deploy_skills(staged, state)
    deploy_vault(state)
    deploy_agent(state)


if __name__ == "__main__":
    main()
