"""SPOILER: reference solver for the drill type titleCase."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return quoted(content)[0].title()
