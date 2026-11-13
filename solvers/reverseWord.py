"""Sample from the rules deck: What is "hello" spelled backwards?"""

import re


def solve(content: str) -> str:
    word = re.search(r'"(.*)"', content).group(1)
    return word[::-1]
