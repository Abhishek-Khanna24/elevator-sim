"""Discrete-time simulation loop."""

from collections.abc import Iterable
from dataclasses import dataclass

from elevator_sim.dispatch.base import Dispatcher
from elevator_sim.elevator import Elevator
from elevator_sim.feed import RequestFeed
from elevator_sim.models import BuildingConfig, Floor, Passenger, Request

DEFAULT_MAX_TICKS = 10_000_000


@dataclass(frozen=True, slots=True)
class StopEvent:
    time: int
    elevator: int
    floor: Floor
    alighted: tuple[str, ...]
    boarded: tuple[str, ...]


@dataclass(slots=True)
class SimulationResult:
    building: BuildingConfig
    strategy: str
    passengers: list[Passenger]
    elevators: list[Elevator]
    positions: list[tuple[Floor, ...]]
    """``positions[t][i]`` is elevator ``i``'s floor at time ``t``."""
    loads: list[tuple[int, ...]]
    """``loads[t][i]`` is elevator ``i``'s passenger count at time ``t`` (after boarding)."""
    stop_events: list[StopEvent]

    @property
    def makespan(self) -> int:
        return len(self.positions) - 1


def run_simulation(
    building: BuildingConfig,
    dispatcher: Dispatcher,
    requests: Iterable[Request],
    max_ticks: int = DEFAULT_MAX_TICKS,
) -> SimulationResult:
    """Run until every request has been released and every passenger delivered.

    Within each tick ``t``:
      1. release requests with ``time <= t`` and assign each to an elevator;
      2. every elevator unloads, picks its LOOK direction and boards waiters;
      3. log positions at ``t``;
      4. every elevator moves one floor (or idles).
    """
    building.validate()
    feed = RequestFeed(requests)
    elevators = [
        Elevator(id=i, capacity=building.capacity, floor=building.lobby)
        for i in range(building.elevators)
    ]
    passengers: list[Passenger] = []
    positions: list[tuple[Floor, ...]] = []
    loads: list[tuple[int, ...]] = []
    stop_events: list[StopEvent] = []
    undelivered = 0

    for t in range(max_ticks):
        for request in feed.release(t):
            building.validate_request(request)
            car_id = dispatcher.assign(request, elevators, t)
            passenger = Passenger(request, car_id)
            elevators[car_id].assign(passenger)
            passengers.append(passenger)
            undelivered += 1

        for car in elevators:
            alighted, boarded = car.service_stop(t)
            undelivered -= len(alighted)
            if alighted or boarded:
                stop_events.append(
                    StopEvent(
                        t,
                        car.id,
                        car.floor,
                        tuple(p.id for p in alighted),
                        tuple(p.id for p in boarded),
                    )
                )

        positions.append(tuple(car.floor for car in elevators))
        loads.append(tuple(car.load for car in elevators))

        if feed.exhausted and undelivered == 0:
            break

        for car in elevators:
            car.move()
    else:
        raise RuntimeError(f"simulation did not finish within {max_ticks} ticks")

    return SimulationResult(
        building=building,
        strategy=dispatcher.name,
        passengers=passengers,
        elevators=elevators,
        positions=positions,
        loads=loads,
        stop_events=stop_events,
    )
