"""Demo: pylint-like functional tests with version-specific expected output.

Mirrors how pylint's functional tests work:
- A ``.py`` source file is analysed by pylint
- Expected output lives alongside it (``pep695.txt``)
- A version-specific override (``pep695.311.txt``) captures output that
  differs when targeting an older ``--py-version``

``override_path`` lets pytest-remaster compare against the right file and
remaster to the version-specific override without touching the generic base.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_remaster import GoldenMaster

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


@pytest.mark.parametrize("py_version", ["3.11", "3.12", "3.13", "3.14"])
def test_pylint_functional_tests(  # pylint: disable=redefined-outer-name
    cases: Path, golden_master: GoldenMaster, py_version: str
) -> None:
    source = cases / "simple_module.py"
    actual = _run_pylint(source, py_version)

    ver = py_version.replace(".", "")
    base = source.with_suffix(".txt")
    override = base.parent / f"{source.stem}.{ver}.txt"

    golden_master.check(actual, base, override_path=override)
