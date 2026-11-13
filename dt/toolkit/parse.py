"""Turn question text into data."""

from __future__ import annotations

import json
import re
from typing import Any

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_QUOTES = [r'"([^"]*)"', r"“([^”]*)”", r"`([^`]*)`", r"'([^']*)'"]


def ints(text: str, signed: bool = True) -> list[int]:
    """All integers in order. ints("add 12 and -7") -> [12, -7].
    Use signed=False when a hyphen is a separator: ints("3-5", signed=False) -> [3, 5]."""
    return [int(n) for n in re.findall(r"-?\d+" if signed else r"\d+", text)]


def numbers(text: str) -> list[int | float]:
    """All numbers, ints kept as ints. numbers("2.5 kg and 4") -> [2.5, 4]."""
    return [value(n) for n in re.findall(_NUMBER, text)]


def quoted(text: str) -> list[str]:
    """Strings inside quotes. Tries "double", then “curly”, `backtick`, then 'single'.
    quoted('What is "hello" backwards?') -> ["hello"]"""
    for pattern in _QUOTES:
        found = re.findall(pattern, text)
        if found:
            return found
    return []


def words(text: str) -> list[str]:
    """Alphabetic words. words("Hi, it's me!") -> ["Hi", "it's", "me"]"""
    return re.findall(r"[A-Za-zÀ-ÿ]+(?:'[A-Za-z]+)?", text)


def value(token: str) -> Any:
    """One token as int, float, bool, None or stripped string.
    value(" 42 ") -> 42, value("true") -> True, value("'a'") -> "a" """
    token = token.strip()
    lowered = token.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    for convert in (int, float):
        try:
            return convert(token)
        except ValueError:
            pass
    return token.strip("\"'")


def lists(text: str) -> list[list[Any]]:
    """Every [bracketed, list] in the text, items converted with value().
    lists("max of [3, 10, -2]?") -> [[3, 10, -2]]"""
    inner = re.findall(r"\[([^\[\]]*)\]", text)
    return [[value(item) for item in body.split(",") if item.strip()] for body in inner]


def csv(text: str, sep: str = ",") -> list[Any]:
    """Split on a separator and convert each item. csv("3, 4,x") -> [3, 4, "x"]"""
    return [value(item) for item in text.split(sep) if item.strip()]


def after(text: str, marker: str) -> str:
    """What follows the first marker, stripped. after("Sort: 3, 1", ":") -> "3, 1" """
    return text.split(marker, 1)[1].strip()


def between(text: str, start: str, end: str) -> str:
    """Text between two markers. between("f(x+1) = ?", "(", ")") -> "x+1" """
    return text.split(start, 1)[1].split(end, 1)[0]


def json_in(text: str) -> Any:
    """First JSON object or array embedded in the text.
    json_in('Sum of {"a": 1, "b": [2]} ?') -> {"a": 1, "b": [2]}"""
    decoder = json.JSONDecoder()
    for position, char in enumerate(text):
        if char in "{[":
            try:
                return decoder.raw_decode(text, position)[0]
            except ValueError:
                continue
    raise ValueError("no JSON found")


def pairs(text: str) -> dict[str, Any]:
    """key: value or key=value pairs. pairs("a=1, b: two") -> {"a": 1, "b": "two"}"""
    found = re.findall(r"(\w+)\s*[:=]\s*([^,;\n]+)", text)
    return {key: value(raw) for key, raw in found}


__all__ = [n for n, v in globals().items() if callable(v) and v.__module__ == __name__ and n[0] != "_"]
