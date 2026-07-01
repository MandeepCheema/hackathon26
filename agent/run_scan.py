"""Drive the Penny agent over each duty. `client` exposes run_sql + call(submit_*)."""
import pathlib, yaml


def _skill(name):
    return pathlib.Path(f"agent/skills/{name}/SKILL.md").read_text()


def _system():
    return yaml.safe_load(open("agent/agent.yaml"))["system"]


def scan_all(client, runner=None):
    if runner is None:
        from agent.sdk_loop import run_agent
        runner = run_agent
    system = _system()
    for duty in ("cash-over-short", "loss-prevention"):
        runner(system, _skill(duty), client)
