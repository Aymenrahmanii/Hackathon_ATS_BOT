"""SPOILER: reference solver for the drill type baseConvert."""

import re
from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    digits, source, target = re.search(r"Convert (\w+) from base (\d+) to base (\d+)", content).groups()
    return to_base(int(digits, int(source)), int(target))
