"""SPOILER: reference solver for the drill type countLetter."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    letter, phrase = quoted(content)
    return str(phrase.count(letter))
