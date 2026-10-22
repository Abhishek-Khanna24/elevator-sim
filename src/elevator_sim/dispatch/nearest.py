"""Nearest-car cost: send the elevator that reaches the caller in the fewest floors.

The cost of a car is how far it travels before the pickup:

- heading toward the caller, who wants to keep going that way: the floors in between
- otherwise: finish the trip it is already committed to, then come back

Delays to other passengers, and how full the car is, are not counted. The smallest cost
wins. A tie goes to the lowest car id.
"""

from collections.abc import Sequence

from elevator_sim.elevator import Elevator
from elevator_sim.models import Direction, Passenger, Request


class NearestDispatcher:
    name = "nearest"

    def cost(self, request: Request, car: Elevator) -> int:
        """Floors ``car`` travels before it can pick ``request`` up. Lower is better."""
        heading = _heading(car)
        if heading is Direction.IDLE or _on_the_way(car, request, heading):
            return abs(car.floor - request.source)
        turn = _reversal(car, heading)
        return abs(car.floor - turn) + abs(turn - request.source)

    def assign(self, request: Request, elevators: Sequence[Elevator], now: int) -> int:
        if not elevators:
            raise ValueError("no elevators to assign")
        chosen = elevators[0]
        best = self.cost(request, chosen)
        for car in elevators[1:]:
            floors = self.cost(request, car)
            if floors < best or (floors == best and car.id < chosen.id):
                chosen = car
                best = floors
        return chosen.id


def _heading(car: Elevator) -> Direction:
    """Direction the car is committed to, including an idle car that already has work."""
    if car.direction is not Direction.IDLE:
        return car.direction
    here = [p for p in car.waiting if p.source == car.floor]
    if here:
        return _oldest(here).direction
    if car.waiting:
        oldest = _oldest(car.waiting)
        return Direction.UP if oldest.source > car.floor else Direction.DOWN
    if car.onboard:
        dest = car.onboard[0].dest
        if dest > car.floor:
            return Direction.UP
        if dest < car.floor:
            return Direction.DOWN
    return Direction.IDLE


def _on_the_way(car: Elevator, request: Request, heading: Direction) -> bool:
    ahead = (request.source - car.floor) * heading >= 0
    return ahead and request.direction is heading


def _reversal(car: Elevator, heading: Direction) -> int:
    """Furthest floor the car must visit before it can turn around."""
    floor = car.floor
    stops = [floor]
    for passenger in car.onboard:
        if (passenger.dest - floor) * heading > 0:
            stops.append(passenger.dest)
    for passenger in car.waiting:
        if (passenger.source - floor) * heading > 0:
            stops.append(passenger.source)
            if (passenger.dest - floor) * heading > 0:
                stops.append(passenger.dest)
    return max(stops) if heading is Direction.UP else min(stops)


def _oldest(passengers: Sequence[Passenger]) -> Passenger:
    oldest = passengers[0]
    for passenger in passengers[1:]:
        if passenger.request_time < oldest.request_time:
            oldest = passenger
    return oldest
