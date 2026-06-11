"""Tests for the Output per-suffix spec in check_each()."""

from __future__ import annotations

import pytest


def test_heterogeneous_outputs(pytester: pytest.Pytester) -> None:
    """Each suffix carries its own serialization and comparison."""
    pytester.makepyfile(
        """
        import json
        from pytest_remaster import CaseData, Output, tolerance_matcher

        def run(case):
            return {"series": [1.05, 2.0], "metrics": {"max_kw": 2.04}, "log": "ok"}

        def test_each(golden_master, tmp_path):
            case_dir = tmp_path / "case"
            case_dir.mkdir()
            (case_dir / "expected.csv").write_text("1 2\\n")
            (case_dir / "expected.metrics.json").write_text('{"max_kw": 2.0}\\n')
            (case_dir / "expected.log").write_text("ok\\n")
            golden_master.check_each(
                CaseData(input=case_dir),
                runner=run,
                extractors={
                    ".csv": Output(
                        lambda r: r["series"],
                        serializer=lambda vals: " ".join(f"{v:g}" for v in vals),
                        deserializer=lambda text: [float(x) for x in text.split()],
                        matcher=tolerance_matcher(default=0.1),
                        roundtrip=True,
                    ),
                    ".metrics.json": Output(
                        lambda r: r["metrics"],
                        serializer=json.dumps,
                        deserializer=json.loads,
                        matcher=tolerance_matcher({"*_kw": 0.5}),
                    ),
                    ".log": lambda r: r["log"],  # bare callable, exact match
                },
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_name_override_str_and_callable(pytester: pytest.Pytester) -> None:
    """Output.name replaces expected{suffix}; callables receive the case."""
    pytester.makepyfile(
        """
        from pytest_remaster import CaseData, Output

        def test_each(golden_master, tmp_path):
            case_dir = tmp_path / "nominal"
            case_dir.mkdir()
            (case_dir / "nominal.csv").write_text("data\\n")
            (case_dir / "trace.log").write_text("ok\\n")
            golden_master.check_each(
                CaseData(input=case_dir),
                runner=lambda case: {"df": "data", "log": "ok"},
                extractors={
                    ".csv": Output(
                        lambda r: r["df"],
                        name=lambda case: f"{case.input.name}.csv",
                    ),
                    ".log": Output(lambda r: r["log"], name="trace.log"),
                },
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_output_comparison_overrides_shared_as_unit(pytester: pytest.Pytester) -> None:
    """An Output setting a normalizer does not inherit the shared matcher."""
    pytester.makepyfile(
        """
        from pytest_remaster import CaseData, Output

        def boom(actual, expected):
            raise AssertionError("shared matcher must not leak into .log")

        def test_each(golden_master, tmp_path):
            case_dir = tmp_path / "case"
            case_dir.mkdir()
            (case_dir / "expected.num").write_text("1.0\\n")
            (case_dir / "expected.log").write_text("OK   \\n")
            golden_master.check_each(
                CaseData(input=case_dir),
                runner=lambda case: {"num": 1.2, "log": "OK"},
                extractors={
                    ".num": lambda r: r["num"],  # uses the shared matcher
                    ".log": Output(
                        lambda r: r["log"], normalizer=str.strip
                    ),  # replaces it
                },
                matcher=lambda a, e: abs(a - float(e)) < 0.5,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_output_serializer_falls_back_to_shared(pytester: pytest.Pytester) -> None:
    """Outputs without a serializer use the shared one."""
    pytester.makepyfile(
        """
        from pytest_remaster import CaseData, Output

        def test_each(golden_master, tmp_path):
            case_dir = tmp_path / "case"
            case_dir.mkdir()
            (case_dir / "expected.a").write_text("<1>\\n")
            (case_dir / "expected.b").write_text("[2]\\n")
            golden_master.check_each(
                CaseData(input=case_dir),
                runner=lambda case: {"a": 1, "b": 2},
                extractors={
                    ".a": lambda r: r["a"],
                    ".b": Output(lambda r: r["b"], serializer=lambda v: f"[{v}]"),
                },
                serializer=lambda v: f"<{v}>",
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_name_override_file_mode(pytester: pytest.Pytester) -> None:
    """In file mode (input with suffix), Output.name resolves to a sibling."""
    pytester.makepyfile(
        """
        from pytest_remaster import CaseData, Output

        def test_each(golden_master, tmp_path):
            source = tmp_path / "arguments.py"
            source.write_text("x = 1\\n")
            (tmp_path / "arguments.lint.txt").write_text("clean\\n")
            golden_master.check_each(
                CaseData(input=source),
                runner=lambda case: "clean",
                extractors={
                    ".txt": Output(
                        lambda r: r,
                        name=lambda case: f"{case.input.stem}.lint.txt",
                    ),
                },
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)
