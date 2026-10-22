"""Dispatcher interface."""

from collections.abc import Sequence
from typing import Protocol

from elevator_sim.elevator import Elevator
from elevator_sim.models import Request


class Dispatcher(Protocol):
    """Assigns each new request to exactly one elevator, immediately and irrevocably."""

    name: str

    def assign(self, request: Request, elevators: Sequence[Elevator], now: int) -> int: ...
