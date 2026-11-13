"""Arithmetic, number theory, sequences, grids, graphs, dynamic programming, dates."""

from __future__ import annotations

import ast
import heapq
import math
import operator
import re
from collections import deque
from collections.abc import Callable, Hashable, Iterable
from datetime import date, datetime
from fractions import Fraction
from typing import Any

Number = int | float
Cell = tuple[int, int]

# --- arithmetic -----------------------------------------------------------------

_BINARY: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def calc(expression: str) -> Number:
    """Evaluate arithmetic safely (no eval). Understands + - * / // % ** ( ), and
    also x, ×, ÷ and ^ (as power). calc("2 + 3 * (4 - 1)") -> 11, calc("2^10") -> 1024.
    / is true division: calc("7 / 2") -> 3.5, calc("6 / 2") -> 3.0 (use js_str to print)."""
    text = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    text = re.sub(r"(?<=[\d)])\s*[xX]\s*(?=[\d(])", "*", text)
    return _evaluate(ast.parse(text.strip(), mode="eval").body)


def _evaluate(node: ast.expr) -> Number:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _evaluate(node.operand)
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10_000:
            raise ValueError("exponent too large")
        return _BINARY[type(node.op)](left, right)
    raise ValueError(f"not arithmetic: {ast.dump(node)}")


def rpn(expression: str) -> Number:
    """Reverse Polish notation. rpn("3 4 + 2 *") -> 14"""
    symbols = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv,
               "^": operator.pow, "%": operator.mod}
    stack: list[Number] = []
    for token in expression.split():
        if token in symbols:
            right, left = stack.pop(), stack.pop()
            stack.append(symbols[token](left, right))
        else:
            stack.append(float(token) if "." in token else int(token))
    return stack[-1]


# --- number theory -----------------------------------------------------------------
# Already in Python: math.gcd, math.lcm, math.factorial, math.comb, math.perm,
# math.isqrt, pow(a, b, mod), int("ff", 16), bin(n), hex(n), divmod(a, b).


def is_prime(n: int) -> bool:
    """is_prime(97) -> True; 0 and 1 are not prime."""
    if n < 2:
        return False
    return all(n % d for d in range(2, math.isqrt(n) + 1))


def primes_upto(n: int) -> list[int]:
    """All primes <= n. primes_upto(20) -> [2, 3, 5, 7, 11, 13, 17, 19]"""
    sieve = [True] * (n + 1)
    sieve[:2] = [False] * min(2, n + 1)
    for d in range(2, math.isqrt(n) + 1):
        if sieve[d]:
            sieve[d * d :: d] = [False] * len(sieve[d * d :: d])
    return [i for i, prime in enumerate(sieve) if prime]


def nth_prime(n: int) -> int:
    """1-indexed. nth_prime(1) -> 2, nth_prime(10) -> 29"""
    candidate, found = 1, 0
    while found < n:
        candidate += 1
        found += is_prime(candidate)
    return candidate


def prime_factors(n: int) -> list[int]:
    """With repetition. prime_factors(360) -> [2, 2, 2, 3, 3, 5]"""
    factors, divisor = [], 2
    while divisor * divisor <= n:
        while n % divisor == 0:
            factors.append(divisor)
            n //= divisor
        divisor += 1
    return factors + ([n] if n > 1 else [])


