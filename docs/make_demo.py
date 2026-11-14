"""Record a real bot run against the mock and render it as an animated SVG.

    uv run python -m docs.make_demo            # about 90 seconds; writes demo.log and demo.svg
    uv run python -m docs.make_demo --render   # redraw demo.svg from demo.log only

The run uses the real 3000 ms throttle and the practice question types. During the
run the script plays the other side: it saves a new solver, has rivals attack, and
switches the round. Only the example-question lines are trimmed from the log.
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
import time
from html import escape
from pathlib import Path

import uvicorn

from dt.bot import Bot
from dt.client import Api
from dt.combat import World
from dt.pool import Pool
from dt.registry import Registry
from dt.throttle import Gate
from mockserver.game import Game
from mockserver.server import create_app, run_rivals, seed

OUT = Path(__file__).with_name("demo.svg")
LOG = Path(__file__).with_name("demo.log")
REVERSE = "import re\n\ndef solve(content):\n    return re.search(r'\"(.*)\"', content).group(1)[::-1]\n"
VOWELS = "from dt.toolkit import *\n\ndef solve(content):\n    return js_str(count_vowels(quoted(content)[0]))\n"

# --- recording ------------------------------------------------------------------------


def record(steps: int = 30) -> list[str]:
    game = Game(seed=11, per_type=400)
    seed(game, rivals=2)
    app = create_app(game)
    lock = app.state.lock
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    threading.Thread(target=run_rivals, args=(game, lock), daemon=True).start()
    while not server.started:
        time.sleep(0.01)

    lines: list[str] = []
    root = Path(tempfile.mkdtemp())
    solvers = root / "solvers"
    solvers.mkdir()
    (solvers / "reverseWord.py").write_text(REVERSE, encoding="utf-8")
    api = Api(f"http://127.0.0.1:{port}", "alice@mock.test", "alice")
    api.login()
    gate = Gate(api, margin_ms=150)
    out = lambda text: lines.append(text.replace("\a", ""))  # noqa: E731
    bot = Bot(api, gate, Registry(solvers, out), Pool(slot=0), World(api), root / "data", "always", out)
    alice = next(u for u in game.users.values() if u.firstname == "Alice")
    rivals = [u for u in game.users.values() if u.is_rival]

    def attack(*attackers: int) -> None:
        with lock:
            for index in attackers:
                game.attack(rivals[index], alice.id)

    for step in range(steps):
        if step == 9:
            out("$ # teammate saves solvers/countVowels.py while the bot runs")
            (solvers / "countVowels.py").write_text(VOWELS, encoding="utf-8")
        if step == 14:
            attack(0)
        if step == 18:
            attack(1, 2, 3)
        if step == 24:
            out("$ # organisers start round 2")
            with lock:
                game.set_round(2)
        bot.step()
        print(lines[-1] if lines else "")
    server.should_exit = True
    return trim(lines)


def trim(lines: list[str]) -> list[str]:
    """Keep one example question per new type; drop the rest of the samples."""
    kept, examples = [], 0
    for line in lines:
        if line.startswith("NEW TYPE"):
            examples = 0
        if line.startswith("   "):
            examples += 1
            if examples > 1:
                continue
        kept.append(line)
    return kept


# --- rendering ------------------------------------------------------------------------

WIDTH, ROWS, LINE_H, PAD, TOP = 1000, 20, 19, 18, 44
PER_LINE_S, HOLD_S = 0.55, 4.0
COLORS = {
    "prompt": "#8b949e", "solver": "#79c0ff", "new": "#d2a8ff", "example": "#8b949e",
    "claim_ok": "#7ee787", "claim_bad": "#e3b341", "attack": "#ff7b72", "defend": "#79c0ff",
    "burst": "#ffa657", "round": "#d2a8ff", "discover": "#c9d1d9", "status": "#6e7681",
}


def kind(line: str) -> str:
    text = line.split(" ", 1)[1] if line[:2].isdigit() else line
    if line.startswith("$"):
        return "prompt"
    if line.startswith("solver"):
        return "solver"
    if line.startswith("NEW TYPE"):
        return "new"
    if line.startswith("   "):
        return "example"
    for word, name in (("ROUND CHANGE", "round"), ("burst", "burst"), ("attack", "attack"),
                       ("defend", "defend"), ("discover", "discover")):
        if text.startswith(word):
            return name
    return "claim_ok" if "-> 200" in text else "claim_bad"


def render(lines: list[str]) -> str:
    total = len(lines) * PER_LINE_S + HOLD_S
    height = TOP + ROWS * LINE_H + PAD
    pct = lambda seconds: f"{100 * seconds / total:.3f}%"  # noqa: E731
    styles, rows = [], []
    for i, line in enumerate(lines):
        start = i * PER_LINE_S
        styles.append(
            f"@keyframes l{i}{{0%,{pct(start)}{{opacity:0}}{pct(start + 0.12)},97%{{opacity:1}}100%{{opacity:0}}}}"
            f".l{i}{{animation:l{i} {total:.2f}s linear infinite}}"
        )
        main, _, status = line.partition(" | ")
        color = COLORS[kind(line)]
        body = f'<tspan fill="{color}">{escape(main)}</tspan>'
        if status:
            body += f'<tspan fill="{COLORS["status"]}">  {escape(status)}</tspan>'
        y = TOP + (i + 1) * LINE_H - 5
        rows.append(f'<text class="l{i}" x="{PAD}" y="{y}" xml:space="preserve">{body}</text>')
    # scroll up one row each time a line arrives past the bottom
    frames = ["0%{transform:translateY(0)}"]
    for i in range(ROWS, len(lines)):
        start = i * PER_LINE_S
        before = -(i - ROWS) * LINE_H
        frames.append(f"{pct(start)}{{transform:translateY({before}px)}}")
        frames.append(f"{pct(start + 0.12)}{{transform:translateY({before - LINE_H}px)}}")
    frames.append(f"99.9%{{transform:translateY({-(max(0, len(lines) - ROWS)) * LINE_H}px)}}")
    frames.append("100%{transform:translateY(0)}")
    styles.append(f"@keyframes scroll{{{''.join(frames)}}}.scroll{{animation:scroll {total:.2f}s linear infinite}}")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Recording of the bot playing against the mock server">
<style>
text{{font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}}
{''.join(styles)}
@media (prefers-reduced-motion: reduce){{[class^=l]{{animation:none;opacity:1}}.scroll{{animation:none}}}}
</style>
<rect width="{WIDTH}" height="{height}" rx="10" fill="#0d1117"/>
<rect width="{WIDTH}" height="30" rx="10" fill="#161b22"/><rect y="20" width="{WIDTH}" height="10" fill="#161b22"/>
<circle cx="20" cy="15" r="6" fill="#ff5f57"/><circle cx="40" cy="15" r="6" fill="#febc2e"/><circle cx="60" cy="15" r="6" fill="#28c840"/>
<text x="{WIDTH // 2}" y="19" text-anchor="middle" fill="#8b949e">python -m dt.bot --player a   (real run against the mock, 3000 ms throttle)</text>
<clipPath id="screen"><rect x="0" y="{TOP + 1}" width="{WIDTH}" height="{ROWS * LINE_H + 2}"/></clipPath>
<g clip-path="url(#screen)"><g class="scroll">
{chr(10).join(rows)}
</g></g>
</svg>
"""


def main() -> None:
    if "--render" in sys.argv:
        lines = LOG.read_text(encoding="utf-8").splitlines()
    else:
        lines = record()
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT.write_text(render(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
