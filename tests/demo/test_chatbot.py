"""Demo test showing pytest-remaster with a fake chatbot."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_remaster import GoldenMaster, discover_test_cases
from tests.demo.chatbot import handle_command

CASES_DIR = Path(__file__).parent / "cases"


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_chatbot_response(case: Path, golden_master: GoldenMaster) -> None:
    cmd = (case / "command").read_text().strip()
    golden_master.check_all(lambda: handle_command(cmd), directory=case)
