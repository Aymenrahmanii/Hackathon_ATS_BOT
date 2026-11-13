"""Format answers the way JavaScript would.

The game server looks like Node.js, so expected answers were most likely built
with String(x) or JSON.stringify(x). Python's str() differs in exactly the
places that break an exact-match answer: True vs true, 3.0 vs 3, [1, 2] vs 1,2.
"""

from __future__ import annotations

import json
import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def js_str(x: Any) -> str:
    """String(x) in JavaScript.
    js_str(True) -> "true", js_str(3.0) -> "3", js_str([1, [2, 3]]) -> "1,2,3",
    js_str(0.1 + 0.2) -> "0.30000000000000004", js_str(None) -> "null" """
    if isinstance(x, bool):
        return "true" if x else "false"
    if x is None:
        return "null"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return _number(x)
    if isinstance(x, (list, tuple)):
        return ",".join("" if item is None else js_str(item) for item in x)
    if isinstance(x, dict):
        return "[object Object]"
    return str(x)


def js_json(x: Any) -> str:
    """JSON.stringify(x): no spaces, 3.0 written as 3.
    js_json({"a": [1.0, True, None]}) -> '{"a":[1,true,null]}'"""
    if isinstance(x, float):
        return _number(x) if math.isfinite(x) else "null"
    if isinstance(x, (list, tuple)):
        return "[" + ",".join(js_json(item) for item in x) + "]"
    if isinstance(x, dict):
        body = ",".join(f"{json.dumps(str(k), ensure_ascii=False)}:{js_json(v)}" for k, v in x.items())
        return "{" + body + "}"
    return json.dumps(x, ensure_ascii=False)


def js_round(x: float) -> int:
    """Math.round: halves go up, also for negatives. js_round(2.5) -> 3, js_round(-2.5) -> -2
    (Python's round() gives 2 and -2: it rounds halves to the even neighbour.)"""
    low = math.floor(x)
    return low + (1 if x - low >= 0.5 else 0)


def to_fixed(x: float, digits: int = 2) -> str:
    """x.toFixed(digits). to_fixed(2.5, 0) -> "3", to_fixed(1.005) -> "1.00", to_fixed(3) -> "3.00" """
    exact = Decimal(x) if x else Decimal(0)  # JavaScript prints -0 as "0.00"...
    # ...but keeps the sign of a negative that rounds to zero: (-0.001).toFixed(2) is "-0.00"
    return str(exact.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def js_mod(a: float, b: float) -> float:
    """a % b in JavaScript: the sign follows a. js_mod(-7, 3) -> -1 (Python: -7 % 3 == 2)"""
    if isinstance(a, int) and isinstance(b, int):
        return int(math.copysign(abs(a) % abs(b), a))
    return math.fmod(a, b)


def js_int_div(a: float, b: float) -> int:
    """Math.trunc(a / b): toward zero. js_int_div(-7, 2) -> -3 (Python: -7 // 2 == -4)"""
    return math.trunc(a / b)


def js_sort(items: list[Any]) -> list[Any]:
    """Array.sort() with no comparator: sorts as strings!
    js_sort([10, 9, 1, 100]) -> [1, 10, 100, 9]"""
    return sorted(items, key=js_str)


def _number(x: float) -> str:
    """Number.prototype.toString, following the ECMAScript algorithm."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    sign, raw, exponent = Decimal(repr(x)).as_tuple()
    digits = "".join(map(str, raw)).rstrip("0")
    point = len(raw) + int(exponent)  # value = 0.digits * 10 ** point
    count = len(digits)
    if count <= point <= 21:
        body = digits + "0" * (point - count)
    elif 0 < point <= 21:
        body = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        body = "0." + "0" * (-point) + digits
    else:
        power = point - 1
        mantissa = digits[0] + ("." + digits[1:] if count > 1 else "")
        body = f"{mantissa}e{'+' if power > 0 else '-'}{abs(power)}"
    return ("-" if sign else "") + body


__all__ = [n for n, v in globals().items() if callable(v) and v.__module__ == __name__ and n[0] != "_"]
