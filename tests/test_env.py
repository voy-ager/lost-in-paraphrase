"""CI-safe: no network, Docker or Ollama. Checks ControlArena imports and tasks build with mockllm."""

import sys

import pytest
from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.settings.apps.apps_setting import AppsSetting
from inspect_ai.dataset import Sample


def test_trusted_monitoring_task_constructs():
    cfg = ControlEvalConfig(
        trusted_model="mockllm/model", untrusted_model="mockllm/model", limit=1
    )
    task = get_control_task(
        AppsSetting(),
        trusted_monitoring_builder(),
        EvalMode.ATTACK,
        eval_config=cfg,
        dataset=[Sample(input="x")],  # dummy sample: no Hugging Face download
    )
    assert task.name


@pytest.mark.slow
def test_smoke_ollama():
    """Local only: needs Docker + Ollama. Same as `python scripts/smoke_ollama.py`."""
    sys.path.insert(0, "scripts")
    from smoke_ollama import run

    assert run()
