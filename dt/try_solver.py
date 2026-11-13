"""Run a solver over the dumped samples and print question -> answer.

    python -m dt.try_solver reverseWord [--limit 10] [--config config.toml]

Nothing is sent to the server: use it to eyeball answers before saving.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from dt.registry import Registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run a solver on saved samples")
    parser.add_argument("nugget_type")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    # Questions may hold characters a Windows console cannot encode.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    raw = tomllib.loads(args.config.read_text(encoding="utf-8"))
    samples = Path(raw.get("data_dir", "data")) / "samples" / f"{args.nugget_type}.jsonl"
    registry = Registry(Path(raw.get("solvers_dir", "solvers")))
    registry.refresh()
    if args.nugget_type not in registry.solvers:
        raise SystemExit(f"No loaded solver named {args.nugget_type}")
    lines = samples.read_text(encoding="utf-8").splitlines()[: args.limit]
    for line in lines:
        content = json.loads(line)["content"]
        print(f"{content!r}\n   -> {registry.solve(args.nugget_type, content)!r}")


if __name__ == "__main__":
    main()
