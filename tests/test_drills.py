"""SPOILERS: this file names the drill types.

Each drill generator is checked against an independently written solver from
drills/answer_key/. A mismatch means the question text and its expected answer
disagree, which would make the drill unfair.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from dt.registry import Registry
from mockserver.drills import PACKS
from mockserver.game import Game
from mockserver.questions import Generator

SAMPLES = 300
TYPES: list[tuple[str, Generator]] = [
    kind for rounds in PACKS.values() for kinds in rounds.values() for kind in kinds
]


@pytest.fixture(scope="module")
def key() -> Registry:
    registry = Registry(Path("drills/answer_key"), lambda _: None)
    registry.refresh()
    return registry


def test_three_packs_of_nine_distinct_types(key: Registry) -> None:
    names = [name for name, _ in TYPES]
    assert len(names) == len(set(names)) == 27
    assert set(names) == set(key.solvers)
    assert all(len(rounds) == 3 and all(len(k) == 3 for k in rounds.values()) for rounds in PACKS.values())


@pytest.mark.parametrize(("name", "generate"), TYPES, ids=[name for name, _ in TYPES])
def test_answer_key_agrees_with_generator(name: str, generate: Generator, key: Registry) -> None:
    rng = random.Random(2026)
    for _ in range(SAMPLES):
        content, answer = generate(rng)
        assert answer == answer.strip() and answer != ""
        assert key.solvers[name].solve(content) == answer, content


@pytest.mark.parametrize(("name", "generate"), TYPES, ids=[name for name, _ in TYPES])
def test_questions_vary_and_are_reproducible(name: str, generate: Generator) -> None:
    first = [generate(random.Random(seed)) for seed in range(40)]
    again = [generate(random.Random(seed)) for seed in range(40)]
    assert first == again
    assert len({content for content, _ in first}) >= 10


def test_a_drill_pack_runs_in_the_game() -> None:
    game = Game(per_type=20, rounds=PACKS[2])
    alice = game.add_user("alice@mock.test", "alice", "Alice", "Delta")
    body = game.discover(alice)[1]
    assert {n["nuggetType"] for n in body} == {"countLetter", "romanToNumber", "nextNumber"}
    assert game.discover(alice, "reverseWord")[0] == 400  # the practice types are gone
