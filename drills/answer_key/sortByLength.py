"""SPOILER: reference solver for the drill type sortByLength."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    chosen = csv(after(content, ":"))
    return ",".join(sorted(chosen, key=lambda word: (len(word), word)))
