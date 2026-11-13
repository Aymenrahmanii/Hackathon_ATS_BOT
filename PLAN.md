# Double Trouble Reloaded — plan to win (team mode, spec v1.6)

Event: **25 Nov 2026**. Source: `hackathon.ats-digital.com/rules/team.html` (v1.6, updated 9 Nov, "subject to change until the start" — re-read it on 24 Nov and on the morning).

Items marked **[probe]** are not stated in the rules. They are my assumptions and must be settled during the warm-up, where penalties are free because scores reset.

---

## 1. What actually decides the ranking

Score = sum of coefficients of claimed nuggets, both players added. Each player gets one throttled action every 3000 ms, so the ceiling is 20 actions/min per player, 60 pts/min on 3× nuggets, **120 pts/min for the team**.

| Throttle | Actions/min | vs. baseline |
|---|---|---|
| 3000 ms | 20.0 | — |
| 4000 ms (1 attacker) | 15.0 | −25% |
| 5000 ms (2) | 12.0 | −40% |
| 6000 ms (3) | 10.0 | −50% |
| 8000 ms (cap, 5) | 7.5 | −62.5% |

Everything reduces to five levers, in order of size:

1. **Time-to-3×-solver in each round.** Every minute the bot is not on 3× costs up to 120 pts. Three rounds, nine unseen types, no internet, no AI. This is where the event is won, and it is a human skill, so it needs drills.
2. **Never stopping.** A bot that crashes on a weird response, a token expiry or a round change loses more than any tactic gains. Solvers must be hot-loaded while the bot keeps running.
3. **Wasted actions.** Wrong answers, "already claimed", needless discovers and every 429 (−1 nugget *and* a lost slot).
4. **Throttle slack.** 100 ms of safety margin on a 3000 ms throttle is 3.2% of the score. Most teams will run with 300–500 ms.
5. **Combat.** Auto-defense is mandatory; attacks are cheap and strong against the many teams that will only bring "steps 1 to 6".

## 2. Rules compliance (read this first)

- On the day: no internet, no Google, **no AI assistants**, no package installs, no phones. Only the game server and `devdocs.ats-digital.com`.
- So everything I help build must be finished, installed and *understood by both of you* before the 25th. On the day you extend it by hand. The codebase is kept deliberately small for that reason.
- Email the organisers now with these questions (answers change the plan):
  1. Is AI-assisted preparation before the day acceptable? (The deck only bans AI on the day, but ask.)
  2. May we bring our own pre-written helper library, notes and Python's bundled offline docs?
  3. Can teammates' laptops reach each other, and is a USB stick allowed to pass files?
  4. Session and round durations.
  5. Is "attack each user only once" once per session, or once while the attack is active?
  6. Any rate limit on the non-throttled endpoints (`/auth/me`, `/users`, `/teams`)?

## 3. Stack and layout

**Python 3.11+, `requests`, standard library only** at runtime. Both are on the venue DevDocs; `python -m pydoc` works offline as a second reference. Pre-install (never depend on) `numpy`, `sympy`, `networkx`, `python-dateutil`. FastAPI/uvicorn for the mock server only.

One codebase, **one process per account, one account per laptop**. Two processes on one account would 429 each other, so each bot takes a lock file. A `--player` flag lets one laptop run both accounts if the other dies.

```
dt/
  config.toml      base_url, credentials, slot (0/1), margins, thresholds
  client.py        one function per endpoint; logs every request/response as JSONL
  throttle.py      the Gate: the only code path allowed to call throttled endpoints
  state.py         watcher thread: /auth/me, /users, /teams -> shared snapshot
  pool.py          nugget pool, teammate partition, staleness, type priority
  registry.py      hot-reload of solvers/, canary mode, per-type stats
  tactics.py       picks the single next action (burst/defend/claim/discover/attack)
  bot.py           main loop + one-line status display
  toolkit/         parse.py, jsfmt.py, text.py, algos.py   (section 6)
  solvers/         one file per nuggetType: solve(content: str) -> str
  tools/try.py     run a solver over samples/<type>.jsonl and print Q -> A
  samples/ failures/ logs/
mock/server.py     full clone of the spec + chaos + simulated rivals
tests/
```

## 4. Bot design

### 4.1 Throttle gate
- Schedule `next_send = last_send + throttle + margin` on `time.monotonic()`, measured from when the previous request was *sent*.
- `margin` starts at 250 ms and is calibrated down in the warm-up (section 8).
- **Stale-throttle protection:** an attack landing mid-wait raises the throttle; firing on the old value is a 429. The watcher polls `/auth/me` about twice a second, and the gate does one final `/auth/me` pre-flight just before each throttled call and re-computes the wait.
- 429: sleep `Retry-After` + margin, count it, widen margin by 50 ms if two occur within a minute.
- 503: no penalty, retry after 100–200 ms.
- Timeout or connection error on a throttled call: assume the server processed it and wait a full throttle. Never retry immediately.
- 401: re-login, retry. Also re-login proactively at 50 min (login is not throttled).
- `requests.Session` with keep-alive, explicit timeouts, `trust_env = False`.

