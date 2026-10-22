"""Hand-checkable scenarios with exact expected timings."""

import pytest

from elevator_sim.dispatch import BruteForceDispatcher
from elevator_sim.models import BuildingConfig, Request
from elevator_sim.simulation import SimulationResult, run_simulation

SPEC_SAMPLE = [
    Request(0, "passenger1", 1, 51),
    Request(0, "passenger2", 1, 37),
    Request(10, "passenger3", 20, 1),
]


def run(
    requests: list[Request],
    floors: int = 60,
    elevators: int = 1,
    capacity: int = 8,
) -> SimulationResult:
    building = BuildingConfig(floors, elevators, capacity)
    return run_simulation(building, BruteForceDispatcher(), requests)


def times(result: SimulationResult) -> dict[str, tuple[int | None, int | None]]:
    return {p.id: (p.board_time, p.dropoff_time) for p in result.passengers}


def test_spec_sample_single_elevator() -> None:
    result = run(SPEC_SAMPLE)
    # Both lobby riders board at t=0; the car passes floor 20 going up at t=19, so the
    # down-bound passenger3 is collected on the way back down (LOOK): 51 -> 20 is 31 floors.
    assert times(result) == {
        "passenger1": (0, 50),
        "passenger2": (0, 36),
        "passenger3": (81, 100),
    }
    assert result.makespan == 100
    assert len(result.positions) == 101
    assert result.positions[0] == (1,)
    assert result.positions[50] == (51,)
    assert result.positions[100] == (1,)


def test_spec_sample_three_elevators_uses_idle_car() -> None:
    result = run(SPEC_SAMPLE, elevators=3)
    t = times(result)
    assert t["passenger3"] == (29, 48)
    assert result.makespan == 50


def test_ticks_through_gaps_one_unit_at_a_time() -> None:
    result = run([Request(100, "late", 1, 3)])
    assert len(result.positions) == 103
    assert all(row == (1,) for row in result.positions[:101])
    assert result.positions[101:] == [(2,), (3,)]
    assert result.elevators[0].idle_ticks == 100


def test_wait_and_travel_metrics() -> None:
    result = run([Request(0, "a", 5, 2)])
    (p,) = result.passengers
    assert (p.board_time, p.dropoff_time) == (4, 7)
    assert (p.wait_time, p.travel_time, p.total_time) == (4, 3, 7)


def test_capacity_forces_second_trip() -> None:
    result = run([Request(0, "a", 1, 4), Request(0, "b", 1, 4)], capacity=1)
    assert times(result) == {"a": (0, 3), "b": (6, 9)}
    assert max(load for (load,) in result.loads) == 1


def test_car_does_not_board_opposite_direction() -> None:
    # Car heads up for "far"; "down" is waiting at 3 wanting to go down and must wait.
    requests = [Request(0, "far", 1, 6), Request(0, "down", 3, 1)]
    result = run(requests, floors=6)
    t = times(result)
    assert t["far"] == (0, 5)
    assert t["down"] == (8, 10)


def test_rider_picked_up_en_route_same_direction() -> None:
    result = run([Request(0, "a", 1, 10), Request(2, "b", 5, 8)], floors=10)
    assert times(result) == {"a": (0, 9), "b": (4, 7)}
    assert result.elevators[0].stops == 4


def test_idle_car_heads_for_oldest_request() -> None:
    # The car sets off toward "old" and collects "new" on the way since it is same-direction.
    result = run([Request(0, "old", 10, 1), Request(1, "new", 2, 3)], floors=10)
    assert times(result) == {"old": (9, 18), "new": (1, 2)}


@pytest.mark.parametrize(
    ("building", "message"),
    [
        (BuildingConfig(1, 1, 4), "2 floors"),
        (BuildingConfig(10, 0, 4), "1 elevator"),
        (BuildingConfig(10, 2, 0), "capacity"),
        (BuildingConfig(10, 2, 4, lobby=11), "lobby"),
    ],
)
def test_invalid_building_rejected(building: BuildingConfig, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        building.validate()


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (Request(0, "x", 0, 3), "outside"),
        (Request(0, "x", 1, 99), "outside"),
        (Request(0, "x", 4, 4), "both 4"),
    ],
)
def test_invalid_requests_rejected(bad: Request, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        run([bad], floors=10)


def test_empty_input() -> None:
    result = run([], elevators=2)
    assert result.positions == [(1, 1)]
    assert result.passengers == []
