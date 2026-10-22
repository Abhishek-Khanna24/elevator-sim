"""A single elevator car: LOOK movement, capacity, and direction-aware boarding."""

from dataclasses import dataclass, field

from elevator_sim.models import Direction, Floor, Passenger

type Projection = dict[str, tuple[int, int]]
"""Passenger id -> (board_time, dropoff_time), assuming the car gets no further work."""


@dataclass(slots=True)
class Elevator:
    id: int
    capacity: int
    floor: Floor
    direction: Direction = Direction.IDLE
    onboard: list[Passenger] = field(default_factory=list)
    waiting: list[Passenger] = field(default_factory=list)
    floors_traveled: int = 0
    idle_ticks: int = 0
    stops: int = 0
    peak_load: int = 0
    passengers_served: int = 0
    version: int = 0
    """Bumped whenever state changes, so dispatchers can cache projections."""

    @property
    def load(self) -> int:
        return len(self.onboard)

    @property
    def is_idle(self) -> bool:
        return not self.onboard and not self.waiting

    def assign(self, passenger: Passenger) -> None:
        self.waiting.append(passenger)
        self.version += 1

    def _choose_direction(self) -> Direction:
        """LOOK: keep going while there is work ahead, otherwise reverse, otherwise idle.

        Waiters on the current floor only count if there is room for them, so a full car never
        "keeps going" toward nothing.
        """
        floor = self.floor
        has_room = self.load < self.capacity
        above = any(p.dest > floor for p in self.onboard) or any(
            p.source > floor for p in self.waiting
        )
        below = any(p.dest < floor for p in self.onboard) or any(
            p.source < floor for p in self.waiting
        )
        here = [p for p in self.waiting if p.source == floor] if has_room else []
        here_up = any(p.direction is Direction.UP for p in here)
        here_down = any(p.direction is Direction.DOWN for p in here)

        match self.direction:
            case Direction.UP:
                if above or here_up:
                    return Direction.UP
                if below or here_down:
                    return Direction.DOWN
            case Direction.DOWN:
                if below or here_down:
                    return Direction.DOWN
                if above or here_up:
                    return Direction.UP
            case Direction.IDLE:
                if here:
                    return min(here, key=lambda p: p.request_time).direction
                if self.waiting:
                    oldest = min(self.waiting, key=lambda p: p.request_time)
                    return Direction.UP if oldest.source > floor else Direction.DOWN
        return Direction.IDLE

    def service_stop(self, now: int) -> tuple[list[Passenger], list[Passenger]]:
        """Unload, pick a direction, then board compatible waiters (FIFO). Returns (out, in)."""
        alighted = [p for p in self.onboard if p.dest == self.floor]
        if alighted:
            self.onboard = [p for p in self.onboard if p.dest != self.floor]
            for p in alighted:
                p.dropoff_time = now
            self.passengers_served += len(alighted)

        self.direction = self._choose_direction()

        boarded: list[Passenger] = []
        if self.direction is not Direction.IDLE:
            candidates = sorted(
                (
                    p
                    for p in self.waiting
                    if p.source == self.floor and p.direction is self.direction
                ),
                key=lambda p: p.request_time,
            )
            room = self.capacity - self.load
            boarded = candidates[:room]
            if boarded:
                boarded_ids = {id(p) for p in boarded}
                self.waiting = [p for p in self.waiting if id(p) not in boarded_ids]
                self.onboard.extend(boarded)
                for p in boarded:
                    p.board_time = now
                self.peak_load = max(self.peak_load, self.load)
            self.direction = self._choose_direction()

        if alighted or boarded:
            self.stops += 1
        self.version += 1
        return alighted, boarded

    def move(self) -> None:
        """Advance one floor in the current direction (one tick)."""
        if self.direction is Direction.IDLE:
            self.idle_ticks += 1
            return
        self.floor += self.direction
        self.floors_traveled += 1
        self.version += 1

    def _next_event_floor(self) -> Floor | None:
        """Nearest floor ahead where something could happen (a drop-off or a waiter)."""
        floor, d = self.floor, self.direction
        ahead = [p.dest for p in self.onboard if (p.dest - floor) * d > 0]
        ahead += [p.source for p in self.waiting if (p.source - floor) * d > 0]
        if not ahead:
            return None
        return min(ahead, key=lambda f: abs(f - floor))

    def project(self, now: int, extra: Passenger | None = None) -> Projection:
        """Predict board/drop-off times if no further requests arrive (optionally adding one).

        Runs the exact same stop logic on a scratch copy, jumping between event floors instead
        of ticking, so the dispatcher's estimate matches what the car will actually do.
        """
        ghost = Elevator(
            id=self.id,
            capacity=self.capacity,
            floor=self.floor,
            direction=self.direction,
            onboard=[Passenger(p.request, p.elevator, p.board_time) for p in self.onboard],
            waiting=[Passenger(p.request, p.elevator) for p in self.waiting],
        )
        if extra is not None:
            ghost.waiting.append(Passenger(extra.request, self.id))
        tracked = ghost.onboard + ghost.waiting
        t = now
        # A full up+down sweep always boards or drops someone, and a sweep visits at most one
        # event floor per tracked passenger, so this bound only trips on logic errors.
        for _ in range(4 * (len(tracked) + 1) ** 2 + 8):
            ghost.service_stop(t)
            if ghost.is_idle or ghost.direction is Direction.IDLE:
                break
            target = ghost._next_event_floor()
            if target is None:
                break
            t += abs(target - ghost.floor)
            ghost.floor = target
        result: Projection = {}
        for p in tracked:
            if p.board_time is None or p.dropoff_time is None:
                raise RuntimeError(f"projection for elevator {self.id} did not finish {p.id}")
            result[p.id] = (p.board_time, p.dropoff_time)
        return result
