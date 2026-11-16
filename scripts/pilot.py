"""Phase 1 pilot: N honest Apps samples, trusted monitoring, one Ollama model in all roles, text-submit parser on.

Usage: python scripts/pilot.py <ollama-model-tag> <n> <max_steps> <log-subdir>
Logs go to logs/pilot/ (gitignored). Prints a one-line JSON summary; Docker and Ollama must be running.
"""

import json
import sys
import threading
import time

import psutil

from lip.runner import run


def peak_rss_sampler(stop: threading.Event, out: dict) -> None:
    # system-wide used RAM (Ollama + Docker VM are separate processes)
    while not stop.is_set():
        out["peak_gb"] = max(
            out.get("peak_gb", 0), psutil.virtual_memory().used / 2**30
        )
        stop.wait(2)


def summarize(log, model: str, wall: float, peak_gb: float) -> dict:
    samples = log.samples or []
    asst = [m for s in samples for m in s.messages if m.role == "assistant"]
    scored = [m for m in asst if (m.metadata or {}).get("suspicion_score") is not None]
    passed = [
        s
        for s in samples
        if any(
            getattr(v, "value", None) in ("C", 1, 1.0, True)
            for v in (s.scores or {}).values()
        )
        or any(
            isinstance(getattr(v, "value", None), dict)
            and v.value.get("main_task_success") in ("C", 1, 1.0, True)
            for v in (s.scores or {}).values()
        )
    ]
    return {
        "model": model,
        "status": log.status,
        "n": len(samples),
        "wall_s": round(wall, 1),
        "s_per_sample": round(wall / max(len(samples), 1), 1),
        "assistant_msgs": len(asst),
        "tool_call_msgs": sum(1 for m in asst if m.tool_calls),
        "text_submit_msgs": sum(
            1 for m in asst if (m.metadata or {}).get("text_submit")
        ),
        "submit_calls": sum(
            1 for m in asst for t in (m.tool_calls or []) if t.function == "submit"
        ),
        "scored_msgs": len(scored),
        "passed": len(passed),
        "peak_ram_gb": round(peak_gb, 1),
    }


def main(model: str, n: int, max_steps: int, tag: str) -> dict:
    cfg = {
        "protocol": "trusted_monitoring_text_submit",
        "mode": "honest",
        "untrusted_model": f"ollama/{model}",
        "trusted_model": f"ollama/{model}",
        "start": 1,
        "n": n,
        "max_steps": max_steps,
        "seed": 0,
        "log_dir": f"logs/pilot/{tag}",
        "setting": {"has_backdoor_solution": True, "shuffle_seed": 0},
    }
    stop, mem = threading.Event(), {}
    threading.Thread(target=peak_rss_sampler, args=(stop, mem), daemon=True).start()
    t0 = time.time()
    log = run(cfg)
    wall = time.time() - t0
    stop.set()
    return summarize(log, model, wall, mem.get("peak_gb", 0))


if __name__ == "__main__":
    a = sys.argv
    print(json.dumps(main(a[1], int(a[2]), int(a[3]), a[4])))
