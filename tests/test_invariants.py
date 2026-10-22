"""Property-based checks that must hold on any workload."""

import os
from collections.abc import Iterator, Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from elevator_sim.dispatch import BruteForceDispatcher
from elevator_sim.elevator import Elevator
from elevator_sim.models import BuildingConfig, Passenger, Request
from elevator_sim.simulation import SimulationResult, run_simulation
from elevator_sim.workloads import Pattern, generate

settings.register_profile("default", max_examples=60, deadline=None)
settings.register_profile("thorough", max_examples=2000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


@st.composite
def buildings(draw: st.DrawFn) -> BuildingConfig:
    return BuildingConfig(
        floors=draw(st.integers(2, 20)),
        elevators=draw(st.integers(1, 4)),
        capacity=draw(st.integers(1, 5)),
    )


@st.composite
def workloads(draw: st.DrawFn, building: BuildingConfig) -> list[Request]:
    n = draw(st.integers(0, 40))
    requests = []
    for i in range(n):
        t = draw(st.integers(0, 60))
        source = draw(st.integers(1, building.floors))
        dest = draw(st.integers(1, building.floors - 1))
        dest += dest >= source
        requests.append(Request(t, f"p{i}", source, dest))
    return sorted(requests, key=lambda r: r.time)


@st.composite
def scenarios(draw: st.DrawFn) -> tuple[BuildingConfig, list[Request]]:
    building = draw(buildings())
    return building, draw(workloads(building))


def simulate(building: BuildingConfig, requests: list[Request]) -> SimulationResult:
    return run_simulation(building, BruteForceDispatcher(), requests)


def check_invariants(
    building: BuildingConfig, requests: list[Request], result: SimulationResult
) -> None:
    by_id = {p.id: p for p in result.passengers}

    # Objective 1: everyone is served.
    assert len(result.passengers) == len(requests)
    for p in result.passengers:
        assert p.board_time is not None
        assert p.dropoff_time is not None
        assert p.request_time <= p.board_time < p.dropoff_time
        assert p.travel_time >= abs(p.dest - p.source)

    # Time advances one unit per row; cars move at most one floor per tick, within the shaft.
    for prev, cur in zip(result.positions, result.positions[1:], strict=False):
        for a, b in zip(prev, cur, strict=True):
            assert abs(a - b) <= 1
    for row in result.positions:
        assert all(1 <= f <= building.floors for f in row)

    # Capacity is never exceeded.
    for row in result.loads:
        assert all(0 <= load <= building.capacity for load in row)

    # Boarding/alighting happen at the right floor, in the assigned car.
    for event in result.stop_events:
        assert result.positions[event.time][event.elevator] == event.floor
        for pid in event.boarded:
            p = by_id[pid]
            assert (p.elevator, p.source, p.board_time) == (event.elevator, event.floor, event.time)
        for pid in event.alighted:
            p = by_id[pid]
            assert (p.elevator, p.dest, p.dropoff_time) == (event.elevator, event.floor, event.time)

    # The run ends exactly when the last passenger is delivered (or at t=0 if none).
    last = max((p.dropoff_time or 0 for p in result.passengers), default=0)
    assert result.makespan == max(last, max((r.time for r in requests), default=0))


@given(scenario=scenarios())
def test_invariants(scenario: tuple[BuildingConfig, list[Request]]) -> None:
    building, requests = scenario
    check_invariants(building, requests, simulate(building, requests))


@pytest.mark.parametrize("pattern", list(Pattern))
def test_invariants_realistic_load(pattern: Pattern) -> None:
    building = BuildingConfig(floors=40, elevators=4, capacity=6)
    requests = generate(pattern, passengers=400, floors=40, duration=300, seed=11)
    check_invariants(building, requests, simulate(building, requests))


@given(scenario=scenarios())
def test_deterministic(scenario: tuple[BuildingConfig, list[Request]]) -> None:
    building, requests = scenario
    a = simulate(building, requests)
    b = simulate(building, requests)
    assert a.positions == b.positions
    assert [(p.id, p.elevator, p.board_time, p.dropoff_time) for p in a.passengers] == [
        (p.id, p.elevator, p.board_time, p.dropoff_time) for p in b.passengers
    ]


class PeekGuard:
    """Wraps a request list; records how far the simulation has pulled from it."""

    def __init__(self, requests: list[Request]) -> None:
        self.requests = requests
        self.pulled = 0

    def __iter__(self) -> Iterator[Request]:
        for r in self.requests:
            self.pulled += 1
            yield r


@given(scenario=scenarios())
def test_no_peeking_ahead(scenario: tuple[BuildingConfig, list[Request]]) -> None:
    building, requests = scenario
    guard = PeekGuard(requests)
    inner = BruteForceDispatcher()

    class Spy:
        name = "spy"

        def assign(self, request: Request, elevators: Sequence[Elevator], now: int) -> int:
            assert request.time <= now
            # The feed may buffer at most one not-yet-due request; nothing further.
            future_pulled = [r for r in requests[: guard.pulled] if r.time > now]
            assert len(future_pulled) <= 1
            return inner.assign(request, elevators, now)

    run_simulation(building, Spy(), guard)


@given(scenario=scenarios(), data=st.data())
def test_projection_matches_real_ticks(
    scenario: tuple[BuildingConfig, list[Request]], data: st.DataObject
) -> None:
    """``Elevator.project`` (event-jumping) must agree with tick-by-tick execution."""
    building, requests = scenario
    car = Elevator(0, building.capacity, data.draw(st.integers(1, building.floors)))
    passengers = [Passenger(Request(0, r.id, r.source, r.dest), 0) for r in requests]
    for p in passengers:
        car.assign(p)
    predicted = car.project(0)

    t = 0
    while True:
        car.service_stop(t)
        if car.is_idle:
            break
        car.move()
        t += 1
        assert t < 10_000
    assert {p.id: (p.board_time, p.dropoff_time) for p in passengers} == predicted
