"""SPOILERS: do not read this file before you have played the drill packs.

Three packs of nine unseen question types (three rounds of x1, x2, x3 each):

    python -m mockserver.server --drill 1 --round-minutes 20 --rivals 3

Every generator returns (content, answer). Answers are built forwards from the
data, not by calling the helper a solver would use, so the answer key in
drills/answer_key/ is an independent check (see tests/test_drills.py).
"""

from __future__ import annotations

import itertools
import json
import math
import random
from datetime import date, timedelta
from fractions import Fraction
from typing import Any

from dt.toolkit import caesar, js_str, to_roman
from mockserver.questions import Generator

WORDS = (
    "amber anchor apple arrow basket beacon breeze bridge candle canyon cedar circle cobalt "
    "comet copper coral crystal dagger delta desert dragon eagle ember falcon fern forest "
    "garden glacier harbor hazel island ivory jungle kettle lantern lemon marble meadow "
    "mirror nectar ocean olive orchid pebble pepper planet quartz raven river saddle shadow "
    "silver spider summit thunder timber tunnel valley velvet violet walnut willow winter zephyr"
).split()
NAMES = (
    "Ada Alan Barbara Claude Dennis Edsger Frances Grace Hedy Ivan John Katherine Linus "
    "Margaret Niklaus Radia Sophie Tim Ursula Vint"
).split()


def _numbers(rng: random.Random, low: int, high: int, least: int = 4, most: int = 8) -> list[int]:
    return [rng.randint(low, high) for _ in range(rng.randint(least, most))]


def _listed(values: list[Any]) -> str:
    return ", ".join(map(str, values))


# === pack 1 ======================================================================


def last_word(rng: random.Random) -> tuple[str, str]:
    words = rng.sample(WORDS, rng.randint(3, 6))
    return f'What is the last word of "{" ".join(words)}"?', words[-1]


def even_sum(rng: random.Random) -> tuple[str, str]:
    values = _numbers(rng, -50, 99)
    total = sum(v for v in values if v % 2 == 0)
    return f"What is the sum of the even numbers in {_listed(values)}?", str(total)


def caesar_decode(rng: random.Random) -> tuple[str, str]:
    plain, shift = " ".join(rng.sample(WORDS, 3)), rng.randint(1, 25)
    return f'Decode "{caesar(plain, shift)}" (Caesar cipher, shifted forward by {shift}).', plain


def to_fahrenheit(rng: random.Random) -> tuple[str, str]:
    halves = rng.randint(-80, 90)  # Celsius in half degrees, so the result has one exact decimal
    tenths = halves * 9 + 320  # Fahrenheit times ten
    answer = f"{'-' if tenths < 0 else ''}{abs(tenths) // 10}.{abs(tenths) % 10}"
    return f"Convert {js_str(halves / 2)}°C to Fahrenheit, rounded to 1 decimal.", answer


def most_frequent_word(rng: random.Random) -> tuple[str, str]:
    chosen = rng.sample(WORDS, 4)
    counts = rng.choice([[3, 2, 1, 1], [4, 2, 2, 1], [3, 1, 1, 1], [5, 4, 2, 1]])
    bag = [word for word, count in zip(chosen, counts) for _ in range(count)]
    rng.shuffle(bag)
    return f'Which word appears most often in "{" ".join(bag)}"?', chosen[0]


def _postfix(rng: random.Random, depth: int) -> tuple[str, int]:
    if depth == 0 or rng.random() < 0.25:
        number = rng.randint(1, 12)
        return str(number), number
    (left, a), (right, b) = _postfix(rng, depth - 1), _postfix(rng, depth - 1)
    symbol = rng.choice("+-*")
    result = a + b if symbol == "+" else a - b if symbol == "-" else a * b
    return f"{left} {right} {symbol}", result


def rpn_eval(rng: random.Random) -> tuple[str, str]:
    tokens, result = _postfix(rng, 3)
    while " " not in tokens:
        tokens, result = _postfix(rng, 3)
    return f"Evaluate this RPN (postfix) expression: {tokens}", str(result)


def is_leap_year(rng: random.Random) -> tuple[str, str]:
    year = rng.choice([1700, 1800, 1900, 2000, 2100, 2400, *(rng.randint(1600, 2400) for _ in range(6))])
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return f"Is {year} a leap year? Answer true or false.", "true" if leap else "false"


