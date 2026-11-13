"""The Gate: the only code path allowed to call throttle-sensitive endpoints.

Calling early costs a nugget, so the Gate owns all the waiting. Usage:

    gate.wait()            # sleeps; re-reads /api/auth/me just before the slot opens
    ...decide what to do with fresh data...
    reply = gate.send(action)

The re-read matters: an attack that landed during the wait has raised our
throttle. The Gate never retries; the bot simply decides again on its next step.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from dt.client import Api, Reply

RETRY_503_S = 0.15
PENALTY_WINDOW_S = 60.0
MARGIN_STEP_MS = 50


class Gate:
    def __init__(
        self,
        api: Api,
        margin_ms: int,
        lead_s: float = 0.2,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api = api
        self.margin_ms = margin_ms
        self.lead_s = lead_s  # how long before the slot opens we refresh our view
        self.clock = clock
        self.sleep = sleep
        self.on_lead: Callable[[], None] | None = None  # extra free reads, e.g. /api/users
        self.throttle_ms = 3000
        self.me: dict[str, Any] = {}
        # Assume an action just happened: a restarted bot must not fire early.
        self.last_send = clock()
        self.not_before = 0.0
        self.penalties: list[float] = []

    def wait(self) -> None:
        """Sleep until the next throttled call is allowed."""
        self._sleep_until(self._target() - self.lead_s)
        self.refresh()
        if self.on_lead:
            self.on_lead()
        self._sleep_until(self._target())

    def send(self, action: Callable[[], Reply]) -> Reply:
        """Run one throttled call. Call wait() first."""
        sent = self.clock()
        reply = action()
        if reply.status == 503:  # throttle not checked: no penalty, slot not used
            self.not_before = self.clock() + RETRY_503_S
            return reply
        # A timeout (status 0) also lands here: assume the server saw the call.
        self.last_send = sent
        if reply.status == 429:
            self._penalised(reply)
        return reply

    def refresh(self) -> None:
        reply = self.api.me()
        if reply.status == 200 and isinstance(reply.data, dict):
            self.me = reply.data
            self.throttle_ms = int(reply.data.get("totalThrottleMs", self.throttle_ms))

    def _target(self) -> float:
        ready = self.last_send + (self.throttle_ms + self.margin_ms) / 1000
        return max(ready, self.not_before)

    def _sleep_until(self, moment: float) -> None:
        remaining = moment - self.clock()
        if remaining > 0:
            self.sleep(remaining)

    def _penalised(self, reply: Reply) -> None:
        now = self.clock()
        wait = reply.retry_after if reply.retry_after is not None else self.throttle_ms / 1000
        self.not_before = now + wait + self.margin_ms / 1000
        self.penalties = [t for t in self.penalties if now - t < PENALTY_WINDOW_S] + [now]
        if len(self.penalties) >= 2:
            self.margin_ms += MARGIN_STEP_MS
