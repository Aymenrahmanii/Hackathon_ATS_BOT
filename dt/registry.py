"""Loads solvers from a folder and reloads them when a file changes.

A solver is a file named <nuggetType>.py that defines solve(content: str) -> str.
Saving the file is enough: the running bot picks it up on its next step.

A new solver is on probation ("canary"): one wrong answer before TRUST_AFTER
correct ones pauses it until the file is edited again.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

TRUST_AFTER = 5
WINDOW = 10
MIN_RATE = 0.7

Stamp = tuple[int, int]  # (mtime_ns, size)


@dataclass
class Solver:
    solve: Callable[[str], str]
    wins: int = 0
    paused: bool = False
    results: deque[bool] = field(default_factory=lambda: deque(maxlen=WINDOW))

    def rate(self) -> float:
        return sum(self.results) / len(self.results) if self.results else 1.0


class Registry:
    def __init__(self, folder: Path, out: Callable[[str], None] = print) -> None:
        self.folder = folder
        self.out = out
        self.solvers: dict[str, Solver] = {}
        self.stamps: dict[str, Stamp] = {}

    def refresh(self) -> None:
        """Load new or changed solver files. A broken file never stops the bot."""
        present: set[str] = set()
        for path in sorted(self.folder.glob("*.py")):
            if path.stem.startswith("_"):
                continue
            present.add(path.stem)
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
            if self.stamps.get(path.stem) != stamp:
                self.stamps[path.stem] = stamp
                self._load(path)
        for name in set(self.stamps) - present:
            del self.stamps[name]
            self.solvers.pop(name, None)
            self.out(f"solver {name}: file removed")

    def rate(self, name: str) -> float:
        """Expected success rate; 0 when there is no usable solver."""
        solver = self.solvers.get(name)
        if solver is None or solver.paused:
            return 0.0
        return solver.rate()

    def solve(self, name: str, content: str) -> str | None:
        solver = self.solvers[name]
        try:
            answer = solver.solve(content)
        except Exception as error:  # a solver bug must not kill the bot
            self.out(f"solver {name}: {type(error).__name__}: {error} on {content!r}")
            self.record(name, False)
            return None
        if not isinstance(answer, str):
            self.out(f"solver {name}: returned {type(answer).__name__}, expected str")
            self.record(name, False)
            return None
        return answer

    def record(self, name: str, correct: bool) -> None:
        solver = self.solvers.get(name)
        if solver is None:
            return
        solver.results.append(correct)
        if correct:
            solver.wins += 1
        elif solver.wins < TRUST_AFTER:
            self._pause(name, solver, "failed on probation")
        elif len(solver.results) == WINDOW and solver.rate() < MIN_RATE:
            self._pause(name, solver, f"success rate fell to {solver.rate():.0%}")

    def _pause(self, name: str, solver: Solver, why: str) -> None:
        solver.paused = True
        self.out(f"\asolver {name}: PAUSED ({why}). Edit the file to retry.")

    def _load(self, path: Path) -> None:
        # exec on the source text, not import: no stale bytecode cache.
        namespace: dict[str, object] = {"__name__": f"solver_{path.stem}", "__file__": str(path)}
        try:
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
            solve = namespace["solve"]
            if not callable(solve):
                raise TypeError("solve is not a function")
        except Exception as error:
            self.solvers.pop(path.stem, None)
            self.out(f"\asolver {path.stem}: NOT LOADED: {type(error).__name__}: {error}")
            return
        self.solvers[path.stem] = Solver(solve)
        self.out(f"solver {path.stem}: loaded (on probation)")
