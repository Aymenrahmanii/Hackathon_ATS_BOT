"""SPOILER: reference solver for the drill type clockAfter."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    later, hour, minute = ints(content)[:3]
    total = hour * 60 + minute + later
    return f"{total // 60 % 24:02d}:{total % 60:02d}"