### 4.2 Next-action priority (one action per slot)
1. **Burst** if attackers ≥ burst threshold and score ≥ 3.
2. **Defend** self or teammate per the split rule.
3. **Claim** the nugget with the best expected value.
4. **Discover** when the pool is empty, stale, or the round changed.
5. **Attack** the next queued target.
6. Otherwise wait; never burn a slot for nothing.

Endgame guard: in the last ~15 s only claim.

### 4.3 Nugget pool
- Round start: one **unfiltered** discover to learn the new type names and coefficients; dump every nugget to `samples/<type>.jsonl` and print five examples per type.
- Afterwards discover with `?nuggetType=` for the best type we can solve.
- Solve the whole pool immediately after discover, during the idle wait.
- **Teammate partition, no communication needed:** slot 0 claims nuggets whose `_id` ends in an even hex digit, slot 1 the odd ones. Zero collisions between us; pools go stale half as fast. If the teammate's score stops moving (visible in `/api/teams`), take everything.
- **Staleness:** a 100-nugget pool takes 5 minutes to drain while every rival draws from the same nuggets. Re-discover after 2 "already claimed" in the last 5 claims. One discover costs one claim; tune the rule from the logs.
- **Type choice:** expected value = coefficient × rolling success rate × (1 − recent "already claimed" rate). A 3× solver at 60% is worth less than a 2× at 100%.
- **Depletion [probe]:** if a filtered discover returns far fewer than 100, the type is running out; fall to the next type automatically.
- **Round change:** "Nugget not found" on claims or unknown types appearing → flush pool, unfiltered discover, alert with a beep.

### 4.4 Solvers: hot reload and canary
- `registry.py` watches `solvers/` by mtime and reloads changed files. An exception or syntax error disables that solver and keeps the bot running.
- A new or changed solver starts in **canary**: one claim at a time. A wrong answer writes question + answer to `failures/<type>.jsonl`, beeps and pauses the solver until the file changes. Five straight successes makes it trusted.
- A trusted solver whose success rate drops under 70% over 10 claims is demoted and flagged.
- Never resend the same answer for the same nugget.
- Answers are sent with `urllib.parse.quote(answer, safe="")`.

### 4.5 Defense
Cost of one defense = one action. Being 1000 ms slower costs one action every 12 s. So **always defend at once**, except in the last seconds.

- Victim defends its lowest attacker id first.
- Teammate helps only when the victim has ≥ 2 attackers and takes the highest id, so the two bots never spend two actions on the same attacker.
- Each bot remembers what it already defended, since `/api/users` lags up to 1 s.
- **Burst threshold:** burst costs 1 action + 3 pts; defending k attackers costs k actions. With p = average points per claim, burst when `k > 1 + 3/p`: **k ≥ 3 while claiming 2× or 3×, k ≥ 5 while on 1×**. Assumes "−3 nuggets" means −3 score points **[probe]**.

### 4.6 Attack
- One attack costs us one action (≤ 3 pts) and costs an undefended target 25% of their output for as long as it stands. Payback is 12 seconds. Against a team with instant auto-defense it is an even trade, never a loss.
- **Free attacks:** at the start of each round the bot has no solver and nothing to claim. Every slot in that dead time goes to attacks, at zero cost. This is the main attack window.
- **During claiming**, attack only targets that pass all of: rival team adjacent to us in the standings or in the top 3; currently below 8000 ms (`3000 + 1000 × len(attackedBy)`, read free from `/api/users`); not already in our `attacking` list; classified "non-defender" (past attacks on them stayed > 30 s) or never tested.
- Both of us attack both members of a priority team: 4 actions take 40% off that team.
- The watcher records each rival's score rate and how fast their `attackedBy` empties. That gives the defender/non-defender classification for free.
- If attacks are once per session **[probe]**, spend them all in the Round 1 dead time, strongest warm-up teams first.

## 5. Mock server (build before the bot is trusted)

A FastAPI clone of every endpoint and error message in the deck: throttle with the −1 penalty, attack cap, self/teammate defend, burst, three rounds with type rotation, random 100-nugget discover.

Plus what the real day will throw at us:
- injected 503s, token expiry, slow and dropped responses;
- attacks landing mid-wait;
- simulated rival bots draining the same nuggets (to tune staleness);
- a round switch on demand;
- type generators that the *other* teammate writes and keeps hidden, for drills.

Acceptance test: two bots run 30 minutes against the mock under chaos with zero crashes and zero self-inflicted 429s.

## 6. Solver toolkit (the offline replacement for Google)

