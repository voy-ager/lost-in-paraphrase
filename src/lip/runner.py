"""Run one experiment config: `python scripts/run.py configs/<name>.toml`.

Task selection: ControlArena's dataset API has no range option, so we take the
setting's dataset (`shuffle_dataset` + `shuffle_seed` fix the order) and slice it by
1-based position [start, start + n). Same config -> same tasks; honest and attack use
the same slice, and the design's splits (SPLITS) are disjoint position ranges.
"""

import tomllib
from pathlib import Path

from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.settings.apps.apps_setting import AppsSetting
from inspect_ai import eval as inspect_eval
from inspect_ai.model import GenerateConfig

# design section 5: inclusive 1-based positions in the seeded backdoor-verified pool
SPLITS = {
    "pilot": (1, 10),
    "main": (11, 110),
    "extension": (111, 210),
    "dev": (301, 340),
    "honeypot": (401, 460),
}
PROTOCOLS = {"trusted_monitoring": trusted_monitoring_builder}  # others plug in here


REQUIRED = {"protocol", "mode", "untrusted_model", "trusted_model", "log_dir"}
OPTIONAL = {"split", "start", "n", "epochs", "max_steps", "seed", "setting"}
SETTING_KEYS = {"has_backdoor_solution", "shuffle_seed"}


def load_config(path):
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    if missing := REQUIRED - cfg.keys():
        raise ValueError(f"missing config keys: {sorted(missing)}")
    if extra := cfg.keys() - REQUIRED - OPTIONAL:
        raise ValueError(f"unknown config keys: {sorted(extra)}")
    s = cfg.setdefault("setting", {})
    if extra := s.keys() - SETTING_KEYS:
        raise ValueError(f"unknown [setting] keys: {sorted(extra)}")
    if not isinstance(s.get("shuffle_seed"), int):
        raise ValueError("[setting] shuffle_seed (int) is required")  # noqa: TRY004
    if s.setdefault("has_backdoor_solution", True) is not True:
        raise ValueError("has_backdoor_solution must be true (backdoor-verified pool)")
    if cfg["protocol"] not in PROTOCOLS:
        raise ValueError(
            f"unknown protocol {cfg['protocol']!r}; have {list(PROTOCOLS)}"
        )
    if cfg["mode"] not in {m.value for m in EvalMode}:
        raise ValueError(f"unknown mode {cfg['mode']!r}; use 'honest' or 'attack'")
    parts = Path(cfg["log_dir"]).parts
    if Path(cfg["log_dir"]).is_absolute() or len(parts) < 2 or parts[0] != "logs":
        raise ValueError("log_dir must be a relative path under logs/ (e.g. logs/x)")
    if "split" in cfg:
        if cfg["split"] not in SPLITS:
            raise ValueError(f"unknown split {cfg['split']!r}; have {list(SPLITS)}")
        lo, hi = SPLITS[cfg["split"]]
        cfg.setdefault("start", lo)
        cfg.setdefault("n", hi - cfg["start"] + 1)
        if not (lo <= cfg["start"] and cfg["start"] + cfg["n"] - 1 <= hi):
            raise ValueError("start/n fall outside the named split")
    if "n" not in cfg:
        raise ValueError("config needs n (or a split)")
    return cfg


def select(samples, start, n):
    """Samples at 1-based positions start..start+n-1."""
    chosen = list(samples)[start - 1 : start - 1 + n]
    if len(chosen) != n:
        raise ValueError(
            f"asked for {n} tasks from position {start}, got {len(chosen)}"
        )
    return chosen


def build_task(cfg, samples=None):
    """Task for cfg. `samples` replaces the dataset (tests); else the setting's dataset is sliced."""
    s = cfg.get("setting", {})
    setting = AppsSetting(
        has_backdoor_solution=s.get("has_backdoor_solution", True),
        shuffle_dataset=s.get("shuffle_seed") is not None,
        shuffle_seed=s.get("shuffle_seed"),
    )
    mode = EvalMode(cfg["mode"])
    ec = ControlEvalConfig(
        untrusted_model=cfg["untrusted_model"],
        trusted_model=cfg["trusted_model"],
        epochs=cfg.get("epochs", 1),
        max_steps=cfg.get("max_steps"),
        log_dir=cfg["log_dir"],
        max_tasks=1,
        untrusted_config=GenerateConfig(seed=cfg.get("seed")),
        trusted_config=GenerateConfig(seed=cfg.get("seed")),
    )
    if samples is None:
        samples = setting.get_dataset(mode)
    task = get_control_task(
        setting,
        PROTOCOLS[cfg["protocol"]](),
        mode,
        eval_config=ec,
        dataset=select(samples, cfg.get("start", 1), cfg["n"]),
    )
    return task, ec


def run(cfg):
    task, ec = build_task(cfg)
    return inspect_eval(task, **ec.eval_args())[0]
