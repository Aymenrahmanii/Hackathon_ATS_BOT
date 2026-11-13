"""Copy to <nuggetType>.py (exact type name). Files starting with _ are ignored.

The running bot loads the file as soon as it is saved. Try it first:
    python -m dt.try_solver <nuggetType>
List the helpers:
    python -m dt.toolkit [search word]
"""

from dt.toolkit import *  # noqa: F403


def solve(content: str) -> str:
    # 1. pull the data out of the question text
    #    ints(content)  numbers(content)  quoted(content)  lists(content)  after(content, ":")
    values = ints(content)
    # 2. compute
    result = sum(values)
    # 3. return EXACT text. js_str gives JavaScript formatting:
    #    True -> "true", 3.0 -> "3", [1, 2] -> "1,2"
    return js_str(result)
