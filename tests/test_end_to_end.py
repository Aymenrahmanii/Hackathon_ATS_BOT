"""The real bot against the real mock over HTTP, with a short throttle."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import requests
import uvicorn

from dt.bot import Bot
from dt.client import Api
from dt.combat import World
from dt.pool import Pool
from dt.registry import Registry
from dt.throttle import Gate
from mockserver.game import Game, User
from mockserver.server import create_app, seed

REVERSE = 'import re\ndef solve(content):\n    return re.search(r\'"(.*)"\', content).group(1)[::-1]\n'
VOWELS = (
    "import re\ndef solve(content):\n"
    "    phrase = re.search(r'\"(.*)\"', content).group(1)\n"
    "    return str(sum(c in 'aeiou' for c in phrase))\n"
)


@dataclass
class Rig:
    game: Game
    lock: threading.Lock
    url: str
    root: Path
    said: list[str] = field(default_factory=list)

    @property
    def solvers(self) -> Path:
        return self.root / "solvers"

    def bot(self, name: str, slot: int, attack_mode: str = "off") -> Bot:
        api = Api(self.url, f"{name}@mock.test", name, self.root / "data" / "logs" / f"{name}.jsonl")
        assert api.login().status == 200
        gate = Gate(api, margin_ms=50, lead_s=0.03)
        registry = Registry(self.solvers, self.said.append)
        data = self.root / "data"
        return Bot(api, gate, registry, Pool(slot), World(api), data, attack_mode, self.said.append)

    def user(self, firstname: str) -> User:
        return next(u for u in self.game.users.values() if u.firstname == firstname)

    def calls(self, name: str) -> list[tuple[str, int]]:
        """(path, status) of every throttled call the named bot made."""
        log = self.root / "data" / "logs" / f"{name}.jsonl"
        rows = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
        free = ("/api/auth/", "/api/users ", "/api/teams")
        return [(r["call"], r["status"]) for r in rows if not any(f in r["call"] + " " for f in free)]

    def attack(self, attacker: str, victim: str) -> None:
        with self.lock:
            assert self.game.attack(self.user(attacker), self.user(victim).id)[0] == 200


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    game = Game(base_ms=150, step_ms=50, cap_ms=400, per_type=300)
    seed(game, rivals=2)
    app = create_app(game)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.01)
    (tmp_path / "solvers").mkdir()
    (tmp_path / "solvers" / "reverseWord.py").write_text(REVERSE, encoding="utf-8")
    yield Rig(game, app.state.lock, f"http://127.0.0.1:{port}", tmp_path)
    server.should_exit = True


def statuses(rig: Rig, name: str) -> list[int]:
    return [status for _, status in rig.calls(name)]


def test_full_loop_hot_reload_and_round_change(rig: Rig) -> None:
    alice = rig.bot("alice", slot=0)
    alice.run(steps=10)
    after_x1 = rig.user("Alice").score
    assert after_x1 >= 6  # 1 discover, then x1 claims with the only solver we have

    (rig.solvers / "countVowels.py").write_text(VOWELS, encoding="utf-8")
    alice.run(steps=8)
    assert rig.user("Alice").score >= after_x1 + 3 * 6  # on the x3 type, no restart

    assert requests.post(f"{rig.url}/mock/round/2", timeout=5).status_code == 200
    alice.run(steps=4)
    assert set(alice.pool.types) == {"upperCase", "maxNumber", "isPalindrome"}
    assert any("ROUND CHANGE" in line for line in rig.said)
    assert (alice.data_dir / "samples" / "isPalindrome.jsonl").exists()

    assert 429 not in statuses(rig, "alice")  # never called early
    assert not any("Traceback" in line for line in rig.said)


def test_survives_503s_and_expiring_tokens(rig: Rig) -> None:
    alice = rig.bot("alice", slot=0)
    rig.game.p503 = 0.25
    rig.game.token_ttl_s = 0.4
    alice.api.login()  # this token dies after 0.4 s
    alice.run(steps=25)
    log = (rig.root / "data" / "logs" / "alice.jsonl").read_text("utf-8")
    seen = {json.loads(line)["status"] for line in log.splitlines()}
    assert {503, 401} <= seen  # both failures really happened
    assert 429 not in seen
    assert rig.user("Alice").score >= 8
    assert not any("Traceback" in line for line in rig.said)


def test_wrong_solver_is_paused_and_logged(rig: Rig) -> None:
    (rig.solvers / "reverseWord.py").write_text(
        "def solve(content):\n    return 'nope'\n", encoding="utf-8"
    )
    alice = rig.bot("alice", slot=0)
    alice.run(steps=4)
    assert rig.user("Alice").score == 0
    assert statuses(rig, "alice").count(400) == 1  # one wrong claim, then it stopped trying
    assert any("PAUSED" in line for line in rig.said)
    failure = json.loads((alice.data_dir / "failures" / "reverseWord.jsonl").read_text("utf-8"))
    assert failure["answer"] == "nope"


def test_self_and_teammate_defense_never_collide(rig: Rig) -> None:
    alice, bob = rig.bot("alice", slot=0), rig.bot("bob", slot=1)
    alice.step()
    bob.step()
    rig.attack("Rival1x", "Alice")
    rig.attack("Rival2x", "Alice")
    low, high = sorted([rig.user("Rival1x").id, rig.user("Rival2x").id])

    bob.step()  # sees two attackers on Alice: takes the highest id
    assert rig.user("Alice").attacked_by == [low]
    alice.step()  # Alice takes her lowest id
    assert rig.user("Alice").attacked_by == []

    assert (f"GET /api/users/{high}/defend?teammateId={rig.user('Alice').id}", 200) in rig.calls("bob")
    assert (f"GET /api/users/{low}/defend", 200) in rig.calls("alice")
    assert 400 not in statuses(rig, "alice") + statuses(rig, "bob")  # no wasted defends


def test_burst_only_when_it_is_cheaper_than_defending(rig: Rig) -> None:
    (rig.solvers / "countVowels.py").write_text(VOWELS, encoding="utf-8")
    alice = rig.bot("alice", slot=0)
    alice.run(steps=2)  # discover, one x3 claim: claims are now worth 3 points
    with rig.lock:
        rig.user("Alice").score = 20
    for rival in ("Rival1x", "Rival1y", "Rival2x"):
        rig.attack(rival, "Alice")
    alice.step()
    assert rig.user("Alice").attacked_by == [] and rig.user("Alice").score == 17

    rig.attack("Rival1x", "Alice")
    rig.attack("Rival2x", "Alice")
    alice.step()  # two attackers: defending is cheaper than another burst
    assert len(rig.user("Alice").attacked_by) == 1
    assert [path for path, _ in rig.calls("alice")].count("GET /api/users/burst") == 1


def test_dead_time_goes_to_attacks_and_defenders_are_left_alone(rig: Rig) -> None:
    (rig.solvers / "reverseWord.py").unlink()  # no solver: every slot is free
    alice = rig.bot("alice", slot=0, attack_mode="idle")
    alice.run(steps=5)  # 1 scan + 4 attacks
    alice_id = rig.user("Alice").id
    rivals = [u for u in rig.game.users.values() if u.is_rival]
    assert all(u.attacked_by == [alice_id] for u in rivals)
    assert rig.user("Bob").attacked_by == []
    assert set(statuses(rig, "alice")) == {200}  # no refused attack

    with rig.lock:  # one rival shakes the attack off quickly
        assert rig.game.defend(rig.user("Rival1x"), alice_id)[0] == 200
    alice.run(steps=2)
    assert rig.user("Rival1x").id in alice.world.defenders
    assert rig.user("Rival1x").attacked_by == []  # not attacked again


def test_scoring_threats_are_attacked_while_claiming(rig: Rig) -> None:
    with rig.lock:
        rig.user("Rival1x").score = 50  # Rival 1 leads; Rival 2 has nothing
    alice = rig.bot("alice", slot=0, attack_mode="always")
    alice.run(steps=7)  # scan, 2 attacks on Rival 1, then claims
    alice_id = rig.user("Alice").id
    assert rig.user("Rival1x").attacked_by == [alice_id]
    assert rig.user("Rival1y").attacked_by == [alice_id]
    assert rig.user("Rival2x").attacked_by == [] and rig.user("Rival2y").attacked_by == []
    assert rig.user("Alice").score >= 3
