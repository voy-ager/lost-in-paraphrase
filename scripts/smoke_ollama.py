"""Local smoke test: 1 Apps sample, trusted monitoring, Ollama for all roles, Docker sandbox.

Needs Docker running and `ollama pull qwen2.5:0.5b`. Logs go to logs/ (gitignored).
"""

import sys

from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.settings.apps.apps_setting import AppsSetting
from inspect_ai import eval as inspect_eval

MODEL = "ollama/qwen2.5:0.5b"


def run() -> bool:
    cfg = ControlEvalConfig(
        trusted_model=MODEL,
        untrusted_model=MODEL,
        limit=1,
        log_dir="logs/smoke",
        max_steps=3,
        max_tasks=1,
        epochs=1,
    )
    task = get_control_task(
        AppsSetting(), trusted_monitoring_builder(), EvalMode.HONEST, eval_config=cfg
    )
    log = inspect_eval(task, **cfg.eval_args())[0]
    print("status:", log.status, "samples:", len(log.samples or []))
    return log.status == "success"


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
