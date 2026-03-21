"""Pytest plugin for golden master testing with automatic regeneration."""

from __future__ import annotations  # pragma: no cover

from typing import TYPE_CHECKING  # pragma: no cover

import pytest  # pragma: no cover

if TYPE_CHECKING:  # pragma: no cover
    from pytest_remaster.core import GoldenMaster


def pytest_addoption(parser: pytest.Parser) -> None:  # pragma: no cover
    group = parser.getgroup(
        "remaster", "Golden master testing with automatic regeneration"
    )
    group.addoption(
        "--remaster",
        action="store_true",
        dest="remaster",
        default=None,
        help="Regenerate golden master files when comparison fails.",
    )
    group.addoption(
        "--no-remaster",
        action="store_false",
        dest="remaster",
        help="Compare against golden master files without regenerating.",
    )
    parser.addini(
        "remaster-by-default",
        type="bool",
        default=True,
        help="Whether to regenerate golden master files by default (default: True).",
    )


@pytest.fixture  # pragma: no cover
def remaster(request: pytest.FixtureRequest) -> bool:  # pragma: no cover
    """Whether tests should regenerate golden master files."""
    cli: bool | None = request.config.getoption("remaster")
    if cli is not None:
        return cli
    result: bool = request.config.getini("remaster-by-default")
    return result


@pytest.fixture  # pragma: no cover
def golden_master(remaster: bool) -> GoldenMaster:  # pragma: no cover
    """Golden master comparison fixture."""
    from pytest_remaster.core import GoldenMaster

    return GoldenMaster(remaster=remaster)
