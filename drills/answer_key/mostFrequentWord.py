"""SPOILER: reference solver for the drill type mostFrequentWord."""

from collections import Counter
from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return Counter(quoted(content)[0].split()).most_common(1)[0][0]
