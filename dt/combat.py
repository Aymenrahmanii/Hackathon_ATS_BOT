"""Defense, burst and attack decisions, from the free endpoints.

World keeps a picture of the other players (/api/users, /api/teams) and
answers two questions: "what must I defend right now?" and "who is worth
attacking?". It never calls a throttled endpoint itself.

The arithmetic behind the rules (see PLAN.md, sections 4.5 and 4.6):
- one attacker slows the victim by one action every 12 s, so defending
  (one action) always pays;
- burst costs one action + 3 points, defending k attackers costs k actions,
  so burst wins when k * p > p + 3, p being the points of one claim.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dt.client import Api, Reply

BURST_COST = 3
MAX_ATTACKERS = 5  # 3000 ms + 5 x 1000 ms = the 8000 ms cap
TEAMS_EVERY_S = 30.0
DEFENDER_S = 30.0  # an attack shaken off faster than this marks a defender
CONFIRM_S = 5.0  # /api/users lags; give our attack this long to show up
LIMIT_RETRY_S = 30.0
TOP_TEAMS = 3


@dataclass(frozen=True)
class Move:
    kind: str  # "burst", "defend" or "attack"
    target: str = ""  # the attacker to defend from, or the user to attack
    mate: str | None = None  # set when defending a teammate


def ids(entries: Any) -> list[str]:
    """attackedBy / attacking as plain ids, whether the server sends ids or objects."""
    return [str(e.get("_id")) if isinstance(e, dict) else str(e) for e in entries or []]


def should_burst(attackers: int, score: int, claim_value: float) -> bool:
    if score < BURST_COST or claim_value <= 0:
        return False  # with nothing to claim, defending one by one is free
    return attackers * claim_value > claim_value + BURST_COST


class World:
    def __init__(self, api: Api, clock: Callable[[], float] = time.monotonic) -> None:
        self.api = api
        self.clock = clock
        self.me_id = ""
        self.users: dict[str, dict[str, Any]] = {}
        self.team_of: dict[str, str] = {}
        self.teams_at = -math.inf
        self.hits: dict[str, float] = {}  # target -> when our attack landed
        self.confirmed: set[str] = set()  # hits we have seen in the target's attackedBy
        self.defenders: set[str] = set()  # targets that shook us off quickly
        self.skip_until: dict[str, float] = {}  # targets the server refused
        self.mate_hits: dict[tuple[str, str], float] = {}  # (mate, attacker) -> first seen

    # --- keeping the picture current -----------------------------------------

    def refresh(self, me: dict[str, Any]) -> None:
        self.me_id = str(me.get("_id", ""))
        reply = self.api.users()
        if reply.status == 200 and isinstance(reply.data, list):
            self.users = {str(u["_id"]): u for u in reply.data if "_id" in u}
        if self.clock() - self.teams_at > TEAMS_EVERY_S:
            self._load_teams()
        self._track_hits()
        self._track_mates()

    def _load_teams(self) -> None:
        reply = self.api.teams()
        if reply.status != 200 or not isinstance(reply.data, list):
            return
        self.teams_at = self.clock()
        self.team_of = {
            str(member["_id"]): str(team.get("name", team.get("_id")))
            for team in reply.data
            for member in team.get("members", [])
        }

    def _track_hits(self) -> None:
        """Learn who defends: did our attack disappear, and how fast?"""
        now = self.clock()
        for target, since in list(self.hits.items()):
            user = self.users.get(target)
            if user is None:
                continue
            if self.me_id in ids(user.get("attackedBy")):
                self.confirmed.add(target)
            elif target in self.confirmed or now - since > CONFIRM_S:
                if now - since < DEFENDER_S:
                    self.defenders.add(target)
                del self.hits[target]
                self.confirmed.discard(target)

    def _track_mates(self) -> None:
        now = self.clock()
        current = {(m["_id"], a) for m in self.mates() for a in ids(m.get("attackedBy"))}
        self.mate_hits = {pair: self.mate_hits.get(pair, now) for pair in current}

    # --- defense ---------------------------------------------------------------

    def mates(self) -> list[dict[str, Any]]:
        mine = self.team_of.get(self.me_id)
        if mine is None:
            return []
        return [
            u for uid, u in self.users.items() if self.team_of.get(uid) == mine and uid != self.me_id
        ]

    def defence(self, me: dict[str, Any], claim_value: float) -> Move | None:
        """Burst or defend, for me first and then for a teammate. None if all is calm."""
        mine = sorted(ids(me.get("attackedBy")))
        if mine:
            if should_burst(len(mine), int(me.get("score", 0)), claim_value):
                return Move("burst")
            return Move("defend", mine[0])  # I take my lowest attacker id...
        for mate in self.mates():
            theirs = sorted(ids(mate.get("attackedBy")))
            late = [a for a in theirs if self._overdue(mate, a)]
            if late:  # their bot is not coping: help whatever the count
                return Move("defend", late[-1], mate["_id"])
            if should_burst(len(theirs), int(mate.get("score", 0)), claim_value):
                continue  # they are about to burst; a defend would be wasted
            if len(theirs) >= 2:  # ...so my teammate helps from the highest id
                return Move("defend", theirs[-1], mate["_id"])
        return None

    def _overdue(self, mate: dict[str, Any], attacker: str) -> bool:
        seen = self.mate_hits.get((mate["_id"], attacker))
        patience = 2 * (3 + len(ids(mate.get("attackedBy")))) + 2  # two of their slots
        return seen is not None and self.clock() - seen > patience

    # --- attack ----------------------------------------------------------------

    def target(self, priority_only: bool) -> str | None:
        """Best user to attack now. priority_only keeps it to teams that threaten
        our rank and are scoring: used while we still have nuggets to claim."""
        mine = self.team_of.get(self.me_id)
        if mine is None:
            return None  # teams unknown: we could hit a teammate
        totals: dict[str, int] = {}
        for uid, user in self.users.items():
            team = self.team_of.get(uid)
            if team is not None:
                totals[team] = totals.get(team, 0) + int(user.get("score", 0))
        totals.setdefault(mine, 0)
        wanted = self._threats(mine, totals) if priority_only else set(totals) - {mine}
        now = self.clock()
        open_targets = [
            (totals[self.team_of[uid]], int(user.get("score", 0)), uid)
            for uid, user in self.users.items()
            if self.team_of.get(uid) in wanted
            and not user.get("isAdmin")
            and uid not in self.defenders
            and uid not in self.hits
            and self.skip_until.get(uid, 0) <= now
            and self.me_id not in ids(user.get("attackedBy"))
            and len(ids(user.get("attackedBy"))) < MAX_ATTACKERS
        ]
        return max(open_targets)[2] if open_targets else None

    def _threats(self, mine: str, totals: dict[str, int]) -> set[str]:
        ranking = sorted(totals, key=lambda team: totals[team], reverse=True)
        place = ranking.index(mine)
        others = [team for team in ranking if team != mine]
        near = set(others[:TOP_TEAMS]) | set(ranking[max(0, place - 1) : place + 2])
        return {team for team in near if team != mine and totals[team] > 0}

    def attacked(self, target: str, reply: Reply) -> None:
        """Record the outcome of an attack so we never waste a slot repeating it."""
        if reply.status == 200:
            self.hits[target] = self.clock()
        elif reply.status in (400, 404):
            limit = "limit" in reply.message.lower()
            self.skip_until[target] = self.clock() + LIMIT_RETRY_S if limit else math.inf
