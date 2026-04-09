"""Demo: pylint-like functional tests with version-specific expected output.

Mirrors how pylint's functional tests work:
- A ``.py`` source file is analysed by pylint with a custom plugin
- Expected output lives alongside it with dimension-based overrides
  (e.g. ``simple_module.311.linux.txt`` for Python 3.11 on Linux)
- ``dimensions`` on ``check()`` lets pytest-remaster resolve the right
  file, remaster to the most specific override, and deduplicate
  redundant files automatically
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_remaster import CaseData, GoldenMaster, discover_test_files

CASES_DIR = Path(__file__).parent / "cases"
PLUGIN_DIR = str(Path(__file__).parent)
MSG_TEMPLATE = "{symbol}:{line}:{column}:{end_line}:{end_column}:{msg}"


def _run_pylint(source: Path, py_version: str) -> str:
    """Run pylint on *source* with the given ``--py-version``.

    Return the sorted message lines.
    """
    env = {**__import__("os").environ, "PYTHONPATH": PLUGIN_DIR}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pylint",
            str(source),
            f"--py-version={py_version}",
            "--rcfile=/dev/null",
            "--score=no",
            "--disable=all",
            "--load-plugins=platform_checker",
            "--enable=platform-info",
            f"--msg-template={MSG_TEMPLATE}",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    lines = [
        line
        for line in result.stdout.splitlines()
        if line and not line.startswith("*") and not line.startswith("-")
    ]
    return "\n".join(sorted(lines))


@pytest.fixture()
def cases(tmp_path: Path) -> Path:
    """Copy case fixtures to a temporary directory.

    Ensures remaster never touches the repository files.
    """
    dest = tmp_path / "cases"
    shutil.copytree(CASES_DIR, dest)
    return dest


@pytest.mark.parametrize("case", discover_test_files(CASES_DIR, "*.py"))
@pytest.mark.parametrize("py_version", ["3.11", "3.12", "3.13", "3.14"])
def test_pylint_functional_tests(  # pylint: disable=redefined-outer-name
    cases: Path, golden_master: GoldenMaster, case: CaseData, py_version: str
) -> None:
    source = cases / case.input.name
    actual = _run_pylint(source, py_version)
    base = source.with_suffix(".txt")
    golden_master.check(
        actual,
        base,
        dimensions={"version": py_version.replace(".", ""), "platform": sys.platform},
    )
