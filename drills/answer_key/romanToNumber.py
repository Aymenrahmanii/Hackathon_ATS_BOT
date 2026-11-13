"""SPOILER: reference solver for the drill type romanToNumber."""

import re
from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return str(from_roman(re.search(r"numeral (\w+)", content).group(1)))
