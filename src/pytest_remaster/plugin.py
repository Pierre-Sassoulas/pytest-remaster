"""Pytest plugin for golden master (characterisation) testing."""

from __future__ import annotations  # pragma: no cover

from collections.abc import Iterator  # pragma: no cover
from typing import TYPE_CHECKING  # pragma: no cover

import pytest  # pragma: no cover

if TYPE_CHECKING:  # pragma: no cover
    from pytest_remaster.golden_master import GoldenMaster


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
    if (cli := request.config.getoption("remaster")) is not None:
        return bool(cli)
    result: bool = request.config.getini("remaster-by-default")
    return result


@pytest.fixture  # pragma: no cover
def golden_master(
    request: pytest.FixtureRequest,  # pragma: no cover
    remaster: bool,  # pylint: disable=redefined-outer-name
) -> Iterator[GoldenMaster]:  # pragma: no cover
    """Golden master comparison fixture.

    Yields a GoldenMaster instance. At teardown, fails if any golden
    masters were updated during the test (remaster mode).
    """
    # pylint: disable-next=import-outside-toplevel
    from pytest_remaster.golden_master import GoldenMaster

    gm = GoldenMaster(remaster=remaster, config=request.config)
    yield gm
    gm.assert_remastered()
