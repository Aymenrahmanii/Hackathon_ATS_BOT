"""SPOILER: reference solver for the drill type evaluate."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return js_str(calc(after(content, ":")))  # js_str prints 56.0 as "56"
