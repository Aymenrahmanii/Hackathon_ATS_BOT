"""SPOILER: reference solver for the drill type caesarDecode."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return caesar(quoted(content)[0], -ints(content)[-1])
