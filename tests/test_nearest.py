"""Nearest-car cost counts floors to the pickup, not a replay of the route."""

from elevator_sim.dispatch import BruteForceDispatcher, NearestDispatcher
from elevator_sim.elevator import Elevator
from elevator_sim.models import BuildingConfig, Direction, Passenger, Request
from elevator_sim.simulation import run_simulation


def test_picks_the_closer_idle_car() -> None:
    far = Elevator(id=0, capacity=4, floor=9)
    near = Elevator(id=1, capacity=4, floor=2)
    request = Request(0, "a", 1, 4)
    dispatcher = NearestDispatcher()
    assert dispatcher.cost(request, near) == 1
    assert dispatcher.cost(request, far) == 8
    assert dispatcher.assign(request, [far, near], 0) == 1


def test_prefers_a_car_already_heading_toward_the_caller() -> None:
    # Car 1 is one floor closer, but it is going down and must finish that trip first.
    going_up = Elevator(
        id=0,
        capacity=4,
        floor=4,
        direction=Direction.UP,
        onboard=[Passenger(Request(0, "up", 1, 12), elevator=0, board_time=0)],
    )
    going_down = Elevator(
        id=1,
        capacity=4,
        floor=5,
        direction=Direction.DOWN,
        onboard=[Passenger(Request(0, "down", 8, 1), elevator=1, board_time=0)],
    )
    request = Request(0, "a", 6, 8)
    dispatcher = NearestDispatcher()
    assert dispatcher.cost(request, going_up) == 2
    assert dispatcher.cost(request, going_down) == 9
    assert dispatcher.assign(request, [going_up, going_down], 0) == 0


def test_ignores_delay_that_brute_force_counts() -> None:
    """The passing car is one floor from the caller. Brute rejects it: the detour delays someone."""
    passing = Elevator(
        id=0,
        capacity=8,
        floor=10,
        direction=Direction.UP,
        onboard=[Passenger(Request(0, "p", 10, 12), elevator=0, board_time=0)],
        waiting=[Passenger(Request(0, "a", 1, 2), elevator=0)],
    )
    idle = Elevator(id=1, capacity=8, floor=14)
    request = Request(0, "n", 11, 20)
    cars = [passing, idle]

    assert NearestDispatcher().cost(request, passing) == 1
    assert NearestDispatcher().cost(request, idle) == 3
    assert NearestDispatcher().assign(request, cars, 0) == 0
    assert BruteForceDispatcher().assign(request, cars, 0) == 1


def test_tie_goes_to_lowest_id() -> None:
    cars = [Elevator(id=1, capacity=4, floor=3), Elevator(id=0, capacity=4, floor=3)]
    assert NearestDispatcher().assign(Request(0, "a", 3, 5), cars, 0) == 0


def test_simulation_delivers_everyone() -> None:
    requests = [Request(0, "a", 1, 4), Request(0, "b", 3, 1)]
    building = BuildingConfig(floors=6, elevators=2, capacity=4)
    result = run_simulation(building, NearestDispatcher(), requests)
    assert result.strategy == "nearest"
    assert {p.id for p in result.passengers if p.delivered} == {"a", "b"}
