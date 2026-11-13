"""Settings for one player, read from a TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    base_url: str
    email: str
    password: str
    slot: int | None  # 0 or 1 splits nuggets with the teammate; None takes all
    margin_ms: int
    solvers_dir: Path
    data_dir: Path
    attack_mode: str  # "off", "idle" (dead time only) or "always"


def load(path: Path, player: str) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    who = raw["players"][player]
    return Config(
        base_url=raw["base_url"].rstrip("/"),
        email=who["email"],
        password=who["password"],
        slot=who.get("slot"),
        margin_ms=int(raw.get("margin_ms", 250)),
        solvers_dir=Path(raw.get("solvers_dir", "solvers")),
        data_dir=Path(raw.get("data_dir", "data")),
        attack_mode=str(raw.get("attack_mode", "always")),
    )