def sort_by_length(rng: random.Random) -> tuple[str, str]:
    chosen = rng.sample(WORDS, rng.randint(4, 6))
    ordered = sorted(chosen, key=lambda word: (len(word), word))
    question = (
        "Sort these words by length (shortest first, ties in alphabetical order) and answer "
        f"as a comma-separated list without spaces: {_listed(chosen)}"
    )
    return question, ",".join(ordered)


def _moves(grid: list[str], start: tuple[int, int], goal: tuple[int, int]) -> int | None:
    seen, frontier, steps = {start}, [start], 0
    while frontier:
        if goal in frontier:
            return steps
        reached = []
        for r, c in frontier:
            for cell in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                inside = 0 <= cell[0] < len(grid) and 0 <= cell[1] < len(grid[0])
                if inside and grid[cell[0]][cell[1]] != "#" and cell not in seen:
                    seen.add(cell)
                    reached.append(cell)
        frontier, steps = reached, steps + 1
    return None


def maze_steps(rng: random.Random) -> tuple[str, str]:
    while True:
        height, width = rng.randint(4, 6), rng.randint(5, 8)
        cells = [["#" if rng.random() < 0.28 else "." for _ in range(width)] for _ in range(height)]
        start, goal = rng.sample([(r, c) for r in range(height) for c in range(width)], 2)
        cells[start[0]][start[1]], cells[goal[0]][goal[1]] = "S", "E"
        grid = ["".join(row) for row in cells]
        steps = _moves(grid, start, goal)
        if steps is not None and steps >= 4:
            break
    question = "What is the fewest number of moves from S to E? (# is a wall; move up, down, left or right)\n"
    return question + "\n".join(grid), str(steps)


# === pack 2 ======================================================================


def count_letter(rng: random.Random) -> tuple[str, str]:
    phrase = " ".join(rng.sample(WORDS, 3))
    letter = rng.choice(phrase.replace(" ", "") + "qxz")
    return f'How many times does the letter "{letter}" appear in "{phrase}"?', str(phrase.count(letter))


def roman_to_number(rng: random.Random) -> tuple[str, str]:
    number = rng.randint(1, 3999)
    return f"What is the Roman numeral {to_roman(number)} as a number?", str(number)


def next_number(rng: random.Random) -> tuple[str, str]:
    kind, length = rng.choice(["step", "ratio", "square", "fibonacci"]), rng.randint(5, 6)
    if kind == "step":
        first, step = rng.randint(-20, 40), rng.choice([-7, -4, -3, 3, 5, 6, 9, 11])
        series = [first + step * i for i in range(length + 1)]
    elif kind == "ratio":
        first, ratio = rng.randint(1, 5), rng.randint(2, 4)
        series = [first * ratio**i for i in range(length + 1)]
    elif kind == "square":
        offset = rng.randint(-3, 9)
        series = [i * i + offset for i in range(1, length + 2)]
    else:
        series = [rng.randint(1, 6), rng.randint(1, 9)]
        while len(series) <= length:
            series.append(series[-1] + series[-2])
    return f"What number comes next: {_listed(series[:-1])}, ?", str(series[-1])


def average_rounded(rng: random.Random) -> tuple[str, str]:
    values = _numbers(rng, 1, 100, least=3, most=8)
    # Rounded the way JavaScript's toFixed does: 6.125 -> "6.13", and always two decimals.
    cents = math.floor(Fraction(sum(values), len(values)) * 100 + Fraction(1, 2))
    question = f"What is the average of {_listed(values)}, rounded to 2 decimals?"
    return question, f"{cents // 100}.{cents % 100:02d}"


def base_convert(rng: random.Random) -> tuple[str, str]:
    source, target = rng.sample([2, 8, 10, 16], 2)
    number = rng.randint(1, 4095)
    style = {2: "b", 8: "o", 10: "d", 16: "x"}
    question = f"Convert {number:{style[source]}} from base {source} to base {target}."
    return question, f"{number:{style[target]}}"


def _json_value(rng: random.Random, depth: int) -> Any:
    roll = rng.random()
    if depth >= 3 or roll < 0.45:
        return rng.randint(-20, 60)
    if roll < 0.6:
        return rng.choice(["x", "12", "n/a", "7 items", True, False, None])
    if roll < 0.8:
        return [_json_value(rng, depth + 1) for _ in range(rng.randint(1, 3))]
    return {key: _json_value(rng, depth + 1) for key in rng.sample("abcdefgh", rng.randint(1, 3))}


