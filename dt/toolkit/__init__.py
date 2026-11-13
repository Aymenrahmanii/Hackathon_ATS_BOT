"""Helpers for writing solvers fast, with no internet.

In a solver:        from dt.toolkit import *
Offline index:      python -m dt.toolkit            (every helper, one line each)
Search the index:   python -m dt.toolkit prime
Full help:          python -m pydoc dt.toolkit.algos

Editing a toolkit file needs a bot restart (solver files do not). If a helper
needs fixing mid-round, copy it into the solver file instead.
"""

from dt.toolkit.algos import *  # noqa: F401,F403
from dt.toolkit.jsfmt import *  # noqa: F401,F403
from dt.toolkit.parse import *  # noqa: F401,F403
from dt.toolkit.text import *  # noqa: F401,F403