def divisors(n: int) -> list[int]:
    """Sorted. divisors(12) -> [1, 2, 3, 4, 6, 12]"""
    small = [d for d in range(1, math.isqrt(n) + 1) if n % d == 0]
    return sorted({*small, *(n // d for d in small)})


def fib(n: int) -> int:
    """0-indexed: fib(0) = 0, fib(1) = 1, fib(10) = 55. Check which index the question uses!"""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def digit_sum(n: int) -> int:
    """digit_sum(-493) -> 16"""
    return sum(int(d) for d in str(abs(n)))


def to_base(n: int, base: int) -> str:
    """Lowercase digits. to_base(255, 16) -> "ff", to_base(5, 2) -> "101".
    The other way is built in: int("ff", 16) -> 255."""
    if n == 0:
        return "0"
    digits, value = [], abs(n)
    while value:
        value, remainder = divmod(value, base)
        digits.append("0123456789abcdefghijklmnopqrstuvwxyz"[remainder])
    return ("-" if n < 0 else "") + "".join(reversed(digits))


def collatz_steps(n: int) -> int:
    """Steps to reach 1. collatz_steps(6) -> 8"""
    steps = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps


# --- sequences --------------------------------------------------------------------


def next_term(sequence: list[Number]) -> Number:
    """Next value of an arithmetic, geometric, Fibonacci-like or polynomial sequence.
    next_term([2, 6, 18]) -> 54, next_term([1, 4, 9, 16]) -> 25, next_term([1, 1, 2, 3, 5]) -> 8"""
    steps = [b - a for a, b in zip(sequence, sequence[1:])]
    if len(set(steps)) == 1:
        return sequence[-1] + steps[0]
    if 0 not in sequence:
        ratios = {Fraction(b) / Fraction(a) for a, b in zip(sequence, sequence[1:])}
        if len(ratios) == 1:
            result = Fraction(sequence[-1]) * ratios.pop()
            return int(result) if result.denominator == 1 else float(result)
    if len(sequence) >= 4 and all(c == a + b for a, b, c in zip(sequence, sequence[1:], sequence[2:])):
        return sequence[-1] + sequence[-2]
    if len(steps) < 2:
        raise ValueError("no pattern found")
    return sequence[-1] + next_term(steps)


def max_subarray(values: list[Number]) -> Number:
    """Largest sum of a contiguous run (Kadane). max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) -> 6"""
    best = current = values[0]
    for value in values[1:]:
        current = max(value, current + value)
        best = max(best, current)
    return best


def longest_increasing(values: list[Number]) -> int:
    """Length of the longest strictly increasing subsequence. [10, 9, 2, 5, 3, 7, 101, 18] -> 4"""
    lengths = [1] * len(values)
    for i, value in enumerate(values):
        for j in range(i):
            if values[j] < value:
                lengths[i] = max(lengths[i], lengths[j] + 1)
    return max(lengths, default=0)


# --- strings as sequences -----------------------------------------------------------


def balanced(s: str) -> bool:
    """Brackets match. balanced("{[()]}") -> True, balanced("(]") -> False"""
    closers, stack = {")": "(", "]": "[", "}": "{", ">": "<"}, []
    for c in s:
        if c in "([{<":
            stack.append(c)
        elif c in closers and (not stack or stack.pop() != closers[c]):
            return False
    return not stack


def edit_distance(a: str, b: str) -> int:
    """Levenshtein. edit_distance("kitten", "sitting") -> 3"""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (x != y))
    return row[-1]


def hamming(a: str, b: str) -> int:
    """Positions that differ. hamming("karolin", "kathrin") -> 3"""
    return sum(x != y for x, y in zip(a, b, strict=True))


def lcs(a: str, b: str) -> str:
    """Longest common subsequence (letters need not be adjacent). lcs("ABCBDAB", "BDCABA") has length 4"""
    table = [[""] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            table[i + 1][j + 1] = table[i][j] + x if x == y else max(table[i][j + 1], table[i + 1][j], key=len)
    return table[-1][-1]


def common_substring(a: str, b: str) -> str:
    """Longest common run of adjacent letters. common_substring("xabcdy", "zbcdw") -> "bcd" """
    best = ""
    lengths = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if x == y:
                lengths[i + 1][j + 1] = lengths[i][j] + 1
                if lengths[i + 1][j + 1] > len(best):
                    best = a[i + 1 - lengths[i + 1][j + 1] : i + 1]
    return best


# --- grids and graphs ---------------------------------------------------------------


def parse_grid(text: str) -> list[str]:
    """Non-empty lines, stripped. Index as grid[row][col]."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def find(grid: list[str], char: str) -> Cell:
    """(row, col) of the first char. find(["..S", "E.."], "E") -> (1, 0)"""
    return next((r, row.index(char)) for r, row in enumerate(grid) if char in row)


def shortest_path(
    grid: list[str], start: Cell, goal: Cell, walls: str = "#", diagonal: bool = False
) -> list[Cell] | None:
    """BFS on a grid. Returns the cells from start to goal, or None.
    Number of moves = len(path) - 1."""
    moves = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        moves += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    def around(cell: Cell) -> Iterable[Cell]:
        for dr, dc in moves:
            r, c = cell[0] + dr, cell[1] + dc
            if 0 <= r < len(grid) and 0 <= c < len(grid[r]) and grid[r][c] not in walls:
                yield r, c

    return bfs_path(around, start, goal)


def bfs_path(
    neighbours: Callable[[Any], Iterable[Any]], start: Hashable, goal: Hashable
) -> list[Any] | None:
    """Fewest-steps path in any graph; neighbours(node) yields the next nodes.
    For a dict graph: bfs_path(lambda n: graph[n], "A", "D")"""
    came_from: dict[Any, Any] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            return _walk_back(came_from, goal)
        for nxt in neighbours(node):
            if nxt not in came_from:
                came_from[nxt] = node
                queue.append(nxt)
    return None


def dijkstra(graph: dict[Any, dict[Any, Number]], start: Any, goal: Any) -> tuple[Number, list[Any]]:
    """Cheapest path in {node: {neighbour: cost}}. Returns (cost, path), or (inf, []).
    dijkstra({"A": {"B": 1, "C": 4}, "B": {"C": 2}, "C": {}}, "A", "C") -> (3, ["A", "B", "C"])"""
    best: dict[Any, Number] = {start: 0}
    came_from: dict[Any, Any] = {start: None}
    queue: list[tuple[Number, int, Any]] = [(0, 0, start)]
    counter = 0
    while queue:
        cost, _, node = heapq.heappop(queue)
        if node == goal:
            return cost, _walk_back(came_from, goal)
        if cost > best[node]:
            continue
        for nxt, weight in graph.get(node, {}).items():
            if cost + weight < best.get(nxt, math.inf):
                best[nxt], came_from[nxt] = cost + weight, node
                counter += 1
                heapq.heappush(queue, (cost + weight, counter, nxt))
    return math.inf, []


def _walk_back(came_from: dict[Any, Any], goal: Any) -> list[Any]:
    path = [goal]
    while came_from[path[-1]] is not None:
        path.append(came_from[path[-1]])
    return path[::-1]


def count_islands(grid: list[str], land: str = "1", diagonal: bool = False) -> int:
    """Connected groups of land cells. count_islands(["110", "001", "001"]) -> 2"""
    seen: set[Cell] = set()
    count = 0
    for r, row in enumerate(grid):
        for c, char in enumerate(row):
            if char in land and (r, c) not in seen:
                count += 1
                seen |= _region(grid, (r, c), land, diagonal)
    return count


def _region(grid: list[str], start: Cell, land: str, diagonal: bool) -> set[Cell]:
    seen, stack = {start}, [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            cell = (r + dr, c + dc)
            if (dr and dc and not diagonal) or cell in seen:
                continue
            if 0 <= cell[0] < len(grid) and 0 <= cell[1] < len(grid[cell[0]]):
                if grid[cell[0]][cell[1]] in land:
                    seen.add(cell)
                    stack.append(cell)
    return seen


# --- dynamic programming --------------------------------------------------------------


def knapsack(items: list[tuple[int, int]], capacity: int) -> int:
    """0/1 knapsack over (weight, value) pairs; returns the best total value.
    knapsack([(1, 1), (3, 4), (4, 5), (5, 7)], 7) -> 9"""
    best = [0] * (capacity + 1)
    for weight, worth in items:
        for room in range(capacity, weight - 1, -1):
            best[room] = max(best[room], best[room - weight] + worth)
    return best[capacity]


def min_coins(coins: list[int], amount: int) -> int:
    """Fewest coins to make the amount, or -1. min_coins([1, 5, 10, 25], 63) -> 6"""
    need = [0] + [math.inf] * amount
    for total in range(1, amount + 1):
        need[total] = min((need[total - c] + 1 for c in coins if c <= total), default=math.inf)
    return -1 if need[amount] == math.inf else int(need[amount])


def coin_ways(coins: list[int], amount: int) -> int:
    """Number of ways to make the amount (order ignored). coin_ways([1, 2, 5], 5) -> 4"""
    ways = [1] + [0] * amount
    for coin in coins:
        for total in range(coin, amount + 1):
            ways[total] += ways[total - coin]
    return ways[amount]


# --- matrices -------------------------------------------------------------------------
# Transpose is built in: [list(row) for row in zip(*m)]


def mat_mul(a: list[list[Number]], b: list[list[Number]]) -> list[list[Number]]:
    """mat_mul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) -> [[19, 22], [43, 50]]"""
    return [[sum(x * y for x, y in zip(row, column)) for column in zip(*b)] for row in a]


def rotate(m: list[list[Any]], clockwise: bool = True) -> list[list[Any]]:
    """Quarter turn. rotate([[1, 2], [3, 4]]) -> [[3, 1], [4, 2]]"""
    turned = zip(*m[::-1]) if clockwise else list(zip(*m))[::-1]
    return [list(row) for row in turned]


def determinant(m: list[list[Number]]) -> Number:
    """determinant([[1, 2], [3, 4]]) -> -2"""
    rows = [[Fraction(value) for value in row] for row in m]
    result = Fraction(1)
    for i in range(len(rows)):
        pivot = next((r for r in range(i, len(rows)) if rows[r][i] != 0), None)
        if pivot is None:
            return 0
        if pivot != i:
            rows[i], rows[pivot] = rows[pivot], rows[i]
            result = -result
        result *= rows[i][i]
        for r in range(i + 1, len(rows)):
            factor = rows[r][i] / rows[i][i]
            rows[r] = [x - factor * y for x, y in zip(rows[r], rows[i])]
    return int(result) if result.denominator == 1 else float(result)


# --- classic puzzles ------------------------------------------------------------------


def sudoku(puzzle: str | list[list[int]]) -> list[list[int]] | None:
    """Solve a 9x9 grid given as 81 characters (0 or . for blanks) or as rows of ints."""
    if isinstance(puzzle, str):
        cells = [int(c) if c.isdigit() else 0 for c in puzzle if c.isdigit() or c == "."]
        grid = [cells[i : i + 9] for i in range(0, 81, 9)]
    else:
        grid = [row[:] for row in puzzle]
    return grid if _fill(grid) else None


def _options(grid: list[list[int]], r: int, c: int) -> set[int]:
    box = {grid[i][j] for i in range(r - r % 3, r - r % 3 + 3) for j in range(c - c % 3, c - c % 3 + 3)}
    return set(range(1, 10)) - set(grid[r]) - {row[c] for row in grid} - box


def _fill(grid: list[list[int]]) -> bool:
    blanks = [(r, c) for r in range(9) for c in range(9) if grid[r][c] == 0]
    if not blanks:
        return True
    r, c = min(blanks, key=lambda cell: len(_options(grid, *cell)))
    for digit in _options(grid, r, c):
        grid[r][c] = digit
        if _fill(grid):
            return True
    grid[r][c] = 0
    return False


def n_queens(n: int) -> int:
    """Number of ways to place n queens. n_queens(8) -> 92"""
    def place(row: int, columns: int, down: int, up: int) -> int:
        if row == n:
            return 1
        free = ~(columns | down | up) & ((1 << n) - 1)
        total = 0
        while free:
            bit = free & -free
            free ^= bit
            total += place(row + 1, columns | bit, (down | bit) << 1, (up | bit) >> 1)
        return total

    return place(0, 0, 0, 0)


# --- dates ----------------------------------------------------------------------------
# calendar.isleap(year) is built in; date(2026, 11, 25) + timedelta(days=10) adds days.

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%B %d, %Y", "%d %B %Y",
                 "%b %d, %Y", "%d %b %Y", "%B %d %Y"]


def parse_date(text: str) -> date:
    """Day-first for 25/11/2026. Accepts 2026-11-25, "November 25, 2026", "25 Nov 2026", "25th November 2026"."""
    cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text.strip())
    for pattern in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            pass
    raise ValueError(f"unknown date format: {text}")


def weekday(day: date | str) -> str:
    """weekday("2026-11-25") -> "Wednesday" """
    return (parse_date(day) if isinstance(day, str) else day).strftime("%A")


def days_between(first: date | str, second: date | str) -> int:
    """second - first, in days. days_between("2026-11-13", "2026-11-25") -> 12"""
    a, b = (parse_date(d) if isinstance(d, str) else d for d in (first, second))
    return (b - a).days


__all__ = [n for n, v in globals().items() if callable(v) and v.__module__ == __name__ and n[0] != "_"]
