from agent.run_scan import scan_all

def test_scan_all_runs_both_duties_with_skill_text():
    calls = []
    def fake_runner(system, task, client):
        calls.append((system, task))
    scan_all(client=object(), runner=fake_runner)
    assert len(calls) == 2
    systems = {c[0] for c in calls}
    assert len(systems) == 1 and "Penny" in next(iter(systems))   # system prompt from agent.yaml
    tasks = " ".join(c[1] for c in calls)
    assert "cash-over-short" in tasks and "loss-prevention" in tasks  # each skill's frontmatter name
