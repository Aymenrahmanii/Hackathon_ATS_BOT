"""One method per endpoint. Every call is logged as one JSON line."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

TOKEN_MAX_AGE_S = 50 * 60  # tokens last 1 h; log in again before that
LOG_BODY_CHARS = 500
SECRET_KEYS = ("accessToken", "refreshToken")


@dataclass(frozen=True)
class Reply:
    status: int  # 0 means no HTTP answer arrived (timeout, connection error)
    data: Any
    retry_after: float | None = None

    @property
    def message(self) -> str:
        return str(self.data.get("message", "")) if isinstance(self.data, dict) else ""


class Api:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        log_path: Path | None = None,
        timeout_s: float = 5.0,
    ) -> None:
        self.base_url = base_url
        self.email = email
        self.password = password
        self.log_path = log_path
        self.timeout_s = timeout_s
        self.token = ""
        self.logged_in_at = 0.0
        self.session = requests.Session()
        self.session.trust_env = False  # ignore proxy settings from the environment
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)

    # --- not throttle-sensitive -------------------------------------------

    def login(self) -> Reply:
        body = {"email": self.email, "password": self.password}
        reply = self._send("POST", "/api/auth/login", json=body)
        if reply.status == 200 and isinstance(reply.data, dict):
            self.token = reply.data.get("accessToken", "")
            self.logged_in_at = time.monotonic()
        return reply

    def ensure_fresh(self) -> None:
        if time.monotonic() - self.logged_in_at > TOKEN_MAX_AGE_S:
            self.login()

    def me(self) -> Reply:
        return self._free("/api/auth/me")

    def users(self) -> Reply:
        return self._free("/api/users")

    def teams(self) -> Reply:
        return self._free("/api/teams")

    # --- throttle-sensitive: call these only through throttle.Gate --------

    def discover(self, nugget_type: str | None = None) -> Reply:
        query = f"?nuggetType={quote(nugget_type, safe='')}" if nugget_type else ""
        return self._throttled("/api/nuggets/discover" + query)

    def claim(self, nugget_id: str, answer: str) -> Reply:
        return self._throttled(f"/api/nuggets/{nugget_id}/claim?answer={quote(answer, safe='')}")

    def attack(self, user_id: str) -> Reply:
        return self._throttled(f"/api/users/{user_id}/attack")

    def defend(self, attacker_id: str, teammate_id: str | None = None) -> Reply:
        query = f"?teammateId={teammate_id}" if teammate_id else ""
        return self._throttled(f"/api/users/{attacker_id}/defend" + query)

    def burst(self) -> Reply:
        return self._throttled("/api/users/burst")

    # --- plumbing -----------------------------------------------------------

    def _free(self, path: str) -> Reply:
        reply = self._send("GET", path)
        if reply.status == 401 and self.login().status == 200:
            reply = self._send("GET", path)
        return reply

    def _throttled(self, path: str) -> Reply:
        # On 401 we log in again but do NOT retry here: the Gate retries after
        # a full throttle wait, in case the server counted the 401 as an action.
        reply = self._send("GET", path)
        if reply.status == 401:
            self.login()
        return reply

    def _send(self, method: str, path: str, **kwargs: Any) -> Reply:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        started = time.monotonic()
        try:
            response = self.session.request(
                method, self.base_url + path, headers=headers, timeout=self.timeout_s, **kwargs
            )
            reply = Reply(response.status_code, _body(response), _retry_after(response))
        except requests.RequestException as error:
            reply = Reply(0, {"message": type(error).__name__})
        self._log(method, path, reply, time.monotonic() - started)
        return reply

    def _log(self, method: str, path: str, reply: Reply, seconds: float) -> None:
        if not self.log_path:
            return
        line = {
            "t": time.strftime("%H:%M:%S"),
            "call": f"{method} {path}",
            "status": reply.status,
            "ms": round(seconds * 1000),
            "body": json.dumps(_without_secrets(reply.data), ensure_ascii=False)[:LOG_BODY_CHARS],
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")


def _body(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"message": response.text[:200]}


def _retry_after(response: requests.Response) -> float | None:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None


def _without_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: value for key, value in data.items() if key not in SECRET_KEYS}
    return data
