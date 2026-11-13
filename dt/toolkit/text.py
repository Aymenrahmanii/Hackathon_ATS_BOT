"""String puzzles: ciphers, encodings, counting, numerals."""

from __future__ import annotations

import base64
import hashlib
import re
from collections import Counter

VOWELS = "aeiouAEIOU"
_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.",
    "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.",
    "o": "---", "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-", "u": "..-",
    "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..", "0": "-----",
    "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
    "7": "--...", "8": "---..", "9": "----.",
}
_FROM_MORSE = {code: char for char, code in _MORSE.items()}
_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_SCALES = {"thousand": 10**3, "million": 10**6, "billion": 10**9}

# --- counting and tests ---------------------------------------------------------


def count_vowels(s: str) -> int:
    """count_vowels("Hello") -> 2 (y is not a vowel)"""
    return sum(c in VOWELS for c in s)


def count_consonants(s: str) -> int:
    """count_consonants("Hello!") -> 3"""
    return sum(c.isalpha() and c not in VOWELS for c in s)


def char_counts(s: str, letters_only: bool = False) -> Counter[str]:
    """Counter of characters. char_counts("aab").most_common(1) -> [("a", 2)]"""
    return Counter(c for c in s if c.isalpha() or not letters_only)


def is_palindrome(s: str, strict: bool = False) -> bool:
    """Ignores case, spaces and punctuation unless strict.
    is_palindrome("A man, a plan, a canal: Panama") -> True"""
    cleaned = s if strict else [c.lower() for c in s if c.isalnum()]
    return list(cleaned) == list(cleaned)[::-1]


def is_anagram(a: str, b: str) -> bool:
    """Ignores case and non-letters. is_anagram("Listen", "Silent") -> True"""
    letters = lambda s: sorted(c.lower() for c in s if c.isalnum())  # noqa: E731
    return letters(a) == letters(b)


def reverse_words(s: str) -> str:
    """Word order reversed. reverse_words("a b c") -> "c b a". (Letters: s[::-1])"""
    return " ".join(s.split()[::-1])


def runs(s: str) -> list[tuple[str, int]]:
    """Consecutive runs. runs("aaabcc") -> [("a", 3), ("b", 1), ("c", 2)]"""
    return [(match.group(1), len(match.group(0))) for match in re.finditer(r"(.)\1*", s, re.S)]


def rle_encode(s: str, count_first: bool = False, ones: bool = True) -> str:
    """rle_encode("aaabcc") -> "a3b1c2"; count_first=True -> "3a1b2c"; ones=False -> "a3bc2" """
    parts = []
    for char, count in runs(s):
        number = str(count) if ones or count > 1 else ""
        parts.append(number + char if count_first else char + number)
    return "".join(parts)


def rle_decode(s: str) -> str:
    """Accepts either order. rle_decode("a3b1c2") == rle_decode("3a1b2c") == "aaabcc" """
    if s[:1].isdigit():
        return "".join(char * int(count) for count, char in re.findall(r"(\d+)(\D)", s))
    return "".join(char * int(count or 1) for char, count in re.findall(r"(\D)(\d*)", s))


# --- ciphers ------------------------------------------------------------------------


def caesar(s: str, shift: int) -> str:
    """Shift letters, keep case and everything else. caesar("abc", 3) -> "def".
    Decrypt with -shift; ROT13 is caesar(s, 13)."""
    def move(c: str) -> str:
        if not c.isascii() or not c.isalpha():
            return c
        base = ord("a") if c.islower() else ord("A")
        return chr((ord(c) - base + shift) % 26 + base)

    return "".join(move(c) for c in s)


def vigenere(s: str, key: str, decrypt: bool = False) -> str:
    """vigenere("attack", "lemon") -> "lxfopv". The key advances on letters only."""
    shifts = [ord(k.lower()) - ord("a") for k in key if k.isalpha()]
    out, used = [], 0
    for c in s:
        if c.isascii() and c.isalpha():
            shift = shifts[used % len(shifts)]
            out.append(caesar(c, -shift if decrypt else shift))
            used += 1
        else:
            out.append(c)
    return "".join(out)


def atbash(s: str) -> str:
    """a<->z, b<->y ... atbash("abc") -> "zyx" """
    def flip(c: str) -> str:
        if not c.isascii() or not c.isalpha():
            return c
        base = ord("a") if c.islower() else ord("A")
        return chr(base + 25 - (ord(c) - base))

    return "".join(flip(c) for c in s)


