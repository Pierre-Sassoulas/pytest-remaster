"""Tests for version-specific overrides: override_path and dimensions."""

from __future__ import annotations

import pytest


def test_resolve_with_override_exists(pytester: pytest.Pytester) -> None:
    """resolve_with_override returns override when it exists."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import resolve_with_override

        def test_resolve(tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("base\\n")
            override.write_text("override\\n")
            assert resolve_with_override(base, override) == override
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_resolve_with_override_missing(pytester: pytest.Pytester) -> None:
    """resolve_with_override returns base when override doesn't exist."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import resolve_with_override

        def test_resolve(tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("base\\n")
            assert resolve_with_override(base, override) == base
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_resolve_with_override_none(pytester: pytest.Pytester) -> None:
    """resolve_with_override returns base when override is None."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster import resolve_with_override

        def test_resolve(tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("base\\n")
            assert resolve_with_override(base) == base
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_override_exists_and_matches(pytester: pytest.Pytester) -> None:
    """check() with override_path uses override when it exists and matches."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_override(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            override.write_text("version-specific output\\n")
            golden_master.check(
                "version-specific output", base, override_path=override
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_override_missing_falls_back_to_base(pytester: pytest.Pytester) -> None:
    """check() with override_path falls back to base when override missing."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fallback(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            golden_master.check("generic output", base, override_path=override)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_override_mismatch_remaster_writes_override(pytester: pytest.Pytester) -> None:
    """check() remasters to override_path, not base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            golden_master.check("new output", base, override_path=override)
            # Override created, base untouched
            assert override.read_text() == "new output\\n"
            assert base.read_text() == "generic output\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.314.txt*"])


def test_override_exists_mismatch_remaster(pytester: pytest.Pytester) -> None:
    """check() updates existing override, not base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            override.write_text("old 3.14 output\\n")
            golden_master.check("new 3.14 output", base, override_path=override)
            assert override.read_text() == "new 3.14 output\\n"
            assert base.read_text() == "generic output\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*a.314.txt*"])


def test_override_mismatch_no_remaster_hints_override(
    pytester: pytest.Pytester,
) -> None:
    """check() strict mode hints at creating override_path."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_hint(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("generic output\\n")
            golden_master.check("new output", base, override_path=override)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*--remaster*a.314.txt*"])


def test_override_redundant_remaster_deletes(pytester: pytest.Pytester) -> None:
    """check() in remaster mode deletes override identical to base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("same content\\n")
            override.write_text("same content\\n")
            golden_master.check("same content", base, override_path=override)
            assert not override.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*redundant*a.314.txt*"])


def test_override_redundant_no_remaster_fails(pytester: pytest.Pytester) -> None:
    """check() in strict mode fails when override is identical to base."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            base.write_text("same content\\n")
            override.write_text("same content\\n")
            golden_master.check("same content", base, override_path=override)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*identical*redundant*"])


def test_override_remaster_dedup_after_write(pytester: pytest.Pytester) -> None:
    """After remastering override, if it matches base, it gets removed."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup_after_write(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            # Base already has the "new" content; override will be written
            # with same content then deduped
            base.write_text("new output\\n")
            override.write_text("old output\\n")
            golden_master.check("new output", base, override_path=override)
            assert not override.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*redundant*a.314.txt*"])


def test_override_no_base_creates_override(pytester: pytest.Pytester) -> None:
    """check() creates override when neither base nor override exist."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_no_base(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            override = tmp_path / "a.314.txt"
            golden_master.check("new output", base, override_path=override)
            assert override.read_text() == "new output\\n"
            assert not base.exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.314.txt*"])


