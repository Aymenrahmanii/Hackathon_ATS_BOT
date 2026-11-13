"""SPOILER: reference solver for the drill type primeFactorList."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return js_str(prime_factors(ints(content)[0]))
