"""Demo test showing pytest-remaster with a fake chatbot."""

from __future__ import annotations

import pytest

from pytest_remaster import (
    CaseData,
    FilePatchRegistry,
    GoldenMaster,
    discover_test_cases,
)
from tests.demo.chatbot import handle_command

CASES_DIR = __file__.replace("test_chatbot.py", "cases")

patcher = FilePatchRegistry()
patcher.register(
    "user_status.json",
    target="tests.demo.chatbot.get_user_status",
    default="offline",
)


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
@patcher.use
def test_chatbot_response(case: CaseData, golden_master: GoldenMaster) -> None:
    cmd = (case.input / "command").read_text().strip()
    golden_master.check_all(lambda: handle_command(cmd), case.input)
