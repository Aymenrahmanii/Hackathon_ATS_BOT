"""SPOILER: reference solver for the drill type mazeSteps."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    grid = parse_grid(content.split("\n", 1)[1])
    path = shortest_path(grid, find(grid, "S"), find(grid, "E"))
    return str(len(path) - 1)
