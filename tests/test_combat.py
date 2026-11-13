"""Defense, burst and target selection, on a hand-built picture of the game."""

from __future__ import annotations

import pytest

from dt.client import Reply
from dt.combat import Move, World, ids, should_burst


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0

    def clock(self) -> float:
        return self.now


class FakeApi:
    """Serves /api/users and /api/teams from two editable tables."""

    def __init__(self) -> None:
        self.people: dict[str, dict] = {}
        self.teams_table: dict[str, list[str]] = {}

    def add(self, team: str, uid: str, score: int = 0) -> None:
        self.people[uid] = {"_id": uid, "firstname": uid, "score": score, "attackedBy": []}
        self.teams_table.setdefault(team, []).append(uid)

    def users(self) -> Reply:
        return Reply(200, [dict(p, attackedBy=list(p["attackedBy"])) for p in self.people.values()])

    def teams(self) -> Reply:
        body = [
            {"name": name, "members": [{"_id": uid} for uid in members]}
            for name, members in self.teams_table.items()
        ]
        return Reply(200, body)


@pytest.fixture
def setup() -> tuple[FakeApi, FakeTime, World]:
    api, time = FakeApi(), FakeTime()
    api.add("us", "me", 30)
    api.add("us", "mate", 30)
    api.add("alpha", "a1", 90)
    api.add("alpha", "a2", 10)
    api.add("beta", "b1", 0)
    return api, time, World(api, time.clock)


def me(api: FakeApi) -> dict:
    return api.people["me"]


@pytest.mark.parametrize(
    ("attackers", "claim_value", "expected"),
    [(2, 3, False), (3, 3, True), (2, 2, False), (3, 2, True), (4, 1, False), (5, 1, True),
     (5, 0, False)],
)
def test_burst_rule(attackers: int, claim_value: float, expected: bool) -> None:
    assert should_burst(attackers, score=50, claim_value=claim_value) is expected


def test_burst_needs_three_points() -> None:
    assert not should_burst(5, score=2, claim_value=3)


def test_ids_accepts_plain_ids_and_objects() -> None:
    assert ids(["x", {"_id": "y"}]) == ["x", "y"]
    assert ids(None) == []


def test_i_defend_my_lowest_attacker_or_burst(setup: tuple[FakeApi, FakeTime, World]) -> None:
    api, _, world = setup
    me(api)["attackedBy"] = ["b1", "a1"]
    world.refresh(me(api))
    assert world.defence(me(api), claim_value=3) == Move("defend", "a1")
    me(api)["attackedBy"] = ["b1", "a1", "a2"]
    assert world.defence(me(api), claim_value=3) == Move("burst")
    assert world.defence(me(api), claim_value=0) == Move("defend", "a1")  # dead time: no burst


def test_teammate_help_takes_the_highest_id(setup: tuple[FakeApi, FakeTime, World]) -> None:
    api, _, world = setup
    api.people["mate"]["attackedBy"] = ["a1"]
    world.refresh(me(api))
    assert world.defence(me(api), claim_value=3) is None  # one attacker: mate handles it
    api.people["mate"]["attackedBy"] = ["a1", "b1"]
    world.refresh(me(api))
    assert world.defence(me(api), claim_value=3) == Move("defend", "b1", "mate")
    api.people["mate"]["attackedBy"] = ["a1", "a2", "b1"]
    world.refresh(me(api))
    assert world.defence(me(api), claim_value=3) is None  # mate will burst


def test_teammate_help_when_their_bot_is_stuck(setup: tuple[FakeApi, FakeTime, World]) -> None:
    api, time, world = setup
    api.people["mate"]["attackedBy"] = ["a1"]
    world.refresh(me(api))
    time.now += 9
    world.refresh(me(api))
    assert world.defence(me(api), claim_value=3) is None
    time.now += 2  # past two of their slots plus 2 s
    world.refresh(me(api))
    assert world.defence(me(api), claim_value=3) == Move("defend", "a1", "mate")


def test_targets_skip_teammates_and_rank_by_threat(setup: tuple[FakeApi, FakeTime, World]) -> None:
    api, _, world = setup
    world.refresh(me(api))
    assert world.target(priority_only=False) == "a1"  # richest team, richest member
    api.people["a1"]["attackedBy"] = ["me"]
    world.refresh(me(api))
    assert world.target(priority_only=False) == "a2"
    api.people["a2"]["attackedBy"] = ["v", "w", "x", "y", "z"]  # at the 8000 ms cap
    world.refresh(me(api))
    assert world.target(priority_only=False) == "b1"
    assert world.target(priority_only=True) is None  # beta has not scored: not a threat


def test_no_targets_until_teams_are_known() -> None:
    api, time = FakeApi(), FakeTime()
    api.add("us", "me")
    api.add("alpha", "a1", 5)
    world = World(api, time.clock)
    api.teams = lambda: Reply(503, {})  # type: ignore[method-assign]
    world.refresh(api.people["me"])
    assert world.target(priority_only=False) is None


def test_fast_defenders_are_not_attacked_again(setup: tuple[FakeApi, FakeTime, World]) -> None:
    api, time, world = setup
    world.refresh(me(api))
    world.attacked("a1", Reply(200, {"message": "Attack successful!"}))
    api.people["a1"]["attackedBy"] = ["me"]
    world.refresh(me(api))
    time.now += 6
    api.people["a1"]["attackedBy"] = []  # shaken off within 30 s
    world.refresh(me(api))
    assert "a1" in world.defenders
    assert world.target(priority_only=False) == "a2"


def test_slow_recovery_makes_the_target_eligible_again(
    setup: tuple[FakeApi, FakeTime, World],
) -> None:
    api, time, world = setup
    world.refresh(me(api))
    world.attacked("a1", Reply(200, {}))
    api.people["a1"]["attackedBy"] = ["me"]
    world.refresh(me(api))
    time.now += 45
    api.people["a1"]["attackedBy"] = []
    world.refresh(me(api))
    assert "a1" not in world.defenders
    assert world.target(priority_only=False) == "a1"


def test_refused_attacks_are_remembered(setup: tuple[FakeApi, FakeTime, World]) -> None:
    api, time, world = setup
    world.refresh(me(api))
    world.attacked("a1", Reply(400, {"message": "You have already attacked this user. ⚔️⚔️"}))
    world.attacked("a2", Reply(400, {"message": "This victim is currently reaching their throttle limit."}))
    assert world.target(priority_only=False) == "b1"
    time.now += 31
    assert world.target(priority_only=False) == "a2"  # the limit can lift; "already" cannot
