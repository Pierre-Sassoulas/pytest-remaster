"""Demo test showing pytest-remaster with stdout, stderr, and caplog capture."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from pytest_remaster import CaseData, GoldenMaster, discover_test_cases
from tests.demo_subprocess.cli import main

CASES_DIR = Path(__file__).parent / "cases"


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_cli(
    case: CaseData,
    golden_master: GoldenMaster,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    def run(case: CaseData) -> tuple[str, str, str]:
        config = json.loads((case.input / "input.json").read_text())
        log_level_str = config.get("log_level", "DEBUG")
        with caplog.at_level(getattr(logging, log_level_str)):
            main(config["command"].split())
        captured = capsys.readouterr()
        return (
            captured.out,
            captured.err,
            "\n".join(f"{r.levelname}: {r.message}" for r in caplog.records),
        )

    golden_master.check_each(
        case,
        runner=run,
        extractors={
            ".stdout": lambda r: r[0],
            ".stderr": lambda r: r[1],
            ".log": lambda r: r[2],
        },
    )
