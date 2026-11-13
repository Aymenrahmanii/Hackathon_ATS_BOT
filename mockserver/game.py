"""Game rules of spec v1.6 as plain Python, no HTTP. Each action returns
(status, body, headers) so the same logic serves the routes and the tests.

Where the spec is silent the mock picks one behaviour; those spots are marked
ASSUMPTION and must be checked against the real server in the warm-up.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mockserver.questions import ROUNDS, Generator

Result = tuple[int, Any, dict[str, str]]
DISCOVER_LIMIT = 100
BURST_COST = 3
# Minutes into a round at which a simulated rival of pace 1.0 "ships" its x1, x2
# and x3 solver. A rival's pace multiplies these; pace 0 means it can claim at once.
RIVAL_UNLOCK_MIN = (2.0, 7.0, 15.0)


@dataclass
class User:
    id: str
    email: str
    password: str
    firstname: str
    lastname: str
    team: str
    is_rival: bool = False
    pace: float = 0.0  # rivals only: see RIVAL_UNLOCK_MIN
    defends: bool = False  # rivals only: shakes off attacks on its next slot
    score: int = 0
    attacked_by: list[str] = field(default_factory=list)
    attacking: list[str] = field(default_factory=list)
    ever_attacked: set[str] = field(default_factory=set)
    last_action: float = -1e9
    refresh_token: str = ""


@dataclass
class Nugget:
    id: str
    content: str
    type: str
    coefficient: int
    answer: str
    round: int
    claimed_by: str | None = None


def ok(message: str, **extra: Any) -> Result:
    return 200, {"success": True, "message": message, **extra}, {}


def fail(status: int, message: str) -> Result:
    return status, {"success": False, "message": message}, {}


class Game:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        seed: int = 0,
        base_ms: int = 3000,
        step_ms: int = 1000,
        cap_ms: int = 8000,
        per_type: int = 400,
        token_ttl_s: float = 3600.0,
        attack_once_ever: bool = False,
        rounds: dict[int, list[tuple[str, Generator]]] | None = None,
    ) -> None:
        self.clock = clock
        self.rng = random.Random(seed)
        self.base_ms = base_ms
        self.step_ms = step_ms
        self.cap_ms = cap_ms
        self.token_ttl_s = token_ttl_s
        # ASSUMPTION: "attack each user only once" means once while the attack
        # stands. Set True to model once per session.
        self.attack_once_ever = attack_once_ever
        self.p503 = 0.0
        self.rival_attack_p = 0.0
        self.rounds = rounds or ROUNDS
        self.round = 1
        self.round_started = clock()
        self.round_seconds: float | None = None  # set when rounds are timed
        self.first_claims: dict[tuple[int, str, str], float] = {}  # (round, type, team) -> seconds
        self.users: dict[str, User] = {}
        self.tokens: dict[str, tuple[str, float]] = {}
        self.nuggets: dict[str, Nugget] = {}
        for number, kinds in self.rounds.items():
            for index, (name, generate) in enumerate(kinds):
                for _ in range(per_type):
                    content, answer = generate(self.rng)
                    nugget = Nugget(self._new_id(), content, name, index + 1, answer, number)
                    self.nuggets[nugget.id] = nugget

    # --- setup ---------------------------------------------------------------

    def add_user(
        self, email: str, password: str, name: str, team: str,
        rival: bool = False, pace: float = 0.0, defends: bool = False,
    ) -> User:
        user = User(self._new_id(), email, password, name, "Mock", team, rival, pace, defends)
        user.refresh_token = self._new_id()
        self.users[user.id] = user
        return user

    def _new_id(self) -> str:
        return f"{self.rng.getrandbits(96):024x}"

    # --- auth and throttle -----------------------------------------------------

    def login(self, email: str, password: str) -> Result:
        user = next((u for u in self.users.values() if u.email == email), None)
        if user is None:
            return 404, {"message": "User not found"}, {}
        if user.password != password:
            return 400, {"message": "Invalid credentials"}, {}
        token = self._new_id() + self._new_id()
        self.tokens[token] = (user.id, self.clock() + self.token_ttl_s)
        return 200, {"accessToken": token, "refreshToken": user.refresh_token}, {}

    def user_for(self, token: str) -> User | None:
        user_id, expires = self.tokens.get(token, ("", 0.0))
        return self.users.get(user_id) if self.clock() < expires else None

    def throttle_ms(self, user: User) -> int:
        return min(self.cap_ms, self.base_ms + self.step_ms * len(user.attacked_by))

    def gate(self, user: User) -> Result | None:
        """Throttle check for one action. None means the action may proceed."""
        if self.rng.random() < self.p503:
            return 503, {"message": "Throttle check unavailable"}, {}
        now = self.clock()
        wait = user.last_action + self.throttle_ms(user) / 1000 - now
        if wait > 0:
            # ASSUMPTION: the penalty is 1 score point, the score never goes
            # below 0, and a 429 does not restart the throttle timer.
            user.score = max(0, user.score - 1)
            return 429, {"message": "Too many requests"}, {"Retry-After": str(math.ceil(wait))}
        # ASSUMPTION: every call that passes the check uses the slot, even
        # when the action itself then fails with 400 or 404.
        user.last_action = now
        return None

    # --- reads -------------------------------------------------------------------

    def me(self, user: User) -> Result:
        body = self._public(user) | {
            "refreshToken": user.refresh_token,
            "totalThrottleMs": self.throttle_ms(user),
        }
        return 200, body, {}

    def list_users(self) -> Result:
        return 200, [self._public(u) for u in self.users.values()], {}

    def list_teams(self) -> Result:
        teams: dict[str, list[User]] = {}
        for user in self.users.values():
            teams.setdefault(user.team, []).append(user)
        body = [
            {
                "_id": f"team-{name}",
                "name": name,
                "members": [
                    {"_id": m.id, "email": m.email, "firstname": m.firstname,
                     "lastname": m.lastname, "score": m.score}
                    for m in members
                ],
                "totalScore": sum(m.score for m in members),
            }
            for name, members in teams.items()
        ]
        return 200, body, {}

    def _public(self, user: User) -> dict[str, Any]:
        # ASSUMPTION: attackedBy / attacking hold plain user ids.
        return {
            "_id": user.id, "email": user.email, "firstname": user.firstname,
            "lastname": user.lastname, "attackedBy": list(user.attacked_by),
            "attacking": list(user.attacking), "isAdmin": False, "score": user.score,
        }

    # --- nuggets -----------------------------------------------------------------

    def _open(self, nugget_type: str | None = None) -> list[Nugget]:
        return [
            n for n in self.nuggets.values()
            if n.round == self.round and n.claimed_by is None
            and (nugget_type is None or n.type == nugget_type)
        ]

    def discover(self, user: User, nugget_type: str | None = None) -> Result:
        current = {name for name, _ in self.rounds.get(self.round, [])}
        if nugget_type is not None and nugget_type not in current:
            return 400, {"message": "Unknown nugget type"}, {}
        found = self._open(nugget_type)
        picked = self.rng.sample(found, min(DISCOVER_LIMIT, len(found)))
        body = [
            {"_id": n.id, "content": n.content, "nuggetType": n.type,
             "claimed": False, "coefficient": n.coefficient}
            for n in picked
        ]
        return 200, body, {}

    def claim(self, user: User, nugget_id: str, answer: str) -> Result:
        nugget = self.nuggets.get(nugget_id)
        if nugget is None or nugget.round != self.round:
            return fail(404, "Nugget not found")
        if nugget.claimed_by is not None:
            return fail(400, "Nugget already claimed")
        if answer != nugget.answer:
            return fail(400, "Wrong answer")
        nugget.claimed_by = user.id
        user.score += nugget.coefficient
        key = (self.round, nugget.type, user.team)
        self.first_claims.setdefault(key, self.clock() - self.round_started)
        return ok("Nugget claimed successfully", nugget={"_id": nugget.id, "claimed": True})

    # --- combat ------------------------------------------------------------------

    def attack(self, user: User, target_id: str) -> Result:
        target = self.users.get(target_id)
        if target is None:
            return fail(404, "The Victim is not found. ⚔️⚔️")
        if target is user:
            return fail(400, "You cannot attack yourself. ⚔️⚔️")
        if target.team == user.team:
            return fail(400, "You cannot attack your Teammate. ⚔️⚔️")
        repeated = self.attack_once_ever and target.id in user.ever_attacked
        if user.id in target.attacked_by or repeated:
            return fail(400, "You have already attacked this user. ⚔️⚔️")
        if self.throttle_ms(target) >= self.cap_ms:
            return fail(400, "This victim is currently reaching their throttle limit. ⚔️⚔️")
        target.attacked_by.append(user.id)
        user.attacking.append(target.id)
        user.ever_attacked.add(target.id)
        return ok("Attack successful! ⚔️ Target's throttle increased.")

    def defend(self, user: User, attacker_id: str, teammate_id: str | None = None) -> Result:
        attacker = self.users.get(attacker_id)
        if attacker is None:
            return fail(404, "Attacker not found. 🛡️")
        if attacker is user:
            return fail(400, "You cannot defend from yourself. 🛡️")
        if teammate_id is None:
            if attacker.id not in user.attacked_by:
                return fail(400, f"You have not been attacked by {attacker.firstname}. 🛡️")
            self._lift(attacker, user)
            return ok("Defense successful! 🛡️ Nice recovery 👌")
        mate = self.users.get(teammate_id)
        if mate is None or mate is user or mate.team != user.team:
            return fail(404, "Teammate not found. 🛡️")
        if attacker.id not in mate.attacked_by:
            names = f"{attacker.firstname} is not attacking your teammate {mate.firstname}"
            return fail(400, f"{names}. 🛡️")
        self._lift(attacker, mate)
        return ok(f"Defense successful! 🛡️ You protected your teammate {mate.firstname}")

    def burst(self, user: User) -> Result:
        if user.score < BURST_COST:
            return fail(400, "Not enough nuggets, 3 are needed for burst mode. 🔥")
        user.score -= BURST_COST
        for attacker_id in list(user.attacked_by):
            self._lift(self.users[attacker_id], user)
        return ok("Burst mode activated! 🔥 All attacks revoked, throttle reset to 3000ms.")

    def _lift(self, attacker: User, victim: User) -> None:
        victim.attacked_by.remove(attacker.id)
        attacker.attacking.remove(victim.id)

    # --- mock-only controls --------------------------------------------------------

    def set_round(self, number: int) -> bool:
        """Round 0 means the session is over: nothing can be discovered or claimed."""
        if number != 0 and number not in self.rounds:
            return False
        self.round = number
        self.round_started = self.clock()
        return True

    def rival_reach(self, rival: User) -> int:
        """Highest coefficient this rival can claim so far in the current round."""
        if rival.pace <= 0:
            return len(RIVAL_UNLOCK_MIN)
        minutes = (self.clock() - self.round_started) / 60 / rival.pace
        return sum(minutes >= unlock for unlock in RIVAL_UNLOCK_MIN)

    def rival_turn(self, rival: User) -> None:
        """A simulated rival takes one action if its throttle allows."""
        now = self.clock()
        if now < rival.last_action + self.throttle_ms(rival) / 1000:
            return
        if rival.defends and rival.attacked_by:
            rival.last_action = now
            self.defend(rival, rival.attacked_by[0])
            return
        players = [u for u in self.users.values() if not u.is_rival]
        if players and self.rng.random() < self.rival_attack_p:
            rival.last_action = now
            self.attack(rival, self.rng.choice(players).id)
            return
        reach = self.rival_reach(rival)
        available = [n for n in self._open() if n.coefficient <= reach]
        if available:
            best = max(n.coefficient for n in available)
            nugget = self.rng.choice([n for n in available if n.coefficient == best])
            rival.last_action = now
            nugget.claimed_by = rival.id
            rival.score += nugget.coefficient
