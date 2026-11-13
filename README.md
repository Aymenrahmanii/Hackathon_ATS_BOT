# Double Trouble bot

Strategy and schedule: [PLAN.md](PLAN.md).

## Setup (once, while online)

    uv sync
    cp config.example.toml config.toml     # then put the real URL and logins in it

## Run

    uv run python -m mockserver.server --rivals 3     # local practice server
    uv run python -m dt.bot --player a                # one bot per account
    uv run python -m dt.bot --player b
    uv run pytest -q

## Add a solver while the bot runs

1. The bot prints each new type and saves its questions to `data/samples/<type>.jsonl`.
2. Copy `solvers/_template.py` to `solvers/<type>.py` (exact type name) and write `solve`.
3. Check it without touching the server: `uv run python -m dt.try_solver <type>`
4. Save. The running bot loads it, tries one claim, and pauses it on a wrong answer
   (details land in `data/failures/<type>.jsonl`). Edit the file to retry.

## Drills (rehearse the real day)

Three packs of nine question types you have not seen: three timed rounds of x1, x2, x3.

    uv run python -m mockserver.server --drill 1 --round-minutes 20 --rivals 3

1. Turn Wi-Fi off. Only the terminal, your editor, `python -m dt.toolkit` and pydoc.
2. Start the server, then one bot per player. Empty `solvers/` first (keep `_template.py`).
3. Write solvers as the types appear. Rounds switch on their own.
4. Watch http://127.0.0.1:8000/mock/scoreboard : standings, time left, and how long you
   took to land each type. Targets: first solver under 5 min, x3 under 20 min.
5. Afterwards compare your solvers with `drills/answer_key/`.

Rival teams "ship" their solvers after a delay (the fastest has x3 after 9 minutes), every
second rival team defends itself, and questions change on every run.

**Spoilers:** do not open `mockserver/drills.py`, `drills/answer_key/` or
`tests/test_drills.py` before playing a pack. Each pack only works once per person.

## Toolkit (the offline replacement for Google)

    from dt.toolkit import *                 # in a solver
    uv run python -m dt.toolkit              # index of all 84 helpers, one line each
    uv run python -m dt.toolkit palindrome   # search the index
    uv run python -m pydoc dt.toolkit.algos  # full help for one module

| Module | For |
|---|---|
| `parse` | getting numbers, quoted strings, lists, JSON out of the question |
| `jsfmt` | printing the answer the way JavaScript would (`js_str`, `to_fixed`, `js_round`...) |
| `text` | ciphers, Morse, Roman numerals, base64/hex/bits, run-length, number words |
| `algos` | safe calculator, primes, sequences, grid and graph paths, DP, sudoku, dates |

Finish every solver with `js_str(result)` unless the question asks for another format.
Editing a toolkit file needs a bot restart; solver files do not.

## Combat

Each slot goes to the first of these that applies: burst, defend myself, defend my
teammate, attack a scoring rival near us in the standings, claim, discover, attack anyone.

- Defense and burst are always on.
- `attack_mode` in `config.toml`: `"always"` (default), `"idle"` (attack only when there
  is nothing to claim) or `"off"`. Changing it needs a bot restart.
- A rival who shakes off our attack within 30 s is marked a defender and left alone.

## Where things are

| File | Job |
|---|---|
| `dt/client.py` | one method per endpoint, logs every call to `data/logs/` |
| `dt/throttle.py` | the only code that may call throttled endpoints |
| `dt/pool.py` | discovered nuggets, teammate split, staleness |
| `dt/registry.py` | hot-reload and probation of solvers |
| `dt/combat.py` | who to defend, when to burst, who to attack |
| `dt/bot.py` | the loop; `_choose` is the priority order of actions |
| `mockserver/` | local clone of the game; `# ASSUMPTION` marks guesses to verify in the warm-up |

Mock controls: `POST /mock/round/2`, `POST /mock/config?p503=0.1&rival_attack_p=0.03&token_ttl_s=20`.
