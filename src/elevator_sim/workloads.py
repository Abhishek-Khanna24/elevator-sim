"""Seeded synthetic traffic patterns."""

import random
from enum import StrEnum

from elevator_sim.models import Floor, Request


class Pattern(StrEnum):
    UNIFORM = "uniform"
    UP_PEAK = "up-peak"
    DOWN_PEAK = "down-peak"
    LUNCH = "lunch"


# (from lobby, to lobby, floor-to-floor) trip mix for each pattern.
MIXES: dict[Pattern, tuple[float, float, float]] = {
    Pattern.UP_PEAK: (0.85, 0.05, 0.10),
    Pattern.DOWN_PEAK: (0.05, 0.85, 0.10),
    Pattern.LUNCH: (0.40, 0.40, 0.20),
}


def _other_floor(rng: random.Random, floors: int, exclude: Floor) -> Floor:
    floor = rng.randint(1, floors - 1)
    return floor + 1 if floor >= exclude else floor


def generate(
    pattern: Pattern,
    *,
    passengers: int,
    floors: int,
    duration: int,
    seed: int = 0,
    lobby: Floor = 1,
) -> list[Request]:
    """``passengers`` requests with arrival times uniform over ``[0, duration)``."""
    if floors < 2:
        raise ValueError("need at least 2 floors")
    rng = random.Random(seed)
    times = sorted(rng.randrange(max(duration, 1)) for _ in range(passengers))
    requests: list[Request] = []
    for i, t in enumerate(times):
        if pattern is Pattern.UNIFORM:
            source = rng.randint(1, floors)
            dest = _other_floor(rng, floors, source)
        else:
            kind = rng.choices(range(3), weights=MIXES[pattern])[0]
            match kind:
                case 0:
                    source, dest = lobby, _other_floor(rng, floors, lobby)
                case 1:
                    source, dest = _other_floor(rng, floors, lobby), lobby
                case _ if floors > 2:
                    source = _other_floor(rng, floors, lobby)
                    dest = rng.choice([f for f in range(1, floors + 1) if f not in (source, lobby)])
                case _:
                    source, dest = lobby, _other_floor(rng, floors, lobby)
        requests.append(Request(t, f"passenger{i + 1}", source, dest))
    return requests
