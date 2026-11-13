"""Nuggets we have discovered and not yet tried."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

STALE_WINDOW = 5  # look at the last N claim results
STALE_HITS = 2  # this many "already claimed" in the window means re-discover


@dataclass(frozen=True)
class Nugget:
    id: str
    content: str
    type: str
    coefficient: int


class Pool:
    def __init__(self, slot: int | None = None) -> None:
        self.slot = slot
        self.nuggets: dict[str, Nugget] = {}
        self.types: dict[str, int] = {}  # nuggetType -> coefficient, this round
        self.tried: set[str] = set()
        self.recent: deque[bool] = deque(maxlen=STALE_WINDOW)

    def __len__(self) -> int:
        return len(self.nuggets)

    def fill(self, raw: list[dict[str, Any]]) -> int:
        """Replace the pool with a fresh discover result. Returns how many we kept."""
        found = [_parse(item) for item in raw if not item.get("claimed")]
        for nugget in found:
            self.types[nugget.type] = nugget.coefficient
        fresh = [n for n in found if n.id not in self.tried]
        mine = [n for n in fresh if self._is_mine(n.id)] or fresh
        self.nuggets = {n.id: n for n in mine}
        self.recent.clear()
        return len(mine)

    def pick(self, rate: Callable[[str], float]) -> Nugget | None:
        """The nugget with the best expected value, or None if none is solvable."""
        best = max(self.nuggets.values(), key=lambda n: n.coefficient * rate(n.type), default=None)
        if best is None or rate(best.type) <= 0:
            return None
        return best

    def best_value(self, rate: Callable[[str], float]) -> float:
        return max((n.coefficient * rate(n.type) for n in self.nuggets.values()), default=0.0)

    def has(self, nugget_type: str) -> bool:
        return any(n.type == nugget_type for n in self.nuggets.values())

    def discard(self, nugget_id: str) -> None:
        self.tried.add(nugget_id)
        self.nuggets.pop(nugget_id, None)

    def note(self, already_claimed: bool) -> None:
        self.recent.append(already_claimed)

    def stale(self) -> bool:
        return sum(self.recent) >= STALE_HITS

    def clear(self) -> None:
        self.nuggets.clear()
        self.recent.clear()

    def reset(self) -> None:
        """New round: nothing we knew is valid any more."""
        self.clear()
        self.types.clear()

    def _is_mine(self, nugget_id: str) -> bool:
        if self.slot is None:
            return True
        try:
            return int(nugget_id[-1], 16) % 2 == self.slot
        except ValueError:
            return True


def _parse(item: dict[str, Any]) -> Nugget:
    return Nugget(
        id=str(item["_id"]),
        content=str(item.get("content", "")),
        type=str(item.get("nuggetType", "")),
        coefficient=int(item.get("coefficient", 1)),
    )
