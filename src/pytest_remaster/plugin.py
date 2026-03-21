"""Pytest plugin for golden master testing with automatic regeneration."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("remaster", "Golden master testing")
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


@pytest.fixture
def remaster(request: pytest.FixtureRequest) -> bool:
    """Whether tests should regenerate golden master files."""
    cli = request.config.getoption("remaster")
    if cli is not None:
        return cli
    return request.config.getini("remaster-by-default")
