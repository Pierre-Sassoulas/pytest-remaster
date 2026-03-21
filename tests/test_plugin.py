"""Basic tests for the pytest-remaster plugin."""

from __future__ import annotations

import pytest


def test_remaster_option_default(pytester: pytest.Pytester) -> None:
    """The --remaster CLI option defaults to None (falls back to ini)."""
    pytester.makepyfile(
        """
        def test_default(pytestconfig):
            assert pytestconfig.getoption("remaster") is None
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_remaster_ini_default(pytester: pytest.Pytester) -> None:
    """The remaster-by-default ini option defaults to True."""
    pytester.makepyfile(
        """
        def test_ini(pytestconfig):
            assert pytestconfig.getini("remaster-by-default") is True
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_remaster_flag_enables(pytester: pytest.Pytester) -> None:
    """Passing --remaster sets the option to True."""
    pytester.makepyfile(
        """
        def test_flag(pytestconfig):
            assert pytestconfig.getoption("remaster") is True
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1)


def test_no_remaster_flag_disables(pytester: pytest.Pytester) -> None:
    """Passing --no-remaster sets the option to False."""
    pytester.makepyfile(
        """
        def test_flag(pytestconfig):
            assert pytestconfig.getoption("remaster") is False
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_remaster_fixture(pytester: pytest.Pytester) -> None:
    """The remaster fixture resolves CLI > ini correctly."""
    pytester.makepyfile(
        """
        def test_fixture_default(remaster):
            assert remaster is True
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_remaster_fixture_no_remaster(pytester: pytest.Pytester) -> None:
    """The remaster fixture returns False with --no-remaster."""
    pytester.makepyfile(
        """
        def test_fixture_off(remaster):
            assert remaster is False
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_remaster_ini_override(pytester: pytest.Pytester) -> None:
    """Setting remaster-by-default=false in ini changes the default."""
    pytester.makeini(
        """
        [pytest]
        remaster-by-default = false
        """
    )
    pytester.makepyfile(
        """
        def test_fixture_ini_false(remaster):
            assert remaster is False
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
