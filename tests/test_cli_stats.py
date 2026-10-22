import json
from pathlib import Path

import pytest

from elevator_sim.cli import main
from elevator_sim.stats import describe

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_describe() -> None:
    assert describe([]) == {}
    assert describe([4]) == {"min": 4, "max": 4, "mean": 4, "median": 4, "p95": 4, "stdev": 0}
    stats = describe(list(range(1, 101)))
    assert (stats["min"], stats["max"], stats["mean"]) == (1, 100, 50.5)
    assert stats["p95"] == pytest.approx(95.05)


def test_run_writes_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", str(EXAMPLES / "sample.csv"), "--elevators", "1", "--out", str(tmp_path)])
    positions = (tmp_path / "positions.csv").read_text().splitlines()
    assert positions[0] == "time,e0"
    assert positions[1] == "0,1"
    assert len(positions) == 102
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["wait_time"]["max"] == 71
    assert summary["total_time"]["min"] == 36
    assert summary["observations"]
    passengers = (tmp_path / "passengers.csv").read_text().splitlines()
    assert passengers[1].startswith("passenger1,0,1,51,0,0,50,0,50,50")
    assert "passengers=3" in capsys.readouterr().out


def test_run_defaults_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", str(EXAMPLES / "sample.csv"), "--out", str(tmp_path), "--json"])
    summary = json.loads(capsys.readouterr().out)
    assert summary["building"] == {"floors": 51, "elevators": 3, "capacity": 8}
    assert summary["passengers"] == 3


def test_generate(tmp_path: Path) -> None:
    out = tmp_path / "w.csv"
    main(["generate", "--pattern", "lunch", "--passengers", "25", "-o", str(out)])
    assert len(out.read_text().splitlines()) == 26


def test_bad_input_exits_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("time,id,source,dest\n0,a,3,3\n")
    with pytest.raises(SystemExit) as exc:
        main(["run", str(bad), "--out", str(tmp_path)])
    assert exc.value.code == 2
