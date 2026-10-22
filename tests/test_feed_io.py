from pathlib import Path

import pytest

from elevator_sim.feed import RequestFeed
from elevator_sim.io import read_requests, write_requests
from elevator_sim.models import Request
from elevator_sim.workloads import Pattern, generate


def test_feed_releases_only_due_requests() -> None:
    reqs = [Request(0, "a", 1, 2), Request(0, "b", 1, 3), Request(5, "c", 3, 1)]
    feed = RequestFeed(reqs)
    assert [r.id for r in feed.release(0)] == ["a", "b"]
    assert feed.release(4) == []
    assert not feed.exhausted
    assert [r.id for r in feed.release(5)] == ["c"]
    assert feed.exhausted


def test_feed_rejects_unsorted_input() -> None:
    feed = RequestFeed([Request(5, "a", 1, 2), Request(1, "b", 1, 2)])
    with pytest.raises(ValueError, match="time-sorted"):
        feed.release(5)


def test_feed_rejects_time_going_backwards() -> None:
    feed = RequestFeed([])
    feed.release(3)
    with pytest.raises(ValueError, match="backwards"):
        feed.release(2)


def test_csv_roundtrip_sorts_and_validates(tmp_path: Path) -> None:
    path = tmp_path / "r.csv"
    write_requests(path, [Request(10, "b", 2, 1), Request(0, "a", 1, 2)])
    assert [r.id for r in read_requests(path)] == ["a", "b"]

    path.write_text("time,id,source,dest\n0,a,1,2\n1,a,2,1\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_requests(path)

    path.write_text("t,who,from,to\n")
    with pytest.raises(ValueError, match="header"):
        read_requests(path)

    path.write_text("time,id,source,dest\n1.5,a,1,2\n")
    with pytest.raises(ValueError, match="discrete"):
        read_requests(path)


@pytest.mark.parametrize("pattern", list(Pattern))
def test_workloads_valid_and_seeded(pattern: Pattern) -> None:
    a = generate(pattern, passengers=300, floors=20, duration=100, seed=3)
    assert a == generate(pattern, passengers=300, floors=20, duration=100, seed=3)
    assert len(a) == 300
    assert all(1 <= r.source <= 20 and 1 <= r.dest <= 20 and r.source != r.dest for r in a)
    assert [r.time for r in a] == sorted(r.time for r in a)


def test_up_peak_is_mostly_from_lobby() -> None:
    reqs = generate(Pattern.UP_PEAK, passengers=1000, floors=30, duration=100, seed=1)
    assert sum(r.source == 1 for r in reqs) / len(reqs) > 0.75


def test_two_floor_building_workloads() -> None:
    for pattern in Pattern:
        reqs = generate(pattern, passengers=50, floors=2, duration=10, seed=0)
        assert all({r.source, r.dest} == {1, 2} for r in reqs)
