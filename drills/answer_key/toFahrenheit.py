"""SPOILER: reference solver for the drill type toFahrenheit."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    celsius = numbers(content)[0]
    return to_fixed(celsius * 9 / 5 + 32, 1)  # "77.0", not "77"
