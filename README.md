# elevator-sim

A discrete-time simulator of a **Destination Dispatch** elevator system. Passengers state their
origin and destination when they call, the controller immediately (and irrevocably) assigns them
to a car, and the simulation ticks forward one floor-of-travel at a time until everyone has
been delivered.

- Configurable number of floors, elevators, and maximum passengers per elevator.
- A scheduler that assigns each passenger to the car that adds the least total passenger time.
- Outputs a per-tick elevator position log, per-passenger timings, and summary statistics with
  auto-generated observations.
- Pure standard library at runtime; Python 3.14, managed with [uv](https://docs.astral.sh/uv/).

## How to run

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) (it will download
Python 3.14 automatically).

```bash
uv sync                                   # create .venv with Python 3.14 + dev tools

# Simulate the spec's sample input with 3 cars on a 60-floor building
uv run elevator-sim run examples/sample.csv --floors 60 --elevators 3 --capacity 8
#   -> out/positions.csv, out/passengers.csv, out/summary.json (+ summary on stdout)

# Generate synthetic traffic: uniform | up-peak | down-peak | lunch
uv run elevator-sim generate --pattern up-peak --passengers 400 --floors 50 \
    --duration 600 --seed 7 -o examples/up_peak.csv
```

`run` options: `--floors` (default: highest floor in the CSV), `--elevators` (default 3),
`--capacity` (default 8), `--lobby` (start floor, default 1), `--strategy` (`brute` or
`nearest`, default `brute`), `--out DIR`, `--json`.

### Input

```csv
time,id,source,dest
0,passenger1,1,51
0,passenger2,1,37
10,passenger3,20,1
```

### Output

- `positions.csv`: one row per tick starting at `t=0`: `time,e0,e1,...` (floor of each car).
- `passengers.csv`: `id, request_time, source, dest, elevator, board_time, dropoff_time,
  wait_time, travel_time, total_time`.
- `summary.json` / stdout: min, max, mean, median, p95, stdev of wait, travel and total time;
  up- vs down-bound waits; per-car passengers, floors travelled, stops, idle ticks and peak
  load; plus plain-English observations (tail length, load balance, idle share...).

### Development

```bash
uv run pytest                                  # 39 tests, ~3s
HYPOTHESIS_PROFILE=thorough uv run pytest      # 2000 random scenarios per property
uv run ruff check && uv run ruff format --check
uv run mypy                                    # strict
```

CI (`.github/workflows/ci.yml`) runs all of the above on every push and pull request.

## How it works

### Time model

Each tick `t`:

1. **Release** requests with `time <= t` from the feed and **assign** each to one car.
2. Each car **unloads** riders whose destination is this floor, picks its direction (LOOK),
   then **boards** waiting passengers assigned to it at this floor who are going that way
   (oldest first, up to capacity).
3. **Log** every car's floor for time `t`.
4. Each car **moves** one floor (or stays idle). `t += 1`.

The loop always advances one unit at a time, including through gaps in the input, and stops at
the tick the last passenger steps out. `wait = board - request`, `travel = dropoff - board`.

**No peeking ahead:** requests come from a `RequestFeed` that only hands out requests whose time
has arrived. The scheduler never sees future demand (a property test checks this).

### Car behaviour (LOOK)

A car keeps moving in its current direction while it has drop-offs or pickups ahead, reverses
when it has none, and idles when it has no work. A waiting passenger only boards if they want to
go the same way the car is heading (or the car is idle/turning around at their floor). An idle
car heads for its oldest waiting passenger.

### Scheduler

The default scheduler (`brute`) tries every car. For each one it replays that car's LOOK route
with the new passenger added and counts:

```
extra = ticks until the new passenger steps off
      + ticks everyone already assigned to that car is delayed
```

The smallest extra wins (ties go to the lowest id). That extra is the increase in total
passenger time, which is objective 2. There are no weights and no load penalty.

`--strategy nearest` instead sends the call to the car that reaches the caller in the fewest
floors, and does not count delays to anyone else.

The route replay (`Elevator.project`) reuses the exact stop logic the real car runs, jumping
between "event floors" instead of ticking. A property test checks that its predicted board and
drop-off times match tick-by-tick execution exactly.

## Results

Four 400-passenger workloads (seed 7) with the default `brute` scheduler, 50 floors, 4 cars,
capacity 10, arrivals spread over 600 ticks (times in ticks):

| workload                         | avg wait | p95 wait | max wait | avg total | p95 total | max total | last delivery |
|----------------------------------|----------|----------|----------|-----------|-----------|-----------|---------------|
| lunch (40% from / 40% to lobby)  | 14.24    | 32.05    | 63       | 36.99     | 67.0      | 85        | 669           |
| uniform                          | 19.69    | 50.05    | 63       | 37.31     | 73.0      | 93        | 666           |
| down-peak (85% to lobby)         | 25.63    | 56.0     | 121      | 49.45     | 93.0      | 159       | 731           |
| up-peak (85% from lobby)         | 86.52    | 179.0    | 194      | 110.34    | 207.0     | 241       | 832           |

Observations:

- **Waiting is where the variation is.** Ride time is bounded by building height (at most 49
  ticks here), so differences in total time come almost entirely from waiting.
- **Up-peak overloads the building.** Arrivals stop at t=600 but the last delivery is at t=832:
  four cars of 10 can't clear the lobby queue as fast as it forms, so waits keep growing for
  the whole burst. The same volume in down-peak finishes 101 ticks sooner with about a third
  of the average wait.
- **Tails are long.** At down-peak the max wait is 4.7x the mean. A caller whose assigned car
  has just passed them going the other way must wait for it to finish its sweep and come back.
- **Load spreads evenly.** On lunch traffic the busiest car carried 28% of passengers (even
  split 25%) and cars were idle only 5% of the time.

## Assumptions and simplifications

- **Floors are numbered 1..N**; all cars start at the lobby (floor 1 by default).
- **Boarding and alighting take zero ticks**: a car can stop, exchange passengers and leave in
  the same tick. Only travel costs time (1 floor = 1 tick); no acceleration or door dwell.
- **Assignments are final**, as the spec requires. A passenger left behind because their car
  was full keeps waiting for the same car, which LOOK guarantees will come back.
- **Same-tick ordering:** requests released at `t` are assigned before cars act at `t`, so a car
  already at the caller's floor picks them up with zero wait.
- **Direction rule:** passengers only board a car heading their way; a car never takes a
  detour with someone on board.
- **Every car serves every floor.**
- **Unsorted input** is sorted by time on load; duplicate IDs, out-of-range floors and
  `source == dest` are rejected.
- **"Serve everyone eventually"** holds for any finite input: LOOK sweeps always reach every
  assigned pickup, and once arrivals stop, each sweep delivers someone. Under endless overload
  a passenger could in principle keep finding their car full; counting the delay to people
  already on that car makes a crowded car expensive, so that is unlikely.