def _total(node: Any) -> int:
    if isinstance(node, bool):
        return 0
    if isinstance(node, int):
        return node
    if isinstance(node, list):
        return sum(_total(item) for item in node)
    if isinstance(node, dict):
        return sum(_total(item) for item in node.values())
    return 0


def json_sum(rng: random.Random) -> tuple[str, str]:
    data = {key: _json_value(rng, 1) for key in rng.sample("pqrstuvw", rng.randint(3, 5))}
    question = "What is the sum of all the numbers in this JSON (strings and booleans do not count)? "
    return question + json.dumps(data), str(_total(data))


def initials(rng: random.Random) -> tuple[str, str]:
    chosen = rng.sample(NAMES, rng.randint(2, 4))
    return f'What are the initials of "{" ".join(chosen)}"?', "".join(name[0] for name in chosen)


def days_from_to(rng: random.Random) -> tuple[str, str]:
    first = date(2019, 1, 1) + timedelta(days=rng.randint(0, 3000))
    gap = rng.randint(1, 900)
    return f"How many days are there from {first} to {first + timedelta(days=gap)}?", str(gap)


def fewest_coins(rng: random.Random) -> tuple[str, str]:
    coins = rng.choice([[1, 3, 4], [1, 5, 6, 9], [1, 4, 5], [1, 7, 10], [1, 5, 10, 25], [1, 6, 10]])
    amount = rng.randint(6, 60)
    need = [0] + [math.inf] * amount
    for total in range(1, amount + 1):
        need[total] = 1 + min(need[total - coin] for coin in coins if coin <= total)
    question = f"What is the fewest number of coins needed to make {amount} using coins of {_listed(coins)}?"
    return question, str(need[amount])


# === pack 3 ======================================================================


def title_case(rng: random.Random) -> tuple[str, str]:
    chosen = rng.sample(WORDS, rng.randint(3, 5))
    question = f'Capitalize the first letter of every word in "{" ".join(chosen)}".'
    return question, " ".join(word[0].upper() + word[1:] for word in chosen)


def prime_factor_list(rng: random.Random) -> tuple[str, str]:
    factors = sorted(rng.choice([2, 2, 2, 3, 3, 5, 7, 11, 13]) for _ in range(rng.randint(2, 5)))
    question = (
        f"What are the prime factors of {math.prod(factors)}, smallest first? "
        "Answer as a comma-separated list without spaces."
    )
    return question, ",".join(map(str, factors))


def cheapest_route(rng: random.Random) -> tuple[str, str]:
    towns = list("ABCDEFG"[: rng.randint(5, 7)])
    order = rng.sample(towns, len(towns))
    roads: dict[tuple[str, str], int] = {}
    for a, b in zip(order, order[1:]):  # a chain first, so the map is connected
        roads[tuple(sorted((a, b)))] = rng.randint(2, 9)
    for _ in range(rng.randint(2, 5)):
        a, b = rng.sample(towns, 2)
        roads.setdefault(tuple(sorted((a, b))), rng.randint(1, 9))
    cost = {town: math.inf for town in towns} | {order[0]: 0}
    for _ in towns:  # Bellman-Ford: relax every road, as many times as there are towns
        for (a, b), price in roads.items():
            cost[a], cost[b] = min(cost[a], cost[b] + price), min(cost[b], cost[a] + price)
    listing = ", ".join(f"{a}-{b}:{price}" for (a, b), price in roads.items())
    question = (
        f"Roads (two-way) with their costs: {listing}. "
        f"What is the cheapest total cost to travel from {order[0]} to {order[-1]}?"
    )
    return question, str(cost[order[-1]])


def number_spread(rng: random.Random) -> tuple[str, str]:
    values = _numbers(rng, -99, 99)
    question = f"What is the difference between the largest and the smallest of these numbers: {_listed(values)}?"
    return question, str(max(values) - min(values))


def run_length_encode(rng: random.Random) -> tuple[str, str]:
    letters: list[str] = []
    for _ in range(rng.randint(3, 6)):
        letters.append(rng.choice([c for c in "abcdxyz" if c != (letters[-1] if letters else "")]))
    text = "".join(letter * rng.randint(1, 5) for letter in letters)
    question = f'Run-length encode "{text}": each letter followed by its count, so "aab" becomes "a2b1".'
    return question, "".join(f"{letter}{len(list(run))}" for letter, run in itertools.groupby(text))


