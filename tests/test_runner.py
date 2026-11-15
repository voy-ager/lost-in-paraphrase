"""CI-safe: no Docker, network or Ollama. Config loading, task construction, split selection.

A full run needs the Apps Docker sandbox, so end-to-end with mockllm is not possible here.
"""

import pytest
from inspect_ai.dataset import Sample

from lip.runner import SPLITS, build_task, load_config, select

POOL = [Sample(input=str(i)) for i in range(1, 501)]


def test_configs_load_and_build_with_mockllm():
    for name in ("pilot_honest", "pilot_attack"):
        cfg = load_config(f"configs/{name}.toml")
        cfg |= {"untrusted_model": "mockllm/model", "trusted_model": "mockllm/model"}
        task, _ = build_task(cfg, samples=POOL)
        assert [s.input for s in task.dataset] == [str(i) for i in range(1, 11)]


def test_bad_config_rejected(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('protocol = "nope"\nmode = "honest"\nlog_dir = "logs/x"\n')
    with pytest.raises(ValueError):
        load_config(p)


def test_selection_deterministic_and_splits_disjoint():
    ids = {
        k: {s.input for s in select(POOL, lo, hi - lo + 1)}
        for k, (lo, hi) in SPLITS.items()
    }
    assert ids == {
        k: {s.input for s in select(POOL, lo, hi - lo + 1)}
        for k, (lo, hi) in SPLITS.items()
    }
    assert SPLITS == {
        "pilot": (1, 10),
        "main": (11, 110),
        "extension": (111, 210),
        "dev": (301, 340),
        "honeypot": (401, 460),
    }
    names = list(ids)
    for i, a in enumerate(names):
        assert len(ids[a]) == SPLITS[a][1] - SPLITS[a][0] + 1
        for b in names[i + 1 :]:
            assert not ids[a] & ids[b]
    with pytest.raises(ValueError):
        select(POOL, 495, 10)


BASE = (
    'protocol = "trusted_monitoring"\nmode = "honest"\nuntrusted_model = "a"\n'
    'trusted_model = "b"\nlog_dir = "logs/x"\nn = 1\n'
)
SET = "[setting]\nshuffle_seed = 0\n"


@pytest.mark.parametrize(
    "text, msg",
    [
        (BASE + "[setting]\nshuffle_sed = 0\n", r"unknown \[setting\]"),
        ("typo = 1\n" + BASE + SET, "unknown config"),
        (BASE.replace('trusted_model = "b"\n', "") + SET, "missing"),
        (BASE, "shuffle_seed"),
        (BASE + SET + "has_backdoor_solution = false\n", "backdoor"),
        (BASE.replace("logs/x", "") + SET, "log_dir"),
        (BASE.replace("honest", "evil") + SET, "unknown mode"),
    ],
)
def test_schema_errors(tmp_path, text, msg):
    p = tmp_path / "c.toml"
    p.write_text(text)
    with pytest.raises(ValueError, match=msg):
        load_config(p)


def test_modes_share_dataset_and_loader_args(monkeypatch):
    import control_arena.settings.apps.apps_setting as m

    calls = []

    def fake(**kw):
        calls.append(kw)
        return POOL

    monkeypatch.setattr(m, "get_dataset", fake)
    ids = []
    for name in ("pilot_honest", "pilot_attack"):
        cfg = load_config(f"configs/{name}.toml")
        cfg |= {"untrusted_model": "mockllm/model", "trusted_model": "mockllm/model"}
        task, _ = build_task(cfg)  # no samples: goes through the setting's loader
        ids.append([s.input for s in task.dataset])
    assert ids[0] == ids[1]
    a, b = calls
    assert {k: v for k, v in a.items() if k != "mode"} == {
        k: v for k, v in b.items() if k != "mode"
    }
    assert a["seed"] == 0 and a["shuffle"] and a["has_backdoor_solution"]