# --- encodings ----------------------------------------------------------------------


def to_morse(s: str) -> str:
    """Letters split by spaces, words by " / ". to_morse("hi yo") -> ".... .. / -.-- ---" """
    return " / ".join(" ".join(_MORSE[c] for c in word.lower() if c in _MORSE) for word in s.split())


def from_morse(s: str) -> str:
    """from_morse(".... .. / -.-- ---") -> "hi yo" (lowercase)"""
    words = re.split(r"\s*/\s*|\s{3,}", s.strip())
    return " ".join("".join(_FROM_MORSE[code] for code in word.split()) for word in words)


def b64_encode(s: str) -> str:
    """b64_encode("hi") -> "aGk=" """
    return base64.b64encode(s.encode()).decode()


def b64_decode(s: str) -> str:
    """b64_decode("aGk=") -> "hi" """
    return base64.b64decode(s).decode()


def hex_encode(s: str) -> str:
    """hex_encode("hi") -> "6869" """
    return s.encode().hex()


def hex_decode(s: str) -> str:
    """hex_decode("68 69") -> "hi" (spaces allowed)"""
    return bytes.fromhex(s).decode()


def to_bits(s: str, sep: str = " ") -> str:
    """8 bits per character. to_bits("hi") -> "01101000 01101001" """
    return sep.join(f"{byte:08b}" for byte in s.encode())


def from_bits(s: str) -> str:
    """from_bits("01101000 01101001") -> "hi" (spaces optional)"""
    bits = re.sub(r"[^01]", "", s)
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8)).decode()


def hash_hex(s: str, algorithm: str = "md5") -> str:
    """hash_hex("hello") -> md5 hex digest; algorithm: "sha1", "sha256", ..."""
    return hashlib.new(algorithm, s.encode()).hexdigest()


# --- case styles --------------------------------------------------------------------


def split_words(s: str) -> list[str]:
    """Words of any identifier style, lowercased. split_words("myVar_name-x") -> ["my", "var", "name", "x"]"""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return [word.lower() for word in re.split(r"[\s_\-]+", spaced) if word]


def camel_case(s: str) -> str:
    """camel_case("my var_name") -> "myVarName" """
    first, *rest = split_words(s)
    return first + "".join(word.capitalize() for word in rest)


def snake_case(s: str) -> str:
    """snake_case("myVarName") -> "my_var_name" (kebab: "-".join(split_words(s)))"""
    return "_".join(split_words(s))


# --- numerals -----------------------------------------------------------------------


def to_roman(n: int) -> str:
    """to_roman(1994) -> "MCMXCIV" """
    out = []
    for amount, symbol in _ROMAN:
        count, n = divmod(n, amount)
        out.append(symbol * count)
    return "".join(out)


def from_roman(s: str) -> int:
    """from_roman("MCMXCIV") -> 1994"""
    values = {symbol: amount for amount, symbol in _ROMAN if len(symbol) == 1}
    numbers = [values[c] for c in s.upper()]
    return sum(-n if n < later else n for n, later in zip(numbers, numbers[1:] + [0]))


def number_to_words(n: int) -> str:
    """number_to_words(1234) -> "one thousand two hundred thirty-four" (no "and")"""
    if n < 0:
        return "minus " + number_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _ONES[hundreds] + " hundred" + (" " + number_to_words(rest) if rest else "")
    for name, scale in reversed(_SCALES.items()):
        if n >= scale:
            high, rest = divmod(n, scale)
            tail = " " + number_to_words(rest) if rest else ""
            return f"{number_to_words(high)} {name}{tail}"
    raise ValueError(n)


def words_to_number(s: str) -> int:
    """words_to_number("two thousand and twenty-six") -> 2026"""
    total = current = 0
    tokens = re.findall(r"[a-z]+", s.lower())
    for token in tokens:
        if token in _ONES:
            current += _ONES.index(token)
        elif token in _TENS:
            current += _TENS.index(token) * 10
        elif token == "hundred":
            current *= 100
        elif token in _SCALES:
            total += current * _SCALES[token]
            current = 0
        elif token not in ("and", "a", "minus", "negative"):
            raise ValueError(f"not a number word: {token}")
    sign = -1 if tokens[:1] in (["minus"], ["negative"]) else 1
    return sign * (total + current)


__all__ = [n for n, v in globals().items() if callable(v) and v.__module__ == __name__ and n[0] != "_"]