def evaluate(rng: random.Random) -> tuple[str, str]:
    a, b, c, d = (rng.randint(2, 20) for _ in range(4))
    e = rng.choice([2, 4, 8])  # halves, quarters, eighths: exact in binary, no float noise
    text, result = rng.choice([
        (f"({a} + {b}) * {c} - {d} / {e}", (a + b) * c - Fraction(d, e)),
        (f"{a} * {b} + {c} / {e} - {d}", a * b + Fraction(c, e) - d),
        (f"({a} - {b}) / {e} + {c} * {d}", Fraction(a - b, e) + c * d),
        (f"{a} + {b} * ({c} - {d}) / {e}", a + Fraction(b * (c - d), e)),
    ])
    return f"Evaluate: {text}", js_str(float(result))


def _dressed(letters: str, rng: random.Random) -> str:
    chunks, position = [], 0
    while position < len(letters):
        size = rng.randint(2, 5)
        chunks.append(letters[position : position + size])
        position += size
    text = " ".join(chunks).capitalize()
    if len(chunks) > 2 and rng.random() < 0.5:
        text = text.replace(" ", ", ", 1)
    return text + rng.choice(["", "!", "."])


def palindrome_phrase(rng: random.Random) -> tuple[str, str]:
    half = "".join(rng.sample(WORDS, 2))[: rng.randint(5, 9)]
    letters = half + rng.choice(["", rng.choice("aeiou")]) + half[::-1]
    truth = rng.random() < 0.5
    if not truth:
        spot = rng.randrange(len(half))
        wrong = rng.choice([c for c in "bcdfgh" if c != letters[spot]])
        letters = letters[:spot] + wrong + letters[spot + 1 :]
    question = (
        f'Is "{_dressed(letters, rng)}" a palindrome when you ignore case, spaces and '
        "punctuation? Answer true or false."
    )
    return question, "true" if truth else "false"


def clock_after(rng: random.Random) -> tuple[str, str]:
    hour, minute, later = rng.randint(0, 23), rng.randint(0, 59), rng.randint(1, 3000)
    total = hour * 60 + minute + later
    question = f"What time is it {later} minutes after {hour:02d}:{minute:02d}? Answer in 24-hour HH:MM."
    return question, f"{total // 60 % 24:02d}:{total % 60:02d}"


def island_count(rng: random.Random) -> tuple[str, str]:
    height, width = rng.randint(4, 6), rng.randint(5, 8)
    grid = ["".join("1" if rng.random() < 0.4 else "0" for _ in range(width)) for _ in range(height)]
    seen: set[tuple[int, int]] = set()
    islands = 0
    for r in range(height):
        for c in range(width):
            if grid[r][c] == "1" and (r, c) not in seen:
                islands += 1
                stack = [(r, c)]
                while stack:
                    y, x = stack.pop()
                    if (y, x) in seen or not (0 <= y < height and 0 <= x < width) or grid[y][x] != "1":
                        continue
                    seen.add((y, x))
                    stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    question = "How many islands of 1s are in this grid? (cells touching up, down, left or right belong to the same island)\n"
    return question + "\n".join(grid), str(islands)


Rounds = dict[int, list[tuple[str, Generator]]]

# pack -> round -> the three types in coefficient order (x1, x2, x3)
PACKS: dict[int, Rounds] = {
    1: {
        1: [("lastWord", last_word), ("evenSum", even_sum), ("caesarDecode", caesar_decode)],
        2: [("toFahrenheit", to_fahrenheit), ("mostFrequentWord", most_frequent_word), ("rpnEval", rpn_eval)],
        3: [("isLeapYear", is_leap_year), ("sortByLength", sort_by_length), ("mazeSteps", maze_steps)],
    },
    2: {
        1: [("countLetter", count_letter), ("romanToNumber", roman_to_number), ("nextNumber", next_number)],
        2: [("averageRounded", average_rounded), ("baseConvert", base_convert), ("jsonSum", json_sum)],
        3: [("initials", initials), ("daysFromTo", days_from_to), ("fewestCoins", fewest_coins)],
    },
    3: {
        1: [("titleCase", title_case), ("primeFactorList", prime_factor_list), ("cheapestRoute", cheapest_route)],
        2: [("numberSpread", number_spread), ("runLengthEncode", run_length_encode), ("evaluate", evaluate)],
        3: [("palindromePhrase", palindrome_phrase), ("clockAfter", clock_after), ("islandCount", island_count)],
    },
}
