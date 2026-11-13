"""SPOILER: reference solver for the drill type cheapestRoute."""

import re
from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    graph = {}
    for a, b, cost in re.findall(r"([A-Z])-([A-Z]):(\d+)", content):
        graph.setdefault(a, {})[b] = int(cost)
        graph.setdefault(b, {})[a] = int(cost)
    start, goal = re.search(r"from ([A-Z]) to ([A-Z])", content).groups()
    return str(dijkstra(graph, start, goal)[0])
