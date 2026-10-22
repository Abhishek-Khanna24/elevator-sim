"""Command-line interface: ``elevator-sim run | generate``."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from elevator_sim.dispatch import (
    BruteForceDispatcher,
    Dispatcher,
    NearestDispatcher,
)
from elevator_sim.io import read_requests, write_passengers, write_positions, write_requests
from elevator_sim.models import BuildingConfig
from elevator_sim.simulation import run_simulation
from elevator_sim.stats import format_summary, summarize
from elevator_sim.workloads import Pattern, generate


def cmd_run(args: argparse.Namespace) -> None:
    requests = read_requests(args.requests)
    highest = max((max(r.source, r.dest) for r in requests), default=2)
    building = BuildingConfig(
        floors=args.floors or highest,
        elevators=args.elevators,
        capacity=args.capacity,
        lobby=args.lobby,
    )
    building.validate()
    dispatcher = _dispatcher(args.strategy)
    result = run_simulation(building, dispatcher, requests)
    summary = summarize(result)

    out: Path = args.out
    write_positions(out / "positions.csv", result.positions)
    write_passengers(out / "passengers.csv", result.passengers)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_summary(summary))
        print(f"\nwrote {out}/positions.csv, passengers.csv, summary.json")


def _dispatcher(strategy: str) -> Dispatcher:
    if strategy == "nearest":
        return NearestDispatcher()
    return BruteForceDispatcher()


def cmd_generate(args: argparse.Namespace) -> None:
    requests = generate(
        Pattern(args.pattern),
        passengers=args.passengers,
        floors=args.floors,
        duration=args.duration,
        seed=args.seed,
    )
    write_requests(args.output, requests)
    print(f"wrote {len(requests)} {args.pattern} requests to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="elevator-sim", description="Destination Dispatch elevator system simulator"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="simulate a request CSV and write logs + stats")
    run.add_argument("requests", type=Path, help="CSV with header time,id,source,dest")
    run.add_argument("--floors", type=int, help="number of floors (default: highest in CSV)")
    run.add_argument("--elevators", type=int, default=3, help="number of elevators (default: 3)")
    run.add_argument("--capacity", type=int, default=8, help="max passengers per car (default: 8)")
    run.add_argument("--lobby", type=int, default=1, help="starting floor (default: 1)")
    run.add_argument("--out", type=Path, default=Path("out"), help="output dir (default: out)")
    run.add_argument(
        "--strategy",
        choices=("brute", "nearest"),
        default="brute",
        help="brute or nearest (default: brute)",
    )
    run.add_argument("--json", action="store_true", help="print the summary as JSON")
    run.set_defaults(func=cmd_run)

    gen = sub.add_parser("generate", help="write a synthetic request CSV")
    gen.add_argument("--pattern", choices=[p.value for p in Pattern], default=Pattern.UNIFORM)
    gen.add_argument("--passengers", type=int, default=200)
    gen.add_argument("--floors", type=int, default=50)
    gen.add_argument("--duration", type=int, default=600, help="arrival window in ticks")
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("-o", "--output", type=Path, required=True)
    gen.set_defaults(func=cmd_generate)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
