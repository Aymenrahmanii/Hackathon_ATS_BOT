"""SPOILER: reference solver for the drill type palindromePhrase."""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    return js_str(is_palindrome(quoted(content)[0]))
