"""Basic tests for the pytest-remaster plugin."""

from __future__ import annotations


def test_remaster_option(pytestconfig):
    """The --remaster option is registered and defaults to False."""
    assert pytestconfig.getoption("--remaster") is False
