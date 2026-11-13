"""Timed rounds, paced rivals and the scoreboard (no spoilers in this file)."""

from __future__ import annotations

from mockserver.game import Game, User
from mockserver.server import scoreboard, seed


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def paced_game(clock: Clock) -> Game:
    game = Game(clock=clock, per_type=200)
    seed(game, rivals=2, paced=True)
    return game


def rival(game: Game, name: str) -> User:
    return next(u for u in game.users.values() if u.firstname == name)


def play(game: Game, clock: Clock, seconds: int) -> None:
    for _ in range(seconds):
        clock.now += 1
        for user in list(game.users.values()):
            if user.is_rival:
                game.rival_turn(user)


def test_rivals_need_time_to_write_each_solver() -> None:
    clock = Clock()
    game = paced_game(clock)
    fast, slow = rival(game, "Rival1x"), rival(game, "Rival2x")  # pace 0.6 and 1.0
    assert (game.rival_reach(fast), game.rival_reach(slow)) == (0, 0)
    play(game, clock, 60)
    assert fast.score == slow.score == 0  # nobody has a solver in the first minute
    play(game, clock, 30)  # 1.5 min: only the fast team has its x1 solver
    assert fast.score > 0 and slow.score == 0
    clock.now = 15 * 60
    assert (game.rival_reach(fast), game.rival_reach(slow)) == (3, 3)


def test_a_new_round_resets_the_rivals_progress() -> None:
    clock = Clock()
    game = paced_game(clock)
    clock.now = 20 * 60
    assert game.rival_reach(rival(game, "Rival1x")) == 3
    game.set_round(2)
    assert game.rival_reach(rival(game, "Rival1x")) == 0


def test_every_second_rival_team_defends_itself() -> None:
    clock = Clock()
    game = paced_game(clock)
    alice = rival(game, "Alice")
    passive, defender = rival(game, "Rival1x"), rival(game, "Rival2x")
    game.attack(alice, passive.id)
    game.attack(alice, defender.id)
    play(game, clock, 5)
    assert passive.attacked_by == [alice.id] and defender.attacked_by == []


def test_session_over_closes_the_game() -> None:
    clock = Clock()
    game = paced_game(clock)
    alice = rival(game, "Alice")
    nugget = next(iter(game.nuggets.values()))
    assert game.set_round(0) and not game.set_round(7)
    assert game.discover(alice)[1] == []
    assert game.claim(alice, nugget.id, nugget.answer)[0] == 404


def test_scoreboard_shows_standings_and_time_to_first_claim() -> None:
    clock = Clock()
    game = paced_game(clock)
    game.round_seconds = 20 * 60
    alice = rival(game, "Alice")
    rival(game, "Rival1x").score = 40
    clock.now = 125
    nugget = next(n for n in game.nuggets.values() if n.round == 1 and n.coefficient == 3)
    assert game.claim(alice, nugget.id, nugget.answer)[0] == 200
    text = scoreboard(game)
    assert "Round 1 of 3, 02:05 played, 17:55 left" in text
    assert text.index("Rival 1") < text.index("Delta Team") and "<- you" in text
    assert f"{nugget.type} x3 02:05" in text and "x1 --:--" in text
    assert "round 2" not in text  # future rounds stay hidden
    game.set_round(0)
    assert scoreboard(game).startswith("Session over") and "round 3" in scoreboard(game)

