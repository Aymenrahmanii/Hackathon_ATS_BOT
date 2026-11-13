"""The main loop: discover -> solve -> claim -> wait -> repeat.

Run one bot per account:  python -m dt.bot --player a
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import traceback
import zlib
from collections.abc import Callable
from pathlib import Path

from dt import config
from dt.client import Api, Reply
from dt.combat import Move, World
from dt.pool import Nugget, Pool
from dt.registry import Registry
from dt.throttle import Gate

IDLE_S = 1.0  # nothing to do: check for new solvers and attacks this often
RETRY_LATER = (401, 429, 503)  # the call did not go through: decide again next step
SCAN_EVERY_S = 30.0  # with no usable solver, look for a new round this often
DEPLETED_S = 60.0  # a type that returned nothing is skipped this long
SAMPLES_PER_TYPE = 300
EXAMPLES_SHOWN = 3


class Bot:
    def __init__(
        self,
        api: Api,
        gate: Gate,
        registry: Registry,
        pool: Pool,
        world: World,
        data_dir: Path,
        attack_mode: str = "always",
        out: Callable[[str], None] = print,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api = api
        self.gate = gate
        self.registry = registry
        self.pool = pool
        self.world = world
        self.data_dir = data_dir
        self.attack_mode = attack_mode  # "off", "idle" or "always"
        self.out = out
        self.clock = clock
        self.sleep = sleep
        self.depleted: dict[str, float] = {}
        self.next_scan = 0.0
        self.sampled: dict[str, set[str]] = {}
        gate.on_lead = lambda: world.refresh(gate.me)

    def run(self, steps: int | None = None) -> None:
        done = 0
        while steps is None or done < steps:
            try:
                self.step()
            except Exception:  # the bot must never stop on its own
                self.out("\a" + traceback.format_exc())
                self.sleep(1.0)
            done += 1

    def step(self) -> None:
        self.api.ensure_fresh()
        self.registry.refresh()
        if self.pool.stale() or self._upgrade_available():
            self.pool.clear()
        self.gate.wait()  # our view of the game is fresh from here on
        move = self._choose()
        if move:
            move()
        else:
            self.sleep(IDLE_S)

    def _choose(self) -> Callable[[], None] | None:
        """What to do with this slot, most valuable first."""
        best = self._best_type()
        fight = self.world.defence(self.gate.me, self._value(best) if best else 0.0)
        if fight:
            return lambda: self._fight(fight)
        claim = self._next_claim()
        if claim and self.attack_mode == "always":
            threat = self.world.target(priority_only=True)
            if threat:
                return lambda: self._fight(Move("attack", threat))
        if claim:
            return lambda: self._claim(*claim)
        if best or self.clock() >= self.next_scan:
            return self._discover
        if self.attack_mode != "off":  # dead time: this slot is free
            anyone = self.world.target(priority_only=False)
            if anyone:
                return lambda: self._fight(Move("attack", anyone))
        return None

    # --- choosing ----------------------------------------------------------

    def _value(self, nugget_type: str) -> float:
        return self.pool.types.get(nugget_type, 0) * self.registry.rate(nugget_type)

    def _best_type(self) -> str | None:
        """The known type worth the most right now, or None if we can solve none."""
        now = self.clock()
        usable = [t for t in self.pool.types if self._value(t) > 0 and self.depleted.get(t, 0) <= now]
        return max(usable, key=self._value, default=None)

    def _upgrade_available(self) -> bool:
        """A better type became solvable while the pool holds only cheaper ones."""
        best = self._best_type()
        if best is None or len(self.pool) == 0 or self.pool.has(best):
            return False
        return self._value(best) > self.pool.best_value(self.registry.rate)

    def _next_claim(self) -> tuple[Nugget, str] | None:
        while (nugget := self.pool.pick(self.registry.rate)) is not None:
            answer = self.registry.solve(nugget.type, nugget.content)
            if answer is not None:
                return nugget, answer
            self.pool.discard(nugget.id)  # solver could not handle it: costs no action
        return None

    # --- acting ------------------------------------------------------------

    def _discover(self) -> None:
        kind = self._best_type()
        reply = self.gate.send(lambda: self.api.discover(kind))
        if reply.status in RETRY_LATER:
            return
        self.next_scan = self.clock() + SCAN_EVERY_S
        if reply.status == 200 and isinstance(reply.data, list):
            kept = self.pool.fill(reply.data)
            self._save_samples(reply.data)
            if kind and kept == 0:  # nothing left for us: try the next type for a while
                self.depleted[kind] = self.clock() + DEPLETED_S
            self._say(f"discover {kind or 'all'} -> {len(reply.data)} nuggets, kept {kept}")
        elif kind and reply.status == 400:
            self._round_changed(f"type {kind} is unknown")
        else:
            self._say(f"discover {kind or 'all'} -> {reply.status} {reply.message}")

    def _claim(self, nugget: Nugget, answer: str) -> None:
        reply = self.gate.send(lambda: self.api.claim(nugget.id, answer))
        if reply.status in RETRY_LATER:
            self._say(f"claim {nugget.type} -> {reply.status}, will retry")
            return  # keep the nugget; a timeout (0) is dropped: it may have counted
        self.pool.discard(nugget.id)
        message = reply.message.lower()
        if reply.status == 200:
            self.registry.record(nugget.type, True)
            self.pool.note(False)
            # The /auth/me snapshot predates the claim; keep the display current.
            self.gate.me["score"] = self.gate.me.get("score", 0) + nugget.coefficient
        elif reply.status == 400 and "wrong" in message:
            self.registry.record(nugget.type, False)
            self.pool.note(False)
            self._save_failure(nugget, answer, reply)
        elif reply.status == 400 and "already claimed" in message:
            self.pool.note(True)
        elif reply.status == 404:
            self._round_changed(reply.message)
            return
        self._say(f"claim {nugget.type} x{nugget.coefficient} -> {reply.status} {reply.message}")

    def _fight(self, move: Move) -> None:
        if move.kind == "burst":
            reply = self.gate.send(self.api.burst)
        elif move.kind == "defend":
            reply = self.gate.send(lambda: self.api.defend(move.target, move.mate))
        else:
            reply = self.gate.send(lambda: self.api.attack(move.target))
            self.world.attacked(move.target, reply)
        who = f" for {self._name(move.mate)}" if move.mate else ""
        what = f"{move.kind} {self._name(move.target)}{who}".replace("  ", " ")
        self._say(f"{what} -> {reply.status} {reply.message}")

    def _name(self, user_id: str | None) -> str:
        user = self.world.users.get(user_id or "", {})
        return str(user.get("firstname") or user_id or "")

    def _round_changed(self, why: str) -> None:
        self.pool.reset()
        self.depleted.clear()
        self.next_scan = 0.0
        self._say(f"\aROUND CHANGE? ({why}) -> rescanning")

    # --- files and display ---------------------------------------------------

    def _save_samples(self, raw: list[dict]) -> None:
        for item in raw:
            kind = str(item.get("nuggetType", "unknown"))
            first_time = kind not in self.sampled
            seen = self.sampled.setdefault(kind, set())
            if item.get("_id") in seen or len(seen) >= SAMPLES_PER_TYPE:
                continue
            seen.add(item.get("_id"))
            _append(self.data_dir / "samples" / f"{kind}.jsonl", item)
            if first_time:
                self.out(f"\aNEW TYPE {kind} x{item.get('coefficient')} -> samples/{kind}.jsonl")
            if len(seen) <= EXAMPLES_SHOWN:
                self.out(f"   {kind}: {item.get('content')!r}")

    def _save_failure(self, nugget: Nugget, answer: str, reply: Reply) -> None:
        record = {"content": nugget.content, "answer": answer, "reply": reply.data}
        _append(self.data_dir / "failures" / f"{nugget.type}.jsonl", record)

    def _say(self, text: str) -> None:
        me = self.gate.me
        status = (
            f"score {me.get('score', '?')} thr {self.gate.throttle_ms} "
            f"atk {len(me.get('attackedBy', []))} pool {len(self.pool)}"
        )
        self.out(f"{time.strftime('%H:%M:%S')} {text} | {status}")


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def hold_lock(email: str) -> socket.socket:
    """Two bots on one account would 429 each other. A bound local port is the
    lock: the OS frees it even if the bot crashes."""
    port = 47000 + zlib.crc32(email.encode()) % 1000
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", port))
    except OSError:
        sys.exit(f"A bot for {email} is already running on this machine.")
    return lock


def build(cfg: config.Config, name: str) -> Bot:
    api = Api(cfg.base_url, cfg.email, cfg.password, cfg.data_dir / "logs" / f"{name}.jsonl")
    reply = api.login()
    if reply.status != 200:
        sys.exit(f"Login failed: {reply.status} {reply.message}")
    gate = Gate(api, cfg.margin_ms)
    registry, pool = Registry(cfg.solvers_dir), Pool(cfg.slot)
    return Bot(api, gate, registry, pool, World(api), cfg.data_dir, cfg.attack_mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Double Trouble bot")
    parser.add_argument("--player", required=True, help="key under [players] in the config")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--steps", type=int, default=None, help="stop after N steps (testing)")
    args = parser.parse_args()
    # Questions may hold characters a Windows console cannot encode.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    cfg = config.load(args.config, args.player)
    lock = hold_lock(cfg.email)
    try:
        build(cfg, args.player).run(args.steps)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        lock.close()


if __name__ == "__main__":
    main()
