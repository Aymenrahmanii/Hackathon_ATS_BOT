"""Gate, Pool and Registry in isolation, with a fake clock."""

from __future__ import annotations

from pathlib import Path

from pytest import approx

from dt.client import Reply
from dt.pool import Pool
from dt.registry import TRUST_AFTER, Registry
from dt.throttle import Gate


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeApi:
    def __init__(self) -> None:
        self.throttle_ms = 3000

    def me(self) -> Reply:
        return Reply(200, {"totalThrottleMs": self.throttle_ms, "score": 7})


class Script:
    """Returns the queued replies in order and records when each call was sent."""

    def __init__(self, time: FakeTime, *replies: Reply) -> None:
        self.time = time
        self.replies = list(replies)
        self.sent: list[float] = []

    def __call__(self) -> Reply:
        self.sent.append(self.time.now)
        return self.replies.pop(0)


def make_gate(time: FakeTime, api: FakeApi) -> Gate:
    return Gate(api, margin_ms=250, clock=time.clock, sleep=time.sleep)


def call(gate: Gate, action: Script) -> Reply:
    gate.wait()
    return gate.send(action)


OK = Reply(200, {"success": True})

# --- Gate ----------------------------------------------------------------------


def test_gate_waits_throttle_plus_margin() -> None:
    time, api = FakeTime(), FakeApi()
    gate = make_gate(time, api)
    action = Script(time, OK, OK)
    call(gate, action)
    call(gate, action)
    assert action.sent == approx([3.25, 6.5])
    assert gate.me["score"] == 7


def test_gate_sees_an_attack_that_landed_during_the_wait() -> None:
    time, api = FakeTime(), FakeApi()
    gate = make_gate(time, api)
    api.throttle_ms = 5000  # two attackers arrived after the last action
    action = Script(time, OK)
    call(gate, action)
    assert action.sent == approx([5.25])


def test_gate_refreshes_the_world_before_the_slot_opens() -> None:
    time, api = FakeTime(), FakeApi()
    gate = make_gate(time, api)
    seen: list[float] = []
    gate.on_lead = lambda: seen.append(time.now)
    gate.wait()
    assert seen == approx([3.05])  # lead_s before the 3.25 s slot


def test_gate_retries_503_without_a_full_wait() -> None:
    time, api = FakeTime(), FakeApi()
    gate = make_gate(time, api)
    action = Script(time, Reply(503, {}), OK)
    assert call(gate, action).status == 503
    assert call(gate, action).status == 200
    assert action.sent == approx([3.25, 3.4])


def test_gate_obeys_retry_after_and_widens_margin_on_repeat() -> None:
    time, api = FakeTime(), FakeApi()
    gate = make_gate(time, api)
    action = Script(time, Reply(429, {}, retry_after=2.0), Reply(429, {}, retry_after=5.0), OK)
    statuses = [call(gate, action).status for _ in range(3)]
    assert statuses == [429, 429, 200]
    assert action.sent[1] == approx(6.5)  # the full throttle beats a 2 s Retry-After
    assert action.sent[2] == approx(6.5 + 5.0 + 0.25)  # a longer Retry-After is obeyed
    assert gate.margin_ms == 300


def test_gate_treats_a_timeout_as_a_used_slot() -> None:
    time, api = FakeTime(), FakeApi()
    gate = make_gate(time, api)
    action = Script(time, Reply(0, {"message": "Timeout"}), OK)
    assert call(gate, action).status == 0
    call(gate, action)
    assert action.sent == approx([3.25, 6.5])


# --- Pool ----------------------------------------------------------------------


def nugget(ident: str, kind: str = "a", coefficient: int = 1) -> dict:
    return {"_id": ident, "content": "q", "nuggetType": kind, "coefficient": coefficient,
            "claimed": False}


def test_pool_splits_nuggets_between_teammates() -> None:
    raw = [nugget("a0"), nugget("a1"), nugget("a2"), nugget("af")]
    even, odd = Pool(slot=0), Pool(slot=1)
    assert even.fill(raw) == 2 and odd.fill(raw) == 2
    assert set(even.nuggets) == {"a0", "a2"} and set(odd.nuggets) == {"a1", "af"}


def test_pool_takes_everything_when_none_are_ours() -> None:
    pool = Pool(slot=0)
    assert pool.fill([nugget("a1"), nugget("a3")]) == 2


def test_pool_picks_best_expected_value() -> None:
    pool = Pool()
    pool.fill([nugget("01", "easy", 1), nugget("02", "mid", 2), nugget("03", "hard", 3)])
    rates = {"easy": 1.0, "mid": 1.0, "hard": 0.5}
    assert pool.pick(lambda kind: rates[kind]).type == "mid"
    assert pool.pick(lambda kind: 0.0) is None
    assert pool.types == {"easy": 1, "mid": 2, "hard": 3}


def test_pool_goes_stale_and_never_retries() -> None:
    pool = Pool()
    pool.fill([nugget("01"), nugget("02")])
    pool.discard("01")
    pool.note(True)
    assert not pool.stale()
    pool.note(True)
    assert pool.stale()
    assert pool.fill([nugget("01"), nugget("02")]) == 1 and not pool.stale()


# --- Registry ------------------------------------------------------------------


def write(folder: Path, name: str, body: str) -> None:
    (folder / f"{name}.py").write_text(body, encoding="utf-8")


def test_registry_loads_and_hot_reloads(tmp_path: Path) -> None:
    notes: list[str] = []
    registry = Registry(tmp_path, notes.append)
    write(tmp_path, "echo", "def solve(content):\n    return content\n")
    write(tmp_path, "_ignored", "def solve(content):\n    return 'x'\n")
    registry.refresh()
    assert registry.solve("echo", "hi") == "hi" and "_ignored" not in registry.solvers
    write(tmp_path, "echo", "def solve(content):\n    return content.upper()\n")
    registry.refresh()
    assert registry.solve("echo", "hi") == "HI"
    (tmp_path / "echo.py").unlink()
    registry.refresh()
    assert registry.rate("echo") == 0.0


def test_registry_survives_broken_files_and_solver_bugs(tmp_path: Path) -> None:
    notes: list[str] = []
    registry = Registry(tmp_path, notes.append)
    write(tmp_path, "broken", "def solve(content:\n")
    write(tmp_path, "crashy", "def solve(content):\n    return 1 / 0\n")
    registry.refresh()
    assert registry.rate("broken") == 0.0
    assert registry.solve("crashy", "q") is None
    assert registry.rate("crashy") == 0.0  # paused: it failed on probation
    assert any("NOT LOADED" in note for note in notes)


def test_registry_probation_then_trust(tmp_path: Path) -> None:
    registry = Registry(tmp_path, lambda _: None)
    write(tmp_path, "kind", "def solve(content):\n    return content\n")
    registry.refresh()
    registry.record("kind", False)
    assert registry.rate("kind") == 0.0  # one miss on probation pauses it
    write(tmp_path, "kind", "def solve(content):\n    return content  # fixed\n")
    registry.refresh()
    for _ in range(TRUST_AFTER):
        registry.record("kind", True)
    registry.record("kind", False)
    assert 0.0 < registry.rate("kind") < 1.0  # trusted: a single miss only lowers the rate
    for _ in range(4):
        registry.record("kind", False)
    assert registry.rate("kind") == 0.0  # sustained failure pauses it again
