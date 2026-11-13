"""SPOILER: reference solver for the drill type initials."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return "".join(name[0] for name in quoted(content)[0].split())
