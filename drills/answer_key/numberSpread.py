"""SPOILER: reference solver for the drill type numberSpread."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    values = ints(after(content, ":"))
    return str(max(values) - min(values))
