"""Core value types shared across the simulator."""

from dataclasses import dataclass
from enum import IntEnum

type Floor = int


class Direction(IntEnum):
    DOWN = -1
    IDLE = 0
    UP = 1


@dataclass(frozen=True, slots=True)
class Request:
    time: int
    id: str
    source: Floor
    dest: Floor

    @property
    def direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN


@dataclass(slots=True, eq=False)
class Passenger:
    request: Request
    elevator: int
    board_time: int | None = None
    dropoff_time: int | None = None

    @property
    def id(self) -> str:
        return self.request.id

    @property
    def source(self) -> Floor:
        return self.request.source

    @property
    def dest(self) -> Floor:
        return self.request.dest

    @property
    def request_time(self) -> int:
        return self.request.time

    @property
    def direction(self) -> Direction:
        return self.request.direction

    @property
    def delivered(self) -> bool:
        return self.dropoff_time is not None

    @property
    def wait_time(self) -> int:
        assert self.board_time is not None
        return self.board_time - self.request.time

    @property
    def travel_time(self) -> int:
        assert self.board_time is not None
        assert self.dropoff_time is not None
        return self.dropoff_time - self.board_time

    @property
    def total_time(self) -> int:
        return self.wait_time + self.travel_time


@dataclass(frozen=True, slots=True)
class BuildingConfig:
    floors: int
    elevators: int
    capacity: int
    lobby: Floor = 1
    """Floor every car starts on."""

    def validate(self) -> None:
        if self.floors < 2:
            raise ValueError("building needs at least 2 floors")
        if self.elevators < 1:
            raise ValueError("building needs at least 1 elevator")
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")
        if not 1 <= self.lobby <= self.floors:
            raise ValueError(f"lobby {self.lobby} is outside floors 1..{self.floors}")

    def validate_request(self, request: Request) -> None:
        for floor in (request.source, request.dest):
            if not 1 <= floor <= self.floors:
                raise ValueError(f"{request.id}: floor {floor} is outside 1..{self.floors}")
        if request.source == request.dest:
            raise ValueError(f"{request.id}: source and dest are both {request.source}")
        if request.time < 0:
            raise ValueError(f"{request.id}: negative request time {request.time}")
