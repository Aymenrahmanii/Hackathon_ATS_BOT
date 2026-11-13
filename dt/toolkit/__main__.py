"""Print the toolkit index: python -m dt.toolkit [search word]"""

from __future__ import annotations

import inspect
import sys

from dt.toolkit import algos, jsfmt, parse, text

BUILT_IN = """\
Already in Python (no import from the toolkit needed)
  s[::-1]  s.upper()  s.title()  s.swapcase()  s.split()  sep.join(xs)  s.count(x)
  sorted(xs, reverse=True)  sorted(xs, key=len)  min  max  sum  len  set(xs)  abs  round
  math: gcd lcm factorial comb perm isqrt sqrt floor ceil prod    pow(a, b, mod)
  int("ff", 16)  bin(n)  hex(n)  oct(n)  divmod(a, b)  chr(n)  ord(c)
  itertools: permutations combinations product accumulate
  collections: Counter(xs).most_common(1)  deque  defaultdict
  statistics: mean median mode stdev      fractions.Fraction      datetime, calendar.isleap
"""


def main() -> None:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    for module in (parse, jsfmt, text, algos):
        lines = []
        for name in module.__all__:
            function = getattr(module, name)
            summary = (inspect.getdoc(function) or "").splitlines()[0]
            signature = str(inspect.signature(function)).replace("'", "")
            line = f"  {name}{signature}\n      {summary}"
            if needle in line.lower():
                lines.append(line)
        if lines:
            print(f"\n{module.__name__.split('.')[-1]}: {(module.__doc__ or '').strip().splitlines()[0]}")
            print("\n".join(lines))
    if not needle:
        print("\n" + BUILT_IN)


if __name__ == "__main__":
    main()
