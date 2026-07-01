from agent.run_scan import scan_all

def test_scan_all_runs_both_duties_with_skill_text():
    """v1 duties (cash-over-short, loss-prevention) are still included; system prompt is Penny's."""
    calls = []
    def fake_runner(system, task, client):
        calls.append((system, task))
    scan_all(client=object(), runner=fake_runner)
    systems = {c[0] for c in calls}
    assert len(systems) == 1 and "Penny" in next(iter(systems))   # system prompt from agent.yaml
    tasks = " ".join(c[1] for c in calls)
    assert "cash-over-short" in tasks and "loss-prevention" in tasks  # each skill's frontmatter name


def test_scan_all_runs_six_duties():
    """v2: 6 duties scanned (policy is a reference skill, not scanned alone)."""
    calls = []
    def fake_runner(system, task, client):
        calls.append((system, task))
    scan_all(client=object(), runner=fake_runner)
    assert len(calls) == 6
    tasks = " ".join(c[1] for c in calls)
    for duty_name in ("cash-over-short", "loss-prevention", "three-way-match",
                      "duplicate-payment", "settlement", "cogs-leakage"):
        assert duty_name in tasks, f"Expected duty '{duty_name}' not found in skill texts"


def test_scan_all_does_not_scan_policy_alone():
    """policy is a reference skill; it must NOT appear as a standalone duty scan."""
    calls = []
    def fake_runner(system, task, client):
        calls.append((system, task))
    scan_all(client=object(), runner=fake_runner)
    # policy skill text starts with 'name: policy' — verify it isn't a top-level duty call
    # (it may be referenced inside other skills but not called standalone by scan_all)
    assert len(calls) == 6  # only 6, not 7
