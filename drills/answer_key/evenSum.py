"""SPOILER: reference solver for the drill type evenSum."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return js_str(sum(n for n in ints(content) if n % 2 == 0))
