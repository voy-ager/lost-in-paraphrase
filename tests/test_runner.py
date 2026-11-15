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
    names = list(ids)
    for i, a in enumerate(names):
        assert len(ids[a]) == SPLITS[a][1] - SPLITS[a][0] + 1
        for b in names[i + 1 :]:
            assert not ids[a] & ids[b]
    with pytest.raises(ValueError):
        select(POOL, 495, 10)
