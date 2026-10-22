"""Brute-force assignment: try every car, keep the one that adds the least time.

For each car, replay the route that car will actually drive with this passenger added.
The score is one count of extra ticks:

    extra = ticks until the new passenger steps off
          + ticks everyone already assigned to that car is delayed

No weights and no load penalty. The smallest extra wins. A tie goes to the lowest car id.
"""

from collections.abc import Sequence

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger, Request


class BruteForceDispatcher:
    name = "brute"

    def extra_time(self, request: Request, car: Elevator, now: int) -> int:
        """Extra passenger-time if ``request`` is given to ``car``. Lower is better."""
        before = car.project(now)
        after = car.project(now, extra=Passenger(request, car.id))
        _board, drop = after[request.id]
        delay = sum(after[pid][1] - times[1] for pid, times in before.items())
        return (drop - now) + delay

    def assign(self, request: Request, elevators: Sequence[Elevator], now: int) -> int:
        if not elevators:
            raise ValueError("no elevators to assign")
        chosen = elevators[0]
        best = self.extra_time(request, chosen, now)
        for car in elevators[1:]:
            extra = self.extra_time(request, car, now)
            if extra < best or (extra == best and car.id < chosen.id):
                chosen = car
                best = extra
        return chosen.id
