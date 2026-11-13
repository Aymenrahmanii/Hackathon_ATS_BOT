"""HTTP face of the mock game.

    python -m mockserver.server --rivals 3                                 practice types
    python -m mockserver.server --drill 1 --round-minutes 20 --rivals 3    timed drill

Standings and your time-to-first-claim per type: http://127.0.0.1:8000/mock/scoreboard

Mock-only controls (not part of the real API):
    POST /mock/round/2                      switch round
    POST /mock/config?p503=0.05             inject 503s on throttled calls
    POST /mock/config?token_ttl_s=20        make new tokens expire fast
    POST /mock/config?rival_attack_p=0.02   let simulated rivals attack players
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Callable

import uvicorn
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from mockserver.drills import PACKS
from mockserver.game import Game, Result, User

UNAUTHORIZED: Result = (401, {"message": "Unauthorized"}, {})
RIVAL_TICK_S = 0.05
RIVAL_PACES = (0.6, 1.0, 1.5, 2.2)  # fast team first; see game.RIVAL_UNLOCK_MIN


class Credentials(BaseModel):
    email: str
    password: str


def respond(result: Result) -> JSONResponse:
    status, body, headers = result
    return JSONResponse(body, status_code=status, headers=headers)


def create_app(game: Game) -> FastAPI:
    app = FastAPI(title="Double Trouble mock")
    lock = threading.Lock()
    app.state.lock = lock

    def signed_in(authorization: str | None) -> User | None:
        token = (authorization or "").removeprefix("Bearer ").strip()
        return game.user_for(token)

    def free(authorization: str | None, read: Callable[[User], Result]) -> JSONResponse:
        with lock:
            user = signed_in(authorization)
            return respond(read(user) if user else UNAUTHORIZED)

    def throttled(authorization: str | None, action: Callable[[User], Result]) -> JSONResponse:
        with lock:
            user = signed_in(authorization)
            if user is None:
                return respond(UNAUTHORIZED)
            return respond(game.gate(user) or action(user))

    @app.post("/api/auth/login")
    def login(credentials: Credentials) -> JSONResponse:
        with lock:
            return respond(game.login(credentials.email, credentials.password))

    @app.get("/api/auth/me")
    def me(authorization: str | None = Header(default=None)) -> JSONResponse:
        return free(authorization, game.me)

    @app.get("/api/users")
    def users(authorization: str | None = Header(default=None)) -> JSONResponse:
        return free(authorization, lambda _: game.list_users())

    @app.get("/api/teams")
    def teams(authorization: str | None = Header(default=None)) -> JSONResponse:
        return free(authorization, lambda _: game.list_teams())

    @app.get("/api/nuggets/discover")
    def discover(
        nuggetType: str | None = None, authorization: str | None = Header(default=None)
    ) -> JSONResponse:
        return throttled(authorization, lambda user: game.discover(user, nuggetType))

    @app.get("/api/nuggets/{nugget_id}/claim")
    def claim(
        nugget_id: str, answer: str = "", authorization: str | None = Header(default=None)
    ) -> JSONResponse:
        return throttled(authorization, lambda user: game.claim(user, nugget_id, answer))

    @app.get("/api/users/burst")
    def burst(authorization: str | None = Header(default=None)) -> JSONResponse:
        return throttled(authorization, game.burst)

    @app.get("/api/users/{user_id}/attack")
    def attack(user_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        return throttled(authorization, lambda user: game.attack(user, user_id))

    @app.get("/api/users/{user_id}/defend")
    def defend(
        user_id: str,
        teammateId: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        return throttled(authorization, lambda user: game.defend(user, user_id, teammateId))

    @app.post("/mock/round/{number}")
    def set_round(number: int) -> JSONResponse:
        with lock:
            changed = game.set_round(number)
        return JSONResponse({"round": game.round}, status_code=200 if changed else 400)

    @app.get("/mock/scoreboard")
    def show_scoreboard() -> PlainTextResponse:
        with lock:
            return PlainTextResponse(scoreboard(game))

    @app.post("/mock/config")
    def configure(
        p503: float | None = None,
        token_ttl_s: float | None = None,
        rival_attack_p: float | None = None,
    ) -> JSONResponse:
        with lock:
            game.p503 = game.p503 if p503 is None else p503
            game.token_ttl_s = game.token_ttl_s if token_ttl_s is None else token_ttl_s
            game.rival_attack_p = game.rival_attack_p if rival_attack_p is None else rival_attack_p
        settings = {"p503": game.p503, "token_ttl_s": game.token_ttl_s,
                    "rival_attack_p": game.rival_attack_p}
        return JSONResponse(settings)

    return app


def clock_text(seconds: float) -> str:
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def scoreboard(game: Game) -> str:
    """Standings, plus how long our team took to land each type (the drill targets)."""
    if game.round == 0:
        lines = ["Session over"]
    else:
        elapsed = game.clock() - game.round_started
        left = f", {clock_text(max(0, game.round_seconds - elapsed))} left" if game.round_seconds else ""
        lines = [f"Round {game.round} of {len(game.rounds)}, {clock_text(elapsed)} played{left}"]
    teams: dict[str, list[User]] = {}
    for user in game.users.values():
        teams.setdefault(user.team, []).append(user)
    ranked = sorted(teams.items(), key=lambda item: -sum(u.score for u in item[1]))
    for place, (name, members) in enumerate(ranked, 1):
        ours = "   <- you" if not members[0].is_rival else ""
        lines.append(f"{place:2}. {name:<14}{sum(u.score for u in members):>6}{ours}")
    for name, members in teams.items():
        if members[0].is_rival:
            continue
        lines += ["", f"{name}: time from round start to first accepted claim"]
        last_round = game.round or len(game.rounds)
        for number in range(1, last_round + 1):
            cells = []
            for index, (kind, _) in enumerate(game.rounds[number]):
                took = game.first_claims.get((number, kind, name))
                cells.append(f"{kind} x{index + 1} {clock_text(took) if took is not None else '--:--'}")
            lines.append(f"  round {number}: " + " | ".join(cells))
    return "\n".join(lines) + "\n"


def seed(game: Game, rivals: int, paced: bool = False) -> None:
    """The two test players of config.example.toml plus simulated rival teams.
    With paced=True rivals need time to "write" each solver and every second
    team defends itself, like a real field."""
    game.add_user("alice@mock.test", "alice", "Alice", "Delta Team")
    game.add_user("bob@mock.test", "bob", "Bob", "Delta Team")
    for number in range(1, rivals + 1):
        pace = RIVAL_PACES[(number - 1) % len(RIVAL_PACES)] if paced else 0.0
        for member in ("x", "y"):
            email = f"rival{number}{member}@mock.test"
            name = f"Rival{number}{member}"
            game.add_user(email, "rival", name, f"Rival {number}", True, pace, paced and number % 2 == 0)


def run_rivals(game: Game, lock: threading.Lock) -> None:
    while True:
        with lock:
            for user in list(game.users.values()):
                if user.is_rival:
                    game.rival_turn(user)
        time.sleep(RIVAL_TICK_S)


def run_rounds(game: Game, lock: threading.Lock, minutes: float) -> None:
    """Advance the round on a timer, then end the session and print the result."""
    for upcoming in [*sorted(game.rounds)[1:], 0]:
        time.sleep(minutes * 60)
        with lock:
            game.set_round(upcoming)
            print(f"--- round {upcoming} started" if upcoming else scoreboard(game), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Double Trouble mock server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--throttle-ms", type=int, default=3000, help="base throttle")
    parser.add_argument("--rivals", type=int, default=0, help="simulated rival teams")
    parser.add_argument("--per-type", type=int, default=400, help="nuggets per type")
    parser.add_argument("--seed", type=int, default=None, help="fix the questions (default: new every run)")
    parser.add_argument("--drill", type=int, choices=sorted(PACKS), help="play an unseen drill pack")
    parser.add_argument("--round-minutes", type=float, help="switch rounds on a timer")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    step = args.throttle_ms // 3
    game = Game(
        seed=args.seed if args.seed is not None else int(time.time()),
        base_ms=args.throttle_ms, step_ms=step, cap_ms=args.throttle_ms + 5 * step,
        per_type=args.per_type, rounds=PACKS[args.drill] if args.drill else None,
    )
    seed(game, args.rivals, paced=bool(args.drill))
    app = create_app(game)
    threading.Thread(target=run_rivals, args=(game, app.state.lock), daemon=True).start()
    if args.round_minutes:
        game.round_seconds = args.round_minutes * 60
        threading.Thread(target=run_rounds, args=(game, app.state.lock, args.round_minutes), daemon=True).start()
    print(f"mock on http://127.0.0.1:{args.port}  scoreboard: /mock/scoreboard", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
