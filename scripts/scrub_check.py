"""Exit 1 if any path contains PII/secret-shaped strings (or is unreadable), else 0."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lip.scrub import scan_paths


def main(argv: list[str]) -> int:
    paths = argv or [d for d in ("results", "docs") if Path(d).exists()]
    hits = scan_paths(paths)
    for f, line, name in hits:
        print(f"{f.as_posix()}:{line}: {name}")
    print(f"scrub: {len(hits)} hit(s) in {len(paths)} path(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
