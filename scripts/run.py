"""One command, one experiment: python scripts/run.py configs/<name>.toml (needs Docker + Ollama)."""

import sys

from lip.runner import load_config, run

if __name__ == "__main__":
    log = run(load_config(sys.argv[1]))
    print("status:", log.status, "samples:", len(log.samples or []))
    sys.exit(0 if log.status == "success" else 1)
