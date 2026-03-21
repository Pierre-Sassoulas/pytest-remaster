"""Pytest plugin for golden master testing with automatic regeneration."""

from __future__ import annotations  # pragma: no cover

import pytest  # pragma: no cover


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
    cli = request.config.getoption("remaster")
    if cli is not None:
        return cli
    return request.config.getini("remaster-by-default")
