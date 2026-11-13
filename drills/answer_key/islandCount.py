"""SPOILER: reference solver for the drill type islandCount."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    grid = parse_grid(content.split("\n", 1)[1])
    return str(count_islands(grid))
