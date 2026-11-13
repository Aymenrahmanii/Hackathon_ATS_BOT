"""SPOILER: reference solver for the drill type daysFromTo."""

import re
from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    first, second = re.findall(r"\d{4}-\d{2}-\d{2}", content)
    return str(days_between(first, second))
