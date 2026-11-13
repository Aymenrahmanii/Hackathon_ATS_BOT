"""The mock must follow spec v1.6: these tests pin the rules the bot relies on."""

from __future__ import annotations

import pytest

from mockserver.game import Game, User


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def game(clock: Clock) -> Game:
    game = Game(clock=clock, per_type=150)
    game.add_user("alice@mock.test", "alice", "Alice", "Delta")
    game.add_user("bob@mock.test", "bob", "Bob", "Delta")
    for index in range(6):
        game.add_user(f"eve{index}@mock.test", "eve", f"Eve{index}", f"Rival {index}")
    return game


def by_name(game: Game, name: str) -> User:
    return next(u for u in game.users.values() if u.firstname == name)


def test_login_errors_and_token(game: Game, clock: Clock) -> None:
    assert game.login("nobody@mock.test", "x")[0] == 404
    assert game.login("alice@mock.test", "wrong")[0] == 400
    status, body, _ = game.login("alice@mock.test", "alice")
    assert status == 200
    assert game.user_for(body["accessToken"]).firstname == "Alice"
    clock.now += 3601
    assert game.user_for(body["accessToken"]) is None


def test_calling_early_costs_one_nugget(game: Game, clock: Clock) -> None:
    alice = by_name(game, "Alice")
    alice.score = 5
    assert game.gate(alice) is None
    clock.now += 2.9
    status, _, headers = game.gate(alice)
    assert (status, headers["Retry-After"], alice.score) == (429, "1", 4)
    clock.now += 0.1
    assert game.gate(alice) is None


def test_attacks_stack_to_the_cap(game: Game) -> None:
    alice = by_name(game, "Alice")
    for index in range(5):
        assert game.attack(by_name(game, f"Eve{index}"), alice.id)[0] == 200
        assert game.throttle_ms(alice) == 3000 + 1000 * (index + 1)
    status, body, _ = game.attack(by_name(game, "Eve5"), alice.id)
    assert status == 400 and "throttle limit" in body["message"]


def test_attack_rejections(game: Game) -> None:
    alice, bob, eve = by_name(game, "Alice"), by_name(game, "Bob"), by_name(game, "Eve0")
    assert "yourself" in game.attack(alice, alice.id)[1]["message"]
    assert "Teammate" in game.attack(alice, bob.id)[1]["message"]
    assert game.attack(alice, "missing")[0] == 404
    assert game.attack(alice, eve.id)[0] == 200
    assert "already attacked" in game.attack(alice, eve.id)[1]["message"]
    assert eve.id in alice.attacking


def test_self_defend(game: Game) -> None:
    alice, eve = by_name(game, "Alice"), by_name(game, "Eve0")
    assert "not been attacked" in game.defend(alice, eve.id)[1]["message"]
    game.attack(eve, alice.id)
    assert game.defend(alice, eve.id)[0] == 200
    assert game.throttle_ms(alice) == 3000 and eve.attacking == []


def test_teammate_defend(game: Game) -> None:
    alice, bob, eve = by_name(game, "Alice"), by_name(game, "Bob"), by_name(game, "Eve0")
    assert "is not attacking your teammate" in game.defend(bob, eve.id, alice.id)[1]["message"]
    game.attack(eve, alice.id)
    assert game.defend(eve, eve.id, alice.id)[0] == 400  # cannot defend from yourself
    assert game.defend(by_name(game, "Eve1"), eve.id, alice.id)[0] == 404  # not a teammate
    status, body, _ = game.defend(bob, eve.id, alice.id)
    assert status == 200 and "protected your teammate Alice" in body["message"]
    assert alice.attacked_by == []


def test_burst_costs_three_and_clears_attacks(game: Game) -> None:
    alice = by_name(game, "Alice")
    assert game.burst(alice)[0] == 400
    alice.score = 10
    for index in range(3):
        game.attack(by_name(game, f"Eve{index}"), alice.id)
    assert game.burst(alice)[0] == 200
    assert (alice.score, game.throttle_ms(alice)) == (7, 3000)
    assert by_name(game, "Eve0").attacking == []


def test_reattack_after_defence_depends_on_the_assumption(clock: Clock) -> None:
    for once_ever, expected in ((False, 200), (True, 400)):
        game = Game(clock=clock, per_type=1, attack_once_ever=once_ever)
        alice = game.add_user("a@mock.test", "a", "Alice", "Delta")
        eve = game.add_user("e@mock.test", "e", "Eve", "Rival")
        game.attack(eve, alice.id)
        game.defend(alice, eve.id)
        assert game.attack(eve, alice.id)[0] == expected


def test_discover_returns_current_round_only(game: Game) -> None:
    alice = by_name(game, "Alice")
    status, body, _ = game.discover(alice)
    assert status == 200 and len(body) == 100
    assert {n["nuggetType"] for n in body} <= {"reverseWord", "addNumbers", "countVowels"}
    filtered = game.discover(alice, "countVowels")[1]
    assert {(n["nuggetType"], n["coefficient"]) for n in filtered} == {("countVowels", 3)}
    assert game.discover(alice, "upperCase")[0] == 400  # belongs to round 2


def test_claim_outcomes(game: Game) -> None:
    alice, bob = by_name(game, "Alice"), by_name(game, "Bob")
    nugget = next(n for n in game.nuggets.values() if n.type == "addNumbers")
    assert game.claim(alice, nugget.id, "nope")[1]["message"] == "Wrong answer"
    assert game.claim(alice, nugget.id, nugget.answer)[0] == 200
    assert alice.score == 2
    assert game.claim(bob, nugget.id, nugget.answer)[1]["message"] == "Nugget already claimed"
    assert game.claim(alice, "missing", "x")[0] == 404


def test_old_round_nuggets_cannot_be_claimed(game: Game) -> None:
    alice = by_name(game, "Alice")
    nugget = next(n for n in game.nuggets.values() if n.round == 1)
    game.set_round(2)
    assert game.claim(alice, nugget.id, nugget.answer)[0] == 404


def test_teams_total_score(game: Game) -> None:
    by_name(game, "Alice").score, by_name(game, "Bob").score = 4, 6
    delta = next(t for t in game.list_teams()[1] if t["name"] == "Delta")
    assert delta["totalScore"] == 10 and len(delta["members"]) == 2
