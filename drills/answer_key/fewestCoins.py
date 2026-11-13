"""SPOILER: reference solver for the drill type fewestCoins."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    amount, *coins = ints(content)
    return str(min_coins(coins, amount))  # greedy fails for coins like 1, 3, 4
