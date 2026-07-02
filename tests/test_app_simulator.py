"""app.simulator — eligibility picker: announce only what will visibly resolve."""
from app import cases, seeds, simulator


def test_picker_skips_flags_with_open_twin(app_db):
    flag_idx = next(i for i, s in enumerate(seeds.CASES) if s["verdict"] == "flag")
    cases.from_seed(seeds.CASES[flag_idx], lap=1)          # its twin is now open

    i, seed = simulator.pick_eligible(flag_idx)
    assert seed is not None
    assert not (seed["duty"] == seeds.CASES[flag_idx]["duty"]
                and seed["entity_id"] == seeds.CASES[flag_idx]["entity_id"])


def test_picker_always_finds_clears_when_all_flags_open(app_db):
    for s in seeds.CASES:
        if s["verdict"] == "flag":
            cases.from_seed(s, lap=1)
    _, seed = simulator.pick_eligible(0)
    assert seed is not None and seed["verdict"] == "clear"


def test_dismissed_flag_becomes_eligible_again(app_db):
    flag = next(s for s in seeds.CASES if s["verdict"] == "flag")
    k = cases.from_seed(flag, lap=1)
    idx = seeds.CASES.index(flag)
    _, seed = simulator.pick_eligible(idx)
    assert seed is not flag                                 # blocked while open

    cases.act(k["id"], "dismiss")
    _, seed = simulator.pick_eligible(idx)
    assert seed is flag                                     # freed after processing


def test_seed_pool_is_demo_deep(app_db):
    flags = [s for s in seeds.CASES if s["verdict"] == "flag"]
    clears = [s for s in seeds.CASES if s["verdict"] == "clear"]
    assert len(flags) >= 8 and len(clears) >= 5             # busy-rail requirement
    assert len({(s["duty"], s["entity_id"]) for s in seeds.CASES}) == len(seeds.CASES)
