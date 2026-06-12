"""Pytest plugin for golden master (characterisation) testing."""

from __future__ import annotations  # pragma: no cover

from collections.abc import Iterator  # pragma: no cover
from typing import TYPE_CHECKING  # pragma: no cover

import pytest  # pragma: no cover

if TYPE_CHECKING:  # pragma: no cover
    from pytest_remaster.golden_master import GoldenMaster


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover
    config.addinivalue_line(
        "markers",
        "remaster(enabled=True): override the project remaster mode for one"
        " test — remaster(False) pins it strict even when remaster-by-default"
        " is true. An explicit --remaster/--no-remaster on the command line"
        " still wins.",
    )


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
    """Whether tests should regenerate golden master files.

    Resolution: explicit ``--remaster``/``--no-remaster`` on the command
    line, then the ``@pytest.mark.remaster`` marker on the test, then the
    ``remaster-by-default`` ini setting. The CLI wins over the marker so a
    deliberate run can always move (or freeze) every baseline.
    """
    if (cli := request.config.getoption("remaster")) is not None:
        return bool(cli)
    if (marker := request.node.get_closest_marker("remaster")) is not None:
        return bool(marker.args[0]) if marker.args else True
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