def test_build_override_chain(pytester: pytest.Pytester) -> None:
    """_build_override_chain generates powerset in priority order."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster.golden_master import _build_override_chain

        def test_chain():
            chain = _build_override_chain(
                Path("/d/a.txt"), version="312", platform="linux",
            )
            names = [p.name for p in chain]
            assert names == [
                "a.312.linux.txt",
                "a.312.txt",
                "a.linux.txt",
            ]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_build_override_chain_three_dimensions(pytester: pytest.Pytester) -> None:
    """_build_override_chain with three dimensions produces 7 entries."""
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_remaster.golden_master import _build_override_chain

        def test_chain():
            chain = _build_override_chain(
                Path("/d/a.txt"),
                version="312", platform="linux", implementation="cpython",
            )
            names = [p.name for p in chain]
            assert names == [
                "a.312.linux.cpython.txt",
                "a.312.linux.txt",
                "a.312.cpython.txt",
                "a.linux.cpython.txt",
                "a.312.txt",
                "a.linux.txt",
                "a.cpython.txt",
            ]
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_dimensions_resolves_most_specific(pytester: pytest.Pytester) -> None:
    """check() with dimensions uses the most specific existing file."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_resolve(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            specific = tmp_path / "a.312.linux.txt"
            specific.write_text("specific\\n")
            golden_master.check(
                "specific", base,
                dimensions={"version": "312", "platform": "linux"},
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_dimensions_falls_back_to_less_specific(pytester: pytest.Pytester) -> None:
    """check() with dimensions falls back through the chain."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fallback(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            # Only version-specific exists, no version+platform
            version_only = tmp_path / "a.312.txt"
            version_only.write_text("version output\\n")
            golden_master.check(
                "version output", base,
                dimensions={"version": "312", "platform": "linux"},
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_dimensions_falls_back_to_base(pytester: pytest.Pytester) -> None:
    """check() with dimensions falls back to base when no overrides exist."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_fallback(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            golden_master.check(
                "generic", base,
                dimensions={"version": "312", "platform": "linux"},
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_dimensions_remaster_updates_base(pytester: pytest.Pytester) -> None:
    """check() with dimensions rewrites the base when no override exists."""
    pytester.makepyfile(
        """
        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            golden_master.check(
                "new output", base,
                dimensions={"version": "312", "platform": "linux"},
            )
            assert base.read_text() == "new output\\n"
            assert list(tmp_path.iterdir()) == [base]
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*a.txt*"])


def test_dimensions_remaster_updates_resolved_override(
    pytester: pytest.Pytester,
) -> None:
    """check() with dimensions rewrites the override that was compared."""
    pytester.makepyfile(
        """
        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            version_only = tmp_path / "a.312.txt"
            version_only.write_text("old 3.12\\n")
            golden_master.check(
                "new 3.12", base,
                dimensions={"version": "312", "platform": "linux"},
            )
            assert version_only.read_text() == "new 3.12\\n"
            assert base.read_text() == "generic\\n"
            assert not (tmp_path / "a.312.linux.txt").exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*updated*a.312.txt*"])


def test_dimensions_remaster_override_matching_base_deleted(
    pytester: pytest.Pytester,
) -> None:
    """A rewritten override identical to the base is deleted."""
    pytester.makepyfile(
        """
        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            override = tmp_path / "a.312.txt"
            override.write_text("old 3.12\\n")
            golden_master.check(
                "generic", base,
                dimensions={"version": "312", "platform": "linux"},
            )
            assert not override.exists()
            assert base.read_text() == "generic\\n"
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines([
        "*updated*a.312.txt*",
        "*deleted (redundant)*a.312.txt*",
    ])


SPLIT_TEST = """
    import pytest

    {marker}
    def test_remaster(golden_master, tmp_path):
        base = tmp_path / "a.txt"
        base.write_text("generic\\n")
        golden_master.check(
            "new output", base,
            dimensions={{
                "version": "312", "platform": "linux", "implementation": "pypy",
            }},
        )
        assert (tmp_path / "{written}").read_text() == "new output\\n"
        assert base.read_text() == "generic\\n"
        assert len(list(tmp_path.iterdir())) == 2
    """


@pytest.mark.parametrize(
    ("split", "written"),
    [
        ('["implementation"]', "a.pypy.txt"),
        ('"implementation"', "a.pypy.txt"),
        ('"all"', "a.312.linux.pypy.txt"),
    ],
)
def test_dimensions_remaster_split_marker(
    pytester: pytest.Pytester, split: str, written: str
) -> None:
    """@pytest.mark.remaster(split=...) writes an override for those dimensions."""
    marker = f"@pytest.mark.remaster(split={split})"
    pytester.makepyfile(SPLIT_TEST.format(marker=marker, written=written))
    result = pytester.runpytest("--remaster", "--strict-markers")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines([f"*created*{written}*"])


def test_dimensions_split_keeps_compared_dimensions(pytester: pytest.Pytester) -> None:
    """Splitting an existing override adds to its dimensions, so it wins next run."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.remaster(split=["implementation"])
        def test_remaster(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            version_only = tmp_path / "a.312.txt"
            version_only.write_text("3.12\\n")
            dimensions = {"version": "312", "implementation": "pypy"}
            golden_master.check("pypy 3.12", base, dimensions=dimensions)
            assert (tmp_path / "a.312.pypy.txt").read_text() == "pypy 3.12\\n"
            assert version_only.read_text() == "3.12\\n"
            assert not (tmp_path / "a.pypy.txt").exists()
        """
    )
    result = pytester.runpytest("--remaster", "--strict-markers")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.312.pypy.txt*"])


def test_dimensions_split_unknown_dimension(pytester: pytest.Pytester) -> None:
    """A split naming none of the check's dimensions is an error."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.remaster(split=["implemntation"])
        def test_typo(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            with pytest.raises(ValueError, match="names none of the dimensions"):
                golden_master.check(
                    "generic", base, dimensions={"implementation": "pypy"}
                )
        """
    )
    result = pytester.runpytest("--remaster", "--strict-markers")
    result.assert_outcomes(passed=1)


def test_dimensions_split_marker_keeps_remaster_mode(pytester: pytest.Pytester) -> None:
    """remaster(split=...) alone does not enable remastering."""
    pytester.makeini("[pytest]\nremaster-by-default = false\n")
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.remaster(split=["implementation"])
        def test_strict(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            golden_master.check(
                "new output", base,
                dimensions={"version": "312", "implementation": "pypy"},
            )
        """
    )
    result = pytester.runpytest("--strict-markers")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*Mismatch at*a.txt*",
        "*--remaster to update*a.pypy.txt*",
    ])


def test_dimensions_split_marker_combined_with_enabled(
    pytester: pytest.Pytester,
) -> None:
    """remaster(True, split=...) enables remastering into the new override."""
    pytester.makeini("[pytest]\nremaster-by-default = false\n")
    marker = '@pytest.mark.remaster(True, split=["implementation"])'
    pytester.makepyfile(SPLIT_TEST.format(marker=marker, written="a.pypy.txt"))
    result = pytester.runpytest("--strict-markers")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*a.pypy.txt*"])


def test_dimensions_dedup_against_less_specific(pytester: pytest.Pytester) -> None:
    """check() deduplicates against less-specific existing overrides."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_dedup(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("generic\\n")
            # Both overrides have the same content
            (tmp_path / "a.312.linux.txt").write_text("same\\n")
            (tmp_path / "a.312.txt").write_text("same\\n")
            golden_master.check(
                "same", base,
                dimensions={"version": "312", "platform": "linux"},
            )
            # Most specific removed because it matches less specific
            assert not (tmp_path / "a.312.linux.txt").exists()
            assert (tmp_path / "a.312.txt").exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*deleted*redundant*a.312.linux.txt*"])


def test_dimensions_new_test_creates_base_file(pytester: pytest.Pytester) -> None:
    """check() with dimensions creates the base file for new tests (no files exist)."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_new(golden_master, tmp_path):
            base = tmp_path / "test.txt"
            golden_master.check(
                "new output", base,
                dimensions={"version": "314", "platform": "linux"},
            )
            # Base file should be created, not the most specific override
            assert base.read_text() == "new output\\n"
            assert not (tmp_path / "test.314.linux.txt").exists()
            assert not (tmp_path / "test.314.txt").exists()
            assert not (tmp_path / "test.linux.txt").exists()
        """
    )
    result = pytester.runpytest("--remaster")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*created*test.txt*"])


def test_dimensions_mutually_exclusive_with_override_path(
    pytester: pytest.Pytester,
) -> None:
    """check() raises ValueError when both override_path and dimensions given."""
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_exclusive(golden_master, tmp_path):
            base = tmp_path / "a.txt"
            base.write_text("content\\n")
            try:
                golden_master.check(
                    "content", base,
                    override_path=tmp_path / "a.312.txt",
                    dimensions={"version": "312"},
                )
                assert False, "should have raised"
            except ValueError as exc:
                assert "mutually exclusive" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)
