"""Time-gated request source: the simulation can only see requests whose time has come."""

from collections.abc import Iterable, Iterator

from elevator_sim.models import Request


class RequestFeed:
    """Releases requests in time order, never handing out one from the future.

    The feed holds at most one not-yet-due request internally (needed to know when to stop
    reading); it is never exposed to the simulation or the dispatcher.
    """

    def __init__(self, requests: Iterable[Request]) -> None:
        self._source: Iterator[Request] = iter(requests)
        self._held: Request | None = None
        self._last_time: int = -1
        self._last_request_time: int = -1
        self._advance()

    def _advance(self) -> None:
        nxt = next(self._source, None)
        if nxt is not None:
            if nxt.time < self._last_request_time:
                raise ValueError(f"requests are not time-sorted: {nxt.id} at t={nxt.time}")
            self._last_request_time = nxt.time
        self._held = nxt

    def release(self, now: int) -> list[Request]:
        """Return every request with ``time <= now`` not yet released."""
        if now < self._last_time:
            raise ValueError("time cannot go backwards")
        self._last_time = now
        due: list[Request] = []
        while self._held is not None and self._held.time <= now:
            due.append(self._held)
            self._advance()
        return due

    @property
    def exhausted(self) -> bool:
        return self._held is None
