"""SPOILER: reference solver for the drill type jsonSum."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    def total(node):
        if isinstance(node, bool):  # True is an int in Python: exclude it first
            return 0
        if isinstance(node, int):
            return node
        if isinstance(node, list):
            return sum(map(total, node))
        if isinstance(node, dict):
            return sum(map(total, node.values()))
        return 0

    return str(total(json_in(content)))
