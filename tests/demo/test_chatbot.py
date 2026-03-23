"""Demo test showing pytest-remaster with a fake chatbot."""

from __future__ import annotations

import pytest

from pytest_remaster import (
    CaseData,
    GoldenMaster,
    PatchRegistry,
    discover_test_cases,
)
from tests.demo.chatbot import handle_command

CASES_DIR = __file__.replace("test_chatbot.py", "cases")

patcher = PatchRegistry()
patcher.add_file_patch(
    "user_status.json",
    target="tests.demo.chatbot.get_user_status",
    default="offline",
)


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_chatbot_response(case: CaseData, golden_master: GoldenMaster) -> None:
    with patcher.mock(case):
        cmd = (case.input / "command").read_text().strip()
        golden_master.check_all(lambda: handle_command(cmd), case.input)
