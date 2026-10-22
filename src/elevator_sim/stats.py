"""Summary statistics and auto-generated observations."""

import statistics
from collections.abc import Sequence
from typing import Any

from elevator_sim.models import Direction
from elevator_sim.simulation import SimulationResult


def describe(values: Sequence[int]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    p95 = (
        statistics.quantiles(ordered, n=20, method="inclusive")[18]
        if len(ordered) > 1
        else ordered[0]
    )
    return {
        "min": ordered[0],
        "max": ordered[-1],
        "mean": round(statistics.fmean(ordered), 2),
        "median": statistics.median(ordered),
        "p95": round(p95, 2),
        "stdev": round(statistics.pstdev(ordered), 2),
    }


def summarize(result: SimulationResult) -> dict[str, Any]:
    passengers = result.passengers
    waits = [p.wait_time for p in passengers]
    travels = [p.travel_time for p in passengers]
    totals = [p.total_time for p in passengers]
    ticks = max(result.makespan, 1)

    by_direction: dict[str, dict[str, float]] = {}
    for direction in (Direction.UP, Direction.DOWN):
        subset = [p.wait_time for p in passengers if p.direction is direction]
        if subset:
            by_direction[direction.name.lower()] = {
                "count": len(subset),
                "mean_wait": round(statistics.fmean(subset), 2),
                "max_wait": max(subset),
            }

    elevators = [
        {
            "id": car.id,
            "passengers": car.passengers_served,
            "floors_traveled": car.floors_traveled,
            "stops": car.stops,
            "idle_ticks": car.idle_ticks,
            "peak_load": car.peak_load,
            "utilization": round(car.floors_traveled / ticks, 3),
        }
        for car in result.elevators
    ]

    summary: dict[str, Any] = {
        "strategy": result.strategy,
        "building": {
            "floors": result.building.floors,
            "elevators": result.building.elevators,
            "capacity": result.building.capacity,
        },
        "passengers": len(passengers),
        "makespan": result.makespan,
        "wait_time": describe(waits),
        "travel_time": describe(travels),
        "total_time": describe(totals),
        "by_direction": by_direction,
        "elevators": elevators,
    }
    summary["observations"] = observations(summary)
    return summary


def observations(summary: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not summary["passengers"]:
        return ["No passengers were simulated."]

    wait, total = summary["wait_time"], summary["total_time"]
    if wait["mean"] > 0:
        ratio = round(wait["max"] / wait["mean"], 1)
        notes.append(
            f"Worst-case wait is {ratio}x the mean (p95 {wait['p95']}, max {wait['max']}): "
            + ("a long tail." if ratio >= 3 else "fairly even service.")
        )
    if total["mean"] > 0:
        share = wait["mean"] / total["mean"]
        notes.append(f"Waiting is {share:.0%} of the average trip; riding is the rest.")

    dirs = summary["by_direction"]
    if "up" in dirs and "down" in dirs:
        up, down = dirs["up"]["mean_wait"], dirs["down"]["mean_wait"]
        slower = "down" if down > up else "up"
        notes.append(f"Mean wait up={up}, down={down}; {slower}-bound callers wait longer.")

    cars = summary["elevators"]
    served = [c["passengers"] for c in cars]
    if len(cars) > 1 and sum(served):
        busiest = max(cars, key=lambda c: c["passengers"])
        notes.append(
            f"Elevator {busiest['id']} carried {busiest['passengers'] / sum(served):.0%} of "
            f"passengers (even split would be {1 / len(cars):.0%})."
        )
    idle = statistics.fmean(c["idle_ticks"] for c in cars) / max(summary["makespan"], 1)
    notes.append(f"Cars were idle {idle:.0%} of the time on average.")
    return notes


def format_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"passengers={summary['passengers']}  makespan={summary['makespan']}",
    ]
    for key in ("wait_time", "travel_time", "total_time"):
        stats = summary[key]
        if stats:
            body = "  ".join(f"{k}={v}" for k, v in stats.items())
            lines.append(f"  {key:<12} {body}")
    lines.append("  elevators:")
    for car in summary["elevators"]:
        lines.append(
            f"    e{car['id']}: passengers={car['passengers']} "
            f"floors={car['floors_traveled']} stops={car['stops']} "
            f"idle={car['idle_ticks']} peak_load={car['peak_load']}"
        )
    lines.append("  observations:")
    lines.extend(f"    - {note}" for note in summary["observations"])
    return "\n".join(lines)
