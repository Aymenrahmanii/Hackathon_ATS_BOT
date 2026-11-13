"""Practice question types for the mock. Each generator returns (content, answer).

The real types are unknown until each round starts; these only exercise the bot.
For drills, one teammate adds new generators here and the other solves them blind.
"""

from __future__ import annotations

import random
from collections.abc import Callable

Generator = Callable[[random.Random], tuple[str, str]]

WORDS = [
    "hello", "nugget", "throttle", "double", "trouble", "python", "burst", "attack",
    "defend", "level", "radar", "claim", "discover", "round", "kayak", "score",
]


def reverse_word(rng: random.Random) -> tuple[str, str]:
    word = rng.choice(WORDS)
    return f'What is "{word}" spelled backwards?', word[::-1]


def add_numbers(rng: random.Random) -> tuple[str, str]:
    a, b = rng.randint(1, 999), rng.randint(1, 999)
    return f"What is {a} + {b}?", str(a + b)


def count_vowels(rng: random.Random) -> tuple[str, str]:
    phrase = " ".join(rng.sample(WORDS, 3))
    return f'How many vowels are in "{phrase}"?', str(sum(c in "aeiou" for c in phrase))


def upper_case(rng: random.Random) -> tuple[str, str]:
    phrase = " ".join(rng.sample(WORDS, 2))
    return f'Write "{phrase}" in uppercase.', phrase.upper()


def max_number(rng: random.Random) -> tuple[str, str]:
    numbers = [rng.randint(-500, 500) for _ in range(rng.randint(4, 8))]
    return f"What is the largest number in [{', '.join(map(str, numbers))}]?", str(max(numbers))


def is_palindrome(rng: random.Random) -> tuple[str, str]:
    word = rng.choice(WORDS)
    return f'Is "{word}" a palindrome? Answer true or false.', str(word == word[::-1]).lower()


def word_count(rng: random.Random) -> tuple[str, str]:
    words = rng.choices(WORDS, k=rng.randint(3, 9))
    return f'How many words are in "{" ".join(words)}"?', str(len(words))


def multiply(rng: random.Random) -> tuple[str, str]:
    a, b = rng.randint(-99, 99), rng.randint(2, 99)
    return f"What is {a} times {b}?", str(a * b)


def sort_numbers(rng: random.Random) -> tuple[str, str]:
    numbers = [rng.randint(0, 200) for _ in range(rng.randint(4, 7))]
    question = f"Sort these numbers in ascending order: {', '.join(map(str, numbers))}"
    return question, ",".join(map(str, sorted(numbers)))


# round number -> the three types, in coefficient order (x1, x2, x3)
ROUNDS: dict[int, list[tuple[str, Generator]]] = {
    1: [("reverseWord", reverse_word), ("addNumbers", add_numbers), ("countVowels", count_vowels)],
    2: [("upperCase", upper_case), ("maxNumber", max_number), ("isPalindrome", is_palindrome)],
    3: [("wordCount", word_count), ("multiply", multiply), ("sortNumbers", sort_numbers)],
}
