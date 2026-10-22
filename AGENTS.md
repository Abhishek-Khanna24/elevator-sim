# Working on elevator-sim

Discrete-time Destination Dispatch simulator. One tick is one floor of travel. A passenger names origin and destination up front, is assigned to one car immediately, and cannot change that assignment. The runtime is the Python standard library plus Pydantic.

## Layout

- `src/elevator_sim/models.py` — `Request`, `Passenger`, `BuildingConfig`, `Direction`. Time and floors are `int`.
- `src/elevator_sim/feed.py` — releases a request only when `time <= now`. The scheduler never sees future demand.
- `src/elevator_sim/elevator.py` — one car. LOOK movement, capacity, direction-aware boarding. `project` predicts board and drop-off times.
- `src/elevator_sim/simulation.py` — the tick loop. Each tick: release and assign, service the stop, log the floor, then move one floor.
- `src/elevator_sim/dispatch/` — `Dispatcher` protocol. `brute` (default) minimizes added passenger time. `nearest` minimizes floors to the pickup.
- `src/elevator_sim/io.py`, `stats.py`, `workloads.py`, `cli.py` — CSV, summary stats, synthetic traffic, and the `elevator-sim` command.
- `tests/` — pytest. `examples/` — sample and generated request CSVs.

Keep a new scheduler behind `Dispatcher`: a `name: str` and `assign(request, elevators, now) -> int` that returns a car id. Register it in `dispatch/__init__.py` and on `--strategy` in `cli.py`.

## How to write code

Work test-first, and keep each rule in one place.

- **TDD.** Write a failing test that states the behavior, then the code that makes it pass, then remove duplication. A bug fix starts with a test that fails on the current code.
- **DRY.** One implementation of each rule. Share a helper for validation, scoring, or a CSV field list instead of copying it into a second module.
- **Pydantic.** Model data that enters the program with Pydantic: requests, building config, and parsed CSV rows. Use a frozen model (`model_config = ConfigDict(frozen=True)`) for a value that must not change after it is built. Validate there, and let Pydantic raise on bad input. A car mid-run can stay a `dataclass(slots=True)` because its floor and passengers change every tick.
- Python 3.14. Use `list[int]`, `int | None`, `type Floor = int`, and `match`. Do not add `from __future__ import annotations`.
- Use `collections.abc` (`Sequence`, `Iterable`, `Iterator`) and `enum.IntEnum` / `StrEnum`.
- Import order is stdlib, third party, then `elevator_sim`. Ruff enforces this.
- A module gets a one-line docstring. A function gets a docstring when the name does not already say what it does. Comments explain why, not what the next line does.
- Raise `ValueError` with a specific message for bad input (floors, capacity, duplicate ids, unsorted feed). The CLI prints `error: ...` to stderr and exits 2.
- Boarding and alighting take zero ticks. Only travel costs a tick. Assignments are final.
- Do not read requests ahead of the current tick. Go through `RequestFeed`.
- Pydantic is the runtime dependency. Dev tools stay in the `dev` dependency group.
- When behavior or CLI flags change, update `README.md` and the tests that lock the old numbers.

## Style

Ruff and mypy are the style guide. Match the surrounding file.

- Line length 100. Target `py314`.
- Ruff selects `E`, `F`, `W`, `I`, `B`, `UP`, `SIM`, `RUF`, `PL`, `C4`, `PT`. It ignores `PLR0913`, `PLR2004`, `PLR0912`, `PLR0911`.
- Mypy is strict on `src` and `tests`.
- Tests are functions named `test_*`, with a return type of `None`. Call `main([...])` instead of spawning a process. Use `tmp_path` for output. Use `pytest.raises(ValueError, match=...)` for rejected input.
- Property tests live in `tests/test_invariants.py`. The default Hypothesis profile draws 60 examples. `HYPOTHESIS_PROFILE=thorough` draws 2000.
- Hand-checked timings live in `tests/test_scenarios.py`. A one-car scenario is the easiest place to see LOOK behavior.

```bash
uv run ruff check && uv run ruff format
uv run mypy
uv run pytest
```

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, `mypy`, and `pytest` on every push to `main` and every pull request. A change is done when those four pass locally.

## How to debug

Reproduce with the smallest input before changing the scheduler.

```bash
uv run elevator-sim run examples/sample.csv --elevators 1 --out out --json
uv run pytest tests/test_scenarios.py::test_spec_sample_single_elevator -q
```

- One car, one or two passengers: the position log in `out/positions.csv` is the trace. Row `t` is the floor at tick `t`. `passengers.csv` has board, drop-off, wait, and travel.
- Wrong car chosen: call `assign` directly with a couple of `Elevator`s, the way `tests/test_brute.py` and `tests/test_nearest.py` do. `brute` scores `Elevator.project`. `nearest` scores floors to the pickup.
- A prediction disagrees with the run: `tests/test_invariants.py::test_projection_matches_real_ticks` compares `project` with tick-by-tick `service_stop` / `move`.
- A passenger waits forever: the feed must be exhausted and every passenger delivered. The loop raises after 10 million ticks.
- Stats look wrong: `summarize` only reads `SimulationResult`. Check board and drop-off times first. Wait is `board - request`, travel is `dropoff - board`.

`out/` is gitignored. Delete it freely.

## uv

[uv](https://docs.astral.sh/uv/) installs Python and runs the project. `.python-version` is `3.14`. `requires-python` is `>=3.14`.

Every package is frozen. `uv.lock` is the exact set of versions that install. Add a package with `uv add` (or `uv add --dev` for a tool) so the lockfile records that version. Then commit `pyproject.toml` and `uv.lock` together. Do not hand-edit the lockfile.

```bash
uv sync --frozen         # install exactly uv.lock, including the dev group
uv run elevator-sim ...  # run the CLI in that environment
uv run pytest            # same for tests, ruff, and mypy
uv lock                  # refresh uv.lock after a dependency change
```

`uv sync --frozen` fails when `pyproject.toml` and `uv.lock` disagree. CI uses the same frozen install (`uv sync --locked --all-groups`).

## Pre-commit

`.pre-commit-config.yaml` runs Ruff on each commit. Install the hook once with `uv run pre-commit install`. Do not skip it.

The hook runs:

- `uv run ruff check`
- `uv run ruff format --check`

Fix a failure with `uv run ruff check --fix` and `uv run ruff format`, then commit again.

## GitHub

`origin` is `https://github.com/Abhishek-Khanna24/elevator-sim`. `main` tracks `origin/main`.

- Commit only when asked. The message says why, in a sentence or two.
- Do not force-push `main`, skip hooks, or change git config.
- Push and open a pull request only when asked. CI must be green before merging.
- Keep generated output (`out/`), caches, and `.venv/` untracked. They are already in `.gitignore`.
- When a package is added or bumped, the frozen `uv.lock` goes in the same commit as `pyproject.toml`.

## Pull requests

Open a pull request only when asked. Target `main`. GitHub starts the description from `.github/pull_request_template.md`. Fill every section. Leave the checklist boxes unchecked until that command has been run.

1. Branch from up-to-date `main`.
2. Commit on that branch. The pre-commit hook runs Ruff.
3. Push with `git push -u origin HEAD`.
4. Create the pull request with `gh pr create`. The body is the template:
   - **Summary:** one to three bullets on why the change exists.
   - **Test plan:** the ruff, mypy, and pytest commands, plus any scenario checked by hand (sample CSV, one car, or a scheduler change).
5. Wait until the CI job `check` is green. It runs `uv sync --locked`, Ruff, mypy, and pytest.
6. Merge only when asked.
