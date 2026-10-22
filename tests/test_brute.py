"""The brute-force dispatcher tries every car and keeps the least extra time."""

from elevator_sim.dispatch import BruteForceDispatcher
from elevator_sim.elevator import Elevator
from elevator_sim.models import BuildingConfig, Direction, Passenger, Request
from elevator_sim.simulation import run_simulation


def test_picks_the_car_with_less_extra_time() -> None:
    far = Elevator(id=0, capacity=4, floor=9)
    near = Elevator(id=1, capacity=4, floor=1)
    request = Request(0, "a", 1, 2)
    assert BruteForceDispatcher().assign(request, [far, near], 0) == 1
    assert BruteForceDispatcher().extra_time(request, near, 0) == 1
    assert BruteForceDispatcher().extra_time(request, far, 0) == 9


def test_tie_goes_to_lowest_id() -> None:
    """Both cars deliver the new passenger at the same time, so the lowest id wins."""
    already = Passenger(Request(0, "old", 1, 3), elevator=0, board_time=0)
    occupied = Elevator(id=0, capacity=8, floor=1, direction=Direction.UP, onboard=[already])
    empty = Elevator(id=1, capacity=8, floor=1)
    request = Request(0, "new", 1, 3)

    assert BruteForceDispatcher().assign(request, [occupied, empty], 0) == 0


def test_simulation_delivers_everyone() -> None:
    requests = [Request(0, "a", 1, 4), Request(0, "b", 3, 1)]
    building = BuildingConfig(floors=6, elevators=2, capacity=4)
    result = run_simulation(building, BruteForceDispatcher(), requests)
    assert result.strategy == "brute"
    assert {p.id for p in result.passengers if p.delivered} == {"a", "b"}
