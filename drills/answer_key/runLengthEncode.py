"""SPOILER: reference solver for the drill type runLengthEncode."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return rle_encode(quoted(content)[0])
