"""Tests for placeholders: dynamic values stored as ``{{ name }}``."""

from __future__ import annotations

import pytest

TEST_BASKET = """
    from pathlib import Path

    HERE = Path(__file__).parent

    def test_basket(golden_master):
        golden_master.check(
            f"apples are in {HERE}/basket",
            HERE / "expected.txt",
            placeholders={"here": str(HERE)},
        )
    """


def test_remaster_writes_the_placeholder(pytester: pytest.Pytester) -> None:
    """The dynamic value never reaches the expected file."""
    pytester.makepyfile(TEST_BASKET)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    expected = pytester.path / "expected.txt"
    assert expected.read_text() == "apples are in {{ here }}/basket\n"
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_placeholder_matches_any_current_value(pytester: pytest.Pytester) -> None:
    """A file written elsewhere passes here."""
    (pytester.path / "expected.txt").write_text("apples are in {{ here }}/basket\n")
    pytester.makepyfile(TEST_BASKET)
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_hardcoded_dynamic_value_is_a_mismatch(pytester: pytest.Pytester) -> None:
    """A file holding the raw value would only pass on one machine."""
    (pytester.path / "expected.txt").write_text(
        f"apples are in {pytester.path}/basket\n"
    )
    pytester.makepyfile(TEST_BASKET)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*+apples are in {{ here }}/basket"])


def test_longest_value_wins(pytester: pytest.Pytester) -> None:
    """A directory inside another one is not cut in two."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_basket(golden_master):
            golden_master.check(
                "/home/cat/garden/apple and /home/cat/ball",
                Path(__file__).parent / "expected.txt",
                placeholders={"home": "/home/cat", "garden": "/home/cat/garden"},
            )
        """
    )
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    expected = pytester.path / "expected.txt"
    assert expected.read_text() == "{{ garden }}/apple and {{ home }}/ball\n"


def test_matcher_gets_the_current_value(pytester: pytest.Pytester) -> None:
    """The matcher compares real values, not markers."""
    (pytester.path / "expected.json").write_text('{"apples": 3, "dir": "{{ here }}"}')
    pytester.makepyfile(
        """
        import json
        from pathlib import Path

        HERE = Path(__file__).parent
        SEEN = []

        def same(actual, expected):
            SEEN.append(expected)
            return actual == expected

        def test_basket(golden_master):
            golden_master.check(
                {"dir": str(HERE), "apples": 3},
                HERE / "expected.json",
                serializer=json.dumps,
                deserializer=json.loads,
                matcher=same,
                placeholders={"here": str(HERE)},
            )
            assert SEEN == [{"dir": str(HERE), "apples": 3}]
        """
    )
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_placeholders_in_check_all_and_check_each(pytester: pytest.Pytester) -> None:
    """The other check methods hand the placeholders down."""
    (pytester.path / "case").mkdir()
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import CaseData

        CASE = Path(__file__).parent / "case"

        def test_basket(golden_master):
            names = {"case": str(CASE)}
            golden_master.check_all([f"{CASE}/apple"], CASE, placeholders=names)
            golden_master.check_each(
                CaseData(CASE),
                runner=lambda case: f"{case.input}/banana",
                extractors={".txt": str},
                placeholders=names,
            )
        """
    )
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    case = pytester.path / "case"
    assert (case / "expected_0").read_text() == "{{ case }}/apple\n"
    assert (case / "expected.txt").read_text() == "{{ case }}/banana\n"


def test_placeholders_in_check_inline(pytester: pytest.Pytester) -> None:
    """Inline expectations hide dynamic values too."""
    fruits = pytester.path / "fruits.txt"
    fruits.write_text("apple  # where:\n")
    pytester.makepyfile(
        """
        from pathlib import Path

        HERE = Path(__file__).parent

        def test_fruits(golden_master):
            golden_master.check_inline(
                HERE / "fruits.txt",
                {"where": lambda line: f"{HERE}/{line.code}"},
                placeholders={"here": str(HERE)},
            )
        """
    )
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert fruits.read_text() == "apple  # where: {{ here }}/apple\n"
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_empty_placeholder_value_is_an_error(pytester: pytest.Pytester) -> None:
    """An empty value would match everywhere."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_basket(golden_master):
            golden_master.check(
                "apple", Path(__file__).parent / "e.txt", placeholders={"home": ""}
            )
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: placeholders need a value*'home'*"])
