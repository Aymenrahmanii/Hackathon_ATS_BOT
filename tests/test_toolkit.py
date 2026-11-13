"""Every toolkit helper, checked against known answers."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from dt import toolkit
from dt.registry import Registry
from dt.toolkit import *  # noqa: F403
from dt.toolkit import algos, jsfmt, parse, text

# --- parse ----------------------------------------------------------------------


def test_numbers_from_text() -> None:
    assert ints("add 12 and -7 to 3") == [12, -7, 3]
    assert ints("3-5", signed=False) == [3, 5]
    assert numbers("2.5 kg, 4 items, -1e3") == [2.5, 4, -1000.0]


def test_quoted_prefers_double_quotes() -> None:
    assert quoted('What is "hello" spelled backwards?') == ["hello"]
    assert quoted('Is "don\'t stop" a phrase?') == ["don't stop"]
    assert quoted("Reverse 'abc' and 'de'") == ["abc", "de"]
    assert quoted("Use “curly” ones") == ["curly"]
    assert quoted("nothing here") == []


def test_lists_and_values() -> None:
    assert lists("max of [3, 10, -2] and [a, 'b']") == [[3, 10, -2], ["a", "b"]]
    assert csv("3, 4.5, x, true") == [3, 4.5, "x", True]
    assert value(" null ") is None and value("7") == 7


def test_cutting_text() -> None:
    assert after("Sort these: 3, 1", ":") == "3, 1"
    assert between("f(x+1) = ?", "(", ")") == "x+1"
    assert words("Hi, it's me!") == ["Hi", "it's", "me"]
    assert pairs("a=1, b: two") == {"a": 1, "b": "two"}


def test_json_in_text() -> None:
    assert json_in('Sum the values of {"a": 1, "b": [2, 3]} please') == {"a": 1, "b": [2, 3]}
    assert json_in("use [1, 2] now") == [1, 2]
    with pytest.raises(ValueError):
        json_in("no json")


# --- JavaScript formatting ---------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (True, "true"), (False, "false"), (None, "null"), (42, "42"), (3.0, "3"), (-0.0, "0"),
        (2.5, "2.5"), (0.1 + 0.2, "0.30000000000000004"), (1 / 3, "0.3333333333333333"),
        (100.0, "100"), (123.456, "123.456"), (1e21, "1e+21"), (1e20, "100000000000000000000"),
        (0.000001, "0.000001"), (0.0000001, "1e-7"), (1.5e-7, "1.5e-7"), (-1234.5, "-1234.5"),
        (float("inf"), "Infinity"), (float("nan"), "NaN"),
        ([1, [2, 3], None, True], "1,2,3,,true"), ("text", "text"), ({"a": 1}, "[object Object]"),
    ],
)
def test_js_str(given: object, expected: str) -> None:
    assert js_str(given) == expected


def test_js_json() -> None:
    assert js_json({"a": 1, "b": [1.0, "x", 2.5], "c": None, "d": True}) == '{"a":1,"b":[1,"x",2.5],"c":null,"d":true}'
    assert js_json("é") == '"é"'


def test_js_rounding_and_arithmetic() -> None:
    assert [js_round(x) for x in (2.5, -2.5, -2.6, 0.49999999999999994, 3.2)] == [3, -2, -3, 0, 3]
    assert [to_fixed(1.005), to_fixed(2.5, 0), to_fixed(-2.5, 0), to_fixed(1.45, 1)] == ["1.00", "3", "-3", "1.4"]
    assert [to_fixed(3), to_fixed(1234.5678, 1)] == ["3.00", "1234.6"]
    assert [to_fixed(-0.0), to_fixed(-0.001)] == ["0.00", "-0.00"]  # both checked against Node
    assert (js_mod(-7, 3), js_mod(7, -3), js_mod(5.5, 2)) == (-1, 1, 1.5)
    assert (js_int_div(-7, 2), js_int_div(7, 2)) == (-3, 3)
    assert js_sort([10, 9, 1, 100]) == [1, 10, 100, 9]


# --- text -------------------------------------------------------------------------


def test_counting() -> None:
    assert (count_vowels("Hello World"), count_consonants("Hello World!")) == (3, 7)
    assert char_counts("aab c", letters_only=True).most_common(1) == [("a", 2)]
    assert is_palindrome("A man, a plan, a canal: Panama") and not is_palindrome("Ab a", strict=True)
    assert is_anagram("Listen", "Silent") and not is_anagram("abc", "abd")
    assert reverse_words("one two  three") == "three two one"


def test_run_length() -> None:
    assert runs("aaabcc") == [("a", 3), ("b", 1), ("c", 2)]
    assert rle_encode("aaabcc") == "a3b1c2"
    assert rle_encode("aaabcc", count_first=True) == "3a1b2c"
    assert rle_encode("aaabcc", ones=False) == "a3bc2"
    assert rle_decode("a3b1c2") == rle_decode("3a1b2c") == rle_decode("a3bc2") == "aaabcc"


def test_ciphers() -> None:
    assert caesar("Hello, World!", 3) == "Khoor, Zruog!"
    assert caesar(caesar("abc xyz", 5), -5) == "abc xyz"
    assert vigenere("attack at dawn", "lemon") == "lxfopv ef rnhr"
    assert vigenere("lxfopv ef rnhr", "lemon", decrypt=True) == "attack at dawn"
    assert atbash("abc XYZ") == "zyx CBA"


def test_encodings() -> None:
    assert to_morse("SOS help") == "... --- ... / .... . .-.. .--."
    assert from_morse("... --- ... / .... . .-.. .--.") == "sos help"
    assert (b64_encode("hello"), b64_decode("aGVsbG8=")) == ("aGVsbG8=", "hello")
    assert (hex_encode("hi"), hex_decode("68 69")) == ("6869", "hi")
    assert (to_bits("hi"), from_bits("0110100001101001")) == ("01101000 01101001", "hi")
    assert hash_hex("hello") == "5d41402abc4b2a76b9719d911017c592"
    assert hash_hex("hello", "sha256").startswith("2cf24dba5fb0a30e")


def test_case_styles() -> None:
    assert split_words("myVar_name-x") == ["my", "var", "name", "x"]
    assert (camel_case("my var_name"), snake_case("myVarName")) == ("myVarName", "my_var_name")


def test_numerals() -> None:
    assert (to_roman(1994), from_roman("MCMXCIV"), to_roman(3888)) == ("MCMXCIV", 1994, "MMMDCCCLXXXVIII")
    assert all(from_roman(to_roman(n)) == n for n in range(1, 400))
    assert number_to_words(1234) == "one thousand two hundred thirty-four"
    assert number_to_words(1_000_005) == "one million five"
    assert words_to_number("two thousand and twenty-six") == 2026
    assert words_to_number("minus forty two") == -42
    assert all(words_to_number(number_to_words(n)) == n for n in (0, 13, 70, 101, 999, 54321))


# --- algorithms -------------------------------------------------------------------


def test_calc_and_rpn() -> None:
    assert calc("2 + 3 * (4 - 1)") == 11
    assert (calc("2^10"), calc("7 / 2"), calc("-3 x 4"), calc("10 ÷ 4"), calc("17 % 5")) == (1024, 3.5, -12, 2.5, 2)
    assert js_str(calc("6 / 2")) == "3"
    assert rpn("3 4 + 2 *") == 14
    for dangerous in ("__import__('os')", "open('x')", "a + 1", "9 ** 99999"):
        with pytest.raises((ValueError, SyntaxError)):
            calc(dangerous)


def test_number_theory() -> None:
    assert [n for n in range(20) if is_prime(n)] == primes_upto(19) == [2, 3, 5, 7, 11, 13, 17, 19]
    assert (nth_prime(1), nth_prime(10), primes_upto(1)) == (2, 29, [])
    assert prime_factors(360) == [2, 2, 2, 3, 3, 5] and prime_factors(97) == [97]
    assert divisors(12) == [1, 2, 3, 4, 6, 12]
    assert [fib(n) for n in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]
    assert (digit_sum(-493), to_base(255, 16), to_base(5, 2), to_base(0, 2), collatz_steps(6)) == (16, "ff", "101", "0", 8)


def test_sequences() -> None:
    assert next_term([3, 7, 11]) == 15
    assert next_term([2, 6, 18]) == 54
    assert next_term([1, 0.5, 0.25]) == 0.125
    assert next_term([1, 1, 2, 3, 5, 8]) == 13
    assert next_term([1, 4, 9, 16]) == 25
    assert next_term([1, 8, 27, 64, 125]) == 216
    assert max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6
    assert longest_increasing([10, 9, 2, 5, 3, 7, 101, 18]) == 4


def test_string_algorithms() -> None:
    assert balanced("{[()]}<>") and not balanced("(]") and not balanced("((")
    assert (edit_distance("kitten", "sitting"), edit_distance("", "abc")) == (3, 3)
    assert hamming("karolin", "kathrin") == 3
    assert len(lcs("ABCBDAB", "BDCABA")) == 4 and lcs("abc", "xyz") == ""
    assert common_substring("xabcdy", "zbcdw") == "bcd"


def test_grids_and_graphs() -> None:
    maze = parse_grid("""
        S.#.
        .##.
        ...E
    """)
    path = shortest_path(maze, find(maze, "S"), find(maze, "E"))
    assert path is not None and len(path) - 1 == 5
    assert shortest_path(["S#E"], (0, 0), (0, 2)) is None
    assert len(shortest_path(["S..", "...", "..E"], (0, 0), (2, 2), diagonal=True)) - 1 == 2
    graph = {"A": {"B": 1, "C": 4}, "B": {"C": 2, "D": 6}, "C": {"D": 1}, "D": {}}
    assert dijkstra(graph, "A", "D") == (4, ["A", "B", "C", "D"])
    assert dijkstra(graph, "D", "A") == (math.inf, [])
    assert bfs_path(lambda node: graph[node], "A", "D") == ["A", "B", "D"]
    assert count_islands(["110", "001", "001"]) == 2
    assert count_islands(["110", "001", "001"], diagonal=True) == 1


def test_dynamic_programming() -> None:
    assert knapsack([(1, 1), (3, 4), (4, 5), (5, 7)], 7) == 9
    assert (min_coins([1, 5, 10, 25], 63), min_coins([5], 3)) == (6, -1)
    assert coin_ways([1, 2, 5], 5) == 4


def test_matrices() -> None:
    assert mat_mul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19, 22], [43, 50]]
    assert rotate([[1, 2], [3, 4]]) == [[3, 1], [4, 2]]
    assert rotate([[1, 2], [3, 4]], clockwise=False) == [[2, 4], [1, 3]]
    assert (determinant([[1, 2], [3, 4]]), determinant([[2, 0, 0], [0, 3, 0], [0, 0, 4]])) == (-2, 24)
    assert determinant([[1, 2], [2, 4]]) == 0


def test_classic_puzzles() -> None:
    puzzle = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
    solved = sudoku(puzzle)
    assert solved is not None and solved[0] == [5, 3, 4, 6, 7, 8, 9, 1, 2]
    assert all(sorted(row) == list(range(1, 10)) for row in solved)
    assert all(sorted(column) == list(range(1, 10)) for column in zip(*solved))
    assert [n_queens(n) for n in (1, 4, 6, 8)] == [1, 2, 4, 92]


def test_dates() -> None:
    forms = ["2026-11-25", "25/11/2026", "November 25, 2026", "25 Nov 2026", "25th November 2026"]
    assert len({parse_date(form) for form in forms}) == 1
    assert weekday("2026-11-25") == "Wednesday"
    assert days_between("2026-11-13", "November 25, 2026") == 12


# --- the toolkit as a whole ---------------------------------------------------------


def test_every_helper_is_exported_and_documented() -> None:
    for module in (parse, jsfmt, text, algos):
        assert module.__all__, module.__name__
        for name in module.__all__:
            assert getattr(toolkit, name) is getattr(module, name), f"{name} is shadowed"
            assert (getattr(module, name).__doc__ or "").strip(), f"{name} has no docstring"


def test_a_solver_can_use_the_toolkit(tmp_path: Path) -> None:
    template = Path("solvers/_template.py").read_text(encoding="utf-8")
    (tmp_path / "sumNumbers.py").write_text(template, encoding="utf-8")
    registry = Registry(tmp_path, lambda _: None)
    registry.refresh()
    assert registry.solve("sumNumbers", "What is the sum of 12, 7 and 30?") == "49"
