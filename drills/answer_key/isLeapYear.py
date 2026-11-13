"""SPOILER: reference solver for the drill type isLeapYear."""

import calendar
from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return js_str(calendar.isleap(ints(content)[0]))
