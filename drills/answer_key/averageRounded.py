"""SPOILER: reference solver for the drill type averageRounded."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    values = ints(content)[:-1]  # the last number is the "2" of "2 decimals"
    return to_fixed(sum(values) / len(values), 2)  # round() would give 6.12 for 6.125
