"""Demo: astroid functional tests with the expectations written in the source.

Each ``.py`` file under ``cases`` is parsed by astroid. A comment at the end
of a line says what astroid must infer for the statement on that line:

- ``# inferred: Const(5)`` — the type and the value
- ``# inferred-type: Const`` — the type only
- ``# inferred-value: 5`` — the value only

Several results are separated by ``|``. ``check_inline`` compares each
comment with the actual inference and rewrites it on ``--remaster``, so a
new expectation is added by writing ``# inferred:`` and running the tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pytest_remaster import CaseData, GoldenMaster, InlineLine, discover_test_files

astroid = pytest.importorskip("astroid")

CASES_DIR = Path(__file__).parent / "cases"


def _node_on_line(module: Any, line: InlineLine) -> Any:
    """Return the node the comment of *line* is about.

    That is the statement starting on the line; for an expression, an
    assignment or a ``return``, the value of the statement.
    """
    statements = (
        node
        for node in module.nodes_of_class(astroid.nodes.NodeNG)
        if node.is_statement and node.lineno == line.lineno
    )
    if (statement := next(statements, None)) is None:
        pytest.fail(f"{line.path}:{line.lineno}: no statement starts on this line")
    return getattr(statement, "value", None) or statement


def _infer(node: Any) -> list[Any]:
    try:
        return list(node.infer())
    except astroid.InferenceError:
        return []


def _type(inferred: Any) -> str:
    if isinstance(inferred, astroid.util.UninferableBase):
        return "Uninferable"
    return type(inferred).__name__


def _value(inferred: Any) -> str:
    if isinstance(inferred, astroid.util.UninferableBase):
        return "Uninferable"
    if isinstance(inferred, astroid.nodes.Const):
        return repr(inferred.value)
    if isinstance(inferred, astroid.nodes.BaseContainer):
        return str(inferred.as_string())
    if isinstance(inferred, astroid.Instance):
        return str(inferred.pytype())
    if hasattr(inferred, "qname"):
        return str(inferred.qname())
    return str(inferred.as_string())


def _each(describe: Any) -> Any:
    """Describe every inferred result, ``InferenceError`` when there is none."""
    return lambda results: (
        " | ".join(describe(result) for result in results) or "InferenceError"
    )


EXTRACTORS = {
    "inferred": _each(lambda inferred: f"{_type(inferred)}({_value(inferred)})"),
    "inferred-type": _each(_type),
    "inferred-value": _each(_value),
}


@pytest.mark.parametrize("case", discover_test_files(CASES_DIR, "*.py"))
def test_inference(case: CaseData, golden_master: GoldenMaster) -> None:
    module = astroid.parse(
        case.input.read_text(encoding="utf-8"), module_name=case.input.stem
    )
    golden_master.check_inline(
        case.input, EXTRACTORS, runner=lambda line: _infer(_node_on_line(module, line))
    )
