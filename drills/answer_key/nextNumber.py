"""SPOILER: reference solver for the drill type nextNumber."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return js_str(next_term(ints(content)))