Writing a solver on the day should be "regex + one library call". Pre-write and unit-test:

- **parse.py:** all ints/floats in a string, quoted strings, bracketed lists, key:value pairs, embedded JSON, text between markers.
- **jsfmt.py:** the server looks like Node + MongoDB (ObjectId ids, Express-style messages) **[probe]**, so answers were probably produced by JavaScript. `js_str()` mimics it: `true`/`false`, `3` not `3.0`, arrays as `1,2,3`, compact `JSON.stringify`. Also JS-style `round` (half up), `%` (sign of dividend), default lexicographic sort, `toFixed`.
- **text.py:** reverse, case variants, vowel/consonant/word counts, palindrome, anagram, Caesar/ROT13/Vigenère, base64, hex, binary, Morse, Roman numerals, run-length encoding, hashes.
- **algos.py:** safe arithmetic evaluator, RPN, primes, factorisation, gcd/lcm, Fibonacci, base conversion, modular arithmetic, permutations/combinations, date arithmetic, bracket matching, BFS/DFS/Dijkstra on text grids, edit distance, LCS, knapsack, sudoku, n-queens, matrix operations, next-term-in-sequence.

`solvers/_template.py` plus `tools/try.py` make the loop: copy template → write → run over the dumped samples → eyeball → save (the bot picks it up in canary).

If you still have the question types from the previous edition or from Round 1, add them as the first drill set.

## 7. Schedule (today is 13 Nov)

| Dates | Work | Done when |
|---|---|---|
| 13–14 Nov | Email organisers. Call login once from both laptops. Skeleton, config, client, logging. | Any JSON reply from the real server; both laptops run the same repo. |
| 15–17 Nov | Mock server. Steps 1–6: gate, pool, registry, recovery. | 30 min unattended on the mock under chaos. |
| 18–19 Nov | Watcher, defense, burst, attack, partition, status line. | Two bots + simulated rivals; correct decisions in the logs. |
| 20–21 Nov | Toolkit + tests, template, `try.py`. | Sample solver written in under 3 minutes. |
| 22–23 Nov | **Drills, Wi-Fi off, DevDocs/pydoc only.** Each of you writes 9 hidden types for the other. Three full simulated rounds per day. | First solver live < 5 min, 3× live < 20 min. |
| 24 Nov | Re-read the spec for changes. Code freeze. Both laptops: sleep and Windows Update disabled, chargers, USB stick with the repo, printed cheat sheet if allowed. | Full offline dress rehearsal passes on both laptops. |

## 8. Warm-up checklist (20–30 min; penalties are free here)

1. Start both bots; confirm the ready check: ten minutes of claims with nobody touching the keyboard.
2. **Calibrate the margin:** step down 25 ms every 20 clean actions until the first 429, then set margin = last safe value + 50 ms.
3. Record which responses restart the throttle: wrong answer, already claimed, 404, failed attack/defend, 429 itself.
4. Check answer formatting conventions on the practice types (case, number and list formats).
5. One attack → defend → re-attack on a rival, and one burst: learn whether re-attacking works and what the penalties do to `score`.
6. Note discover sizes per type and how fast "already claimed" appears.
7. Recon: which teams score fast (strong bots) and whose `attackedBy` clears quickly (auto-defenders). Save the list for the attack queue.
8. Force a re-login. Measure round-trip latency.
9. Watch what a stale pool returns at the warm-up → Round 1 reset; that is the round-change signal.

## 9. Round protocol (×3)

| Minute | Player A | Player B | Bots |
|---|---|---|---|
| 0 | Read dumped samples of all three types | Same | Unfiltered discover, dump samples, then spend dead time on attacks and defense |
| 1 | Takes the **3×** type | Takes the **easiest** type, usually 1× | — |
| ~3–5 | Still on 3× | Ships it on laptop B, then starts 2× | B claims 1× |
| When 3× passes canary | Copies the solver to B by USB | Installs it, hands back the others | Both on 3× |
| Rest of round | Reads `failures/`, fixes edge cases | Finishes 2× as a fallback for 3× depletion; watches standings and the attack queue | — |

Rules of thumb: test on dumped samples before saving; if 3× is not converging after ~15 minutes, swap or pair on it while the bots stay on the best available type; nobody restarts a running bot unless it is dead.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Spec changes before the start | Endpoints, messages and constants live in `config.toml`; re-read on the 24th and on the morning |
| Exact-match formatting | `jsfmt.py`, canary mode, `failures/` log |
| A laptop dies | Same repo on both and on USB; `--player` runs both accounts on one machine |
| Double-run on one account | Lock file per account |
| 429 storm from attacks | `/auth/me` pre-flight; margin auto-widens |
| Polling seen as abuse | 2 Hz on `/auth/me`, 1 Hz on the lists; drop to 1 Hz if told |
| Hard 3× type | Expected-value routing keeps both bots on the best solvable type |
