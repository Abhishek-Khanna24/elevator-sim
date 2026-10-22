"""CSV input/output."""

import csv
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from elevator_sim.models import Passenger, Request

REQUEST_FIELDS = ("time", "id", "source", "dest")
_DISCRETE_TIME = re.compile(r"-?\d+")
PASSENGER_FIELDS = (
    "id",
    "request_time",
    "source",
    "dest",
    "elevator",
    "board_time",
    "dropoff_time",
    "wait_time",
    "travel_time",
    "total_time",
)


def _discrete_time(value: str) -> int:
    text = value.strip()
    if _DISCRETE_TIME.fullmatch(text) is None:
        raise ValueError(f"time must be a discrete integer, got {value!r}")
    return int(text)


def read_requests(path: Path) -> list[Request]:
    """Read and time-sort (stably) a ``time,id,source,dest`` CSV."""
    with path.open(newline="") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        if reader.fieldnames is None or tuple(reader.fieldnames) != REQUEST_FIELDS:
            raise ValueError(f"{path}: expected header {','.join(REQUEST_FIELDS)}")
        requests = [
            Request(
                time=_discrete_time(row["time"]),
                id=row["id"].strip(),
                source=int(row["source"]),
                dest=int(row["dest"]),
            )
            for row in reader
        ]
    seen: set[str] = set()
    for r in requests:
        if r.id in seen:
            raise ValueError(f"{path}: duplicate passenger id {r.id!r}")
        seen.add(r.id)
    return sorted(requests, key=lambda r: r.time)


def write_requests(path: Path, requests: Iterable[Request]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(REQUEST_FIELDS)
        writer.writerows((r.time, r.id, r.source, r.dest) for r in requests)


def write_positions(path: Path, positions: Sequence[Sequence[int]]) -> None:
    """One row per tick: ``time,e0,e1,...`` (row index == time)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_elevators = len(positions[0]) if positions else 0
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", *(f"e{i}" for i in range(num_elevators))])
        writer.writerows([t, *row] for t, row in enumerate(positions))


def write_passengers(path: Path, passengers: Iterable[Passenger]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(PASSENGER_FIELDS)
        for p in passengers:
            writer.writerow(
                (
                    p.id,
                    p.request_time,
                    p.source,
                    p.dest,
                    p.elevator,
                    p.board_time,
                    p.dropoff_time,
                    p.wait_time,
                    p.travel_time,
                    p.total_time,
                )
            )
