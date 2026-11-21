"""Tests for check_inline: expectations stored in comments of the input file."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write(pytester: pytest.Pytester, name: str, content: str) -> Path:
    """Write *content* as it is (``makefile`` would strip the last newline)."""
    path = pytester.path / name
    path.write_text(content, encoding="utf-8")
    return path


TEST_SUMS = """
    from pathlib import Path

    SUMS = Path(__file__).parent / "sums.txt"

    def test_sums(golden_master):
        golden_master.check_inline(SUMS, {"total": lambda line: eval(line.code)})
    """


def test_matching_expectations_pass(pytester: pytest.Pytester) -> None:
    """Every comment matching its line passes and leaves the file alone."""
    sums = _write(pytester, "sums.txt", "2 + 3  # total: 5\n4 * 2  # total: 8\n")
    before = sums.read_text()
    pytester.makepyfile(TEST_SUMS)
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1)
    assert sums.read_text() == before


def test_mismatch_fails_listing_every_line(pytester: pytest.Pytester) -> None:
    """Strict mode reports all the wrong comments at once, without writing."""
    content = "2 + 3  # total: 6\n1 + 1  # total: 2\n4 * 2  # total: 9\n"
    sums = _write(pytester, "sums.txt", content)
    pytester.makepyfile(TEST_SUMS)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "Mismatch at *sums.txt:",
        "*sums.txt:1: total: expected '6', got '5'",
        "*sums.txt:3: total: expected '9', got '8'",
        "Run with --remaster to update *sums.txt.",
    ])
    assert sums.read_text() == content


def test_remaster_rewrites_comments_in_place(pytester: pytest.Pytester) -> None:
    """Remaster fixes the wrong comments and keeps the rest of the file."""
    sums = _write(
        pytester,
        "sums.txt",
        "# Sums of fruits\n2 + 3  # total: 6\n\n4 * 2  # total: 8\n",
    )
    pytester.makepyfile(TEST_SUMS)
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines([
        "*Expected files updated, please review the changes:",
        "*updated: *sums.txt:2: total: expected '6', got '5'",
    ])
    assert (
        sums.read_text() == "# Sums of fruits\n2 + 3  # total: 5\n\n4 * 2  # total: 8\n"
    )
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_remaster_fills_an_empty_expectation(pytester: pytest.Pytester) -> None:
    """A key with no value is how a new expectation gets added."""
    sums = _write(pytester, "sums.txt", "2 + 3  # total:\n")
    pytester.makepyfile(TEST_SUMS)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_text() == "2 + 3  # total: 5\n"


def test_remaster_keeps_line_endings(pytester: pytest.Pytester) -> None:
    r"""A file with ``\r\n`` line endings keeps them when rewritten."""
    sums = pytester.path / "sums.txt"
    sums.write_bytes(b"2 + 3  # total: 6\r\n4 * 2  # total: 8\r\n")
    pytester.makepyfile(TEST_SUMS)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_bytes() == b"2 + 3  # total: 5\r\n4 * 2  # total: 8\r\n"


def test_several_keys_on_one_line_share_the_runner(pytester: pytest.Pytester) -> None:
    """The runner runs once per line; each key reads what it needs from it."""
    words = _write(
        pytester, "words.txt", "apple  # shout: APPLE  # size: 4\nkiwi  #size:4\n"
    )
    pytester.makepyfile(
        """
        from pathlib import Path

        WORDS = Path(__file__).parent / "words.txt"
        SEEN = []

        def run(line):
            SEEN.append((line.lineno, line.code, dict(line.expected)))
            return line.code

        def test_words(golden_master):
            golden_master.check_inline(
                WORDS, {"size": len, "shout": str.upper}, runner=run
            )
            assert SEEN == [
                (1, "apple", {"shout": "APPLE", "size": "4"}),
                (2, "kiwi", {"size": "4"}),
            ]
        """
    )
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert words.read_text() == "apple  # shout: APPLE  # size: 5\nkiwi  #size:4\n"


def test_custom_comment_marker_and_serializer(pytester: pytest.Pytester) -> None:
    """Files in another language pick their own comment marker."""
    _write(pytester, "fruits.js", "apple // size: <5>\n# size: ignored\n")
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fruits(golden_master):
            golden_master.check_inline(
                Path(__file__).parent / "fruits.js",
                {"size": lambda line: len(line.code)},
                serializer=lambda value: f"<{value}>",
                comment="//",
            )
        """
    )
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_mismatches_are_collected(pytester: pytest.Pytester) -> None:
    """Inside collecting(), a wrong comment does not hide the next check."""
    _write(pytester, "sums.txt", "2 + 3  # total: 6\n")
    _write(pytester, "more.txt", "1 + 1  # total: 3\n")
    pytester.makepyfile(
        """
        from pathlib import Path

        HERE = Path(__file__).parent

        def test_sums(golden_master):
            with golden_master.collecting():
                for name in ("sums.txt", "more.txt"):
                    golden_master.check_inline(
                        HERE / name, {"total": lambda line: eval(line.code)}
                    )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*2 golden master mismatches:*",
        "*sums.txt:1: total: expected '6', got '5'",
        "*more.txt:1: total: expected '3', got '2'",
    ])


def test_file_without_expectation_is_malformed(pytester: pytest.Pytester) -> None:
    """A file checking nothing is an error, not a silent pass."""
    _write(pytester, "sums.txt", "2 + 3\n")
    pytester.makepyfile(TEST_SUMS)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*MalformedTestCase: *sums.txt*no inline expectation found*'# total:'*"
    ])


def test_value_must_fit_on_one_line(pytester: pytest.Pytester) -> None:
    """A value spanning lines cannot live in a comment."""
    _write(pytester, "sums.txt", "2 + 3  # total: 5\n")
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_sums(golden_master):
            golden_master.check_inline(
                Path(__file__).parent / "sums.txt", {"total": lambda line: "5\\n6"}
            )
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*ValueError: *sums.txt:1: an inline expectation must fit on one line*"
    ])


def test_extractors_are_required(pytester: pytest.Pytester) -> None:
    """Without any key there is nothing to look for."""
    _write(pytester, "sums.txt", "2 + 3  # total: 5\n")
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_sums(golden_master):
            golden_master.check_inline(Path(__file__).parent / "sums.txt", {})
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: check_inline needs at least one*"])


TEST_VERSIONED_SUMS = """
    from pathlib import Path

    SUMS = Path(__file__).parent / "sums.txt"

    def test_sums(golden_master):
        golden_master.check_inline(
            SUMS, {{"total": lambda line: eval(line.code)}}, version={version}
        )
    """


def test_expectation_for_another_version_is_ignored(pytester: pytest.Pytester) -> None:
    """One line can say something different for old and new versions."""
    content = "2 + 3  # <3.14: total: 5  # >=3.14: total: 6\n4 * 2  # >9.0:total: 0\n"
    sums = _write(pytester, "sums.txt", content)
    pytester.makepyfile(TEST_VERSIONED_SUMS.format(version=(3, 13, 2)))
    pytester.runpytest("--remaster").assert_outcomes(passed=1)
    assert sums.read_text() == content


def test_only_the_running_version_is_checked(pytester: pytest.Pytester) -> None:
    """A wrong value fails for the version it is written for, and only there."""
    content = "2 + 3  # <3.14: total: 5  # >=3.14: total: 6\n"
    sums = _write(pytester, "sums.txt", content)
    pytester.makepyfile(TEST_VERSIONED_SUMS.format(version=(3, 14, 0)))
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*sums.txt:1: total: expected '6', got '5'"])
    assert sums.read_text() == content


def test_remaster_keeps_the_other_versions(pytester: pytest.Pytester) -> None:
    """Remaster only rewrites what the running version can vouch for."""
    sums = _write(
        pytester, "sums.txt", "2 + 3  # <3.14: total: 9  # >=3.14: total: 6\n"
    )
    pytester.makepyfile(TEST_VERSIONED_SUMS.format(version=(3, 14, 0)))
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_text() == "2 + 3  # <3.14: total: 9  # >=3.14: total: 5\n"


def test_file_for_other_versions_only_is_not_malformed(
    pytester: pytest.Pytester,
) -> None:
    """A file whose expectations are all for other versions checks nothing here."""
    _write(pytester, "sums.txt", "2 + 3  # >=9.0: total: 6\n")
    pytester.makepyfile(TEST_VERSIONED_SUMS.format(version=(3, 14, 0)))
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_unknown_version_operator_is_an_error(pytester: pytest.Pytester) -> None:
    """A condition that cannot be read never passes silently."""
    _write(pytester, "sums.txt", "2 + 3  # ==3.14: total: 5\n")
    pytester.makepyfile(TEST_VERSIONED_SUMS.format(version=(3, 14, 0)))
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: unknown version operator '=='*"])


def test_remaster_fills_an_empty_versioned_expectation(
    pytester: pytest.Pytester,
) -> None:
    """Filling a value keeps the next comment two spaces away."""
    sums = _write(pytester, "sums.txt", "2 + 3  # <3.14: total:  # >=3.14: total: 6\n")
    pytester.makepyfile(TEST_VERSIONED_SUMS.format(version=(3, 13, 0)))
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_text() == "2 + 3  # <3.14: total: 5  # >=3.14: total: 6\n"


TEST_FRUITS = """
    from pathlib import Path

    FRUITS = Path(__file__).parent / "fruits.txt"

    def count(line, letter="a"):
        return line.code.count(letter)

    def test_fruits(golden_master):
        golden_master.check_inline(FRUITS, {"count": count})
    """


def test_key_with_an_argument(pytester: pytest.Pytester) -> None:
    """The text between the parentheses is given to the function."""
    fruits = _write(
        pytester, "fruits.txt", "banana  # count: 3  # count(n):  # count(z): 0\n"
    )
    pytester.makepyfile(TEST_FRUITS)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert fruits.read_text() == "banana  # count: 3  # count(n): 2  # count(z): 0\n"
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_key_with_an_argument_mismatch_names_the_argument(
    pytester: pytest.Pytester,
) -> None:
    """The failure says which argument is wrong."""
    _write(pytester, "fruits.txt", "banana  # count(n): 5  # >=3.0: count(b): 1\n")
    pytester.makepyfile(TEST_FRUITS)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*fruits.txt:1: count(n): expected '5', got '2'"])


TEST_TREE = """
    from pathlib import Path

    TREE = Path(__file__).parent / "tree.txt"
    APPLE = {"color": "red", "leaves": [{"color": "green"}, {"color": "brown"}]}

    def follow(line, key):
        found = APPLE
        for step in key.replace("]", "").replace("[", ".").split("."):
            found = found[int(step)] if step.isdigit() else found[step]
        return found

    def test_tree(golden_master):
        golden_master.check_inline(TREE, follow, key_pattern=r"[a-z]+[a-z0-9.\\[\\]]*")
    """


def test_key_pattern_reads_keys_not_listed_in_advance(
    pytester: pytest.Pytester,
) -> None:
    """Any key matching the pattern is given to the one function."""
    tree = _write(
        pytester,
        "tree.txt",
        "# note: a comment alone on its line is not an expectation\n"
        "apple  # color: red  # leaves[1].color:  # >=3.0: leaves[0].color: blue\n",
    )
    pytester.makepyfile(TEST_TREE)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert tree.read_text() == (
        "# note: a comment alone on its line is not an expectation\n"
        "apple  # color: red  # leaves[1].color: brown"
        "  # >=3.0: leaves[0].color: green\n"
    )
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_key_pattern_without_expectation_is_malformed(
    pytester: pytest.Pytester,
) -> None:
    """Comment-only lines do not count, so this file checks nothing."""
    _write(pytester, "tree.txt", "# color: red\napple\n")
    pytester.makepyfile(TEST_TREE)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*MalformedTestCase: *no inline expectation found*"])


def test_key_pattern_and_mapping_are_exclusive(pytester: pytest.Pytester) -> None:
    """A mapping lists its keys; a pattern needs one function."""
    _write(pytester, "sums.txt", "2 + 3  # total: 5\n")
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_sums(golden_master):
            golden_master.check_inline(
                Path(__file__).parent / "sums.txt", {"total": len}, key_pattern="x"
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: check_inline takes either a mapping*"])


def test_comment_about_the_next_line(pytester: pytest.Pytester) -> None:
    """``# +1:`` is about the line below, whose code the extractor receives."""
    sums = _write(pytester, "sums.txt", "# +1: total: 6\n2 + 3\n4 * 2  # total: 8\n")
    pytester.makepyfile(TEST_SUMS)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*sums.txt:2: total: expected '6', got '5'"])
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_text() == "# +1: total: 5\n2 + 3\n4 * 2  # total: 8\n"
    pytester.runpytest("--no-remaster").assert_outcomes(passed=1)


def test_comment_about_a_line_above_or_a_numbered_line(
    pytester: pytest.Pytester,
) -> None:
    """``# -1:`` is about the line above, a bare number about that line."""
    sums = _write(
        pytester, "sums.txt", "2 + 3\n# -1: total:\n4 * 2\n# 3: >=3.0: total:\n"
    )
    pytester.makepyfile(TEST_SUMS)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_text() == ("2 + 3\n# -1: total: 5\n4 * 2\n# 3: >=3.0: total: 8\n")


def test_expectations_of_one_line_are_gathered(pytester: pytest.Pytester) -> None:
    """A line gets the comments pointing at it and its own, with one runner call."""
    tree = _write(
        pytester,
        "tree.txt",
        "# +2: leaves[0].color:\n# +1: leaves[1].color: brown\napple  # color:\n",
    )
    pytester.makepyfile(TEST_TREE)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert tree.read_text() == (
        "# +2: leaves[0].color: green\n# +1: leaves[1].color: brown\n"
        "apple  # color: red\n"
    )


def test_remaster_leaves_the_matching_comments_alone(pytester: pytest.Pytester) -> None:
    """Only the wrong value is rewritten: the spacing of the others stays."""
    sums = _write(
        pytester, "sums.txt", "2 + 3 #total:5\n# -1: total: 5\n4 * 2 #total:9\n"
    )
    pytester.makepyfile(TEST_SUMS)
    pytester.runpytest("--remaster").assert_outcomes(passed=1, errors=1)
    assert sums.read_text() == "2 + 3 #total:5\n# -1: total: 5\n4 * 2 #total: 8\n"


def test_comment_pointing_outside_the_file_is_an_error(
    pytester: pytest.Pytester,
) -> None:
    """A wrong offset is reported, not silently dropped."""
    _write(pytester, "sums.txt", "2 + 3\n# +1: total: 5\n")
    pytester.makepyfile(TEST_SUMS)
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: *sums.txt:2: *points at line 3*"])
