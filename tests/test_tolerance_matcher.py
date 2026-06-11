"""Tests for the tolerance_matcher builder.

Unlike the plugin tests, these call the matcher directly: it is a pure
function with no pytest machinery, so pytester is only needed for the
final integration test with the golden_master fixture.
"""

from __future__ import annotations

import math

import pytest

from pytest_remaster import Tolerance, tolerance_matcher


def test_scalar_within_tolerance() -> None:
    matcher = tolerance_matcher(default=0.5)
    assert matcher(1.2, 1.0) is True


def test_scalar_beyond_tolerance() -> None:
    matcher = tolerance_matcher(default=0.5)
    with pytest.raises(AssertionError, match=r"golden=1 actual=3 \|Δ\|=2 tol=0.5"):
        matcher(3.0, 1.0)


def test_exact_key_tolerance() -> None:
    matcher = tolerance_matcher({"hz": 1e-3})
    assert matcher({"hz": 50.0005}, {"hz": 50.0}) is True
    with pytest.raises(AssertionError, match=r"hz:.*tol=0\.001"):
        matcher({"hz": 50.01}, {"hz": 50.0})


def test_fnmatch_pattern_tolerance() -> None:
    matcher = tolerance_matcher({"*_kw": 0.5})
    assert matcher({"w_bess_kw": 1.4}, {"w_bess_kw": 1.0}) is True
    with pytest.raises(AssertionError, match=r"w_bess_kw:.*tol=0\.5"):
        matcher({"w_bess_kw": 2.0}, {"w_bess_kw": 1.0})


def test_exact_key_wins_over_pattern() -> None:
    matcher = tolerance_matcher({"*_kw": 0.5, "w_grid_kw": 5.0})
    assert matcher({"w_grid_kw": 4.0}, {"w_grid_kw": 1.0}) is True


def test_default_is_exact() -> None:
    matcher = tolerance_matcher({"*_kw": 0.5})
    with pytest.raises(AssertionError, match=r"soc_pct:.*tol=0"):
        matcher({"soc_pct": 50.0000001}, {"soc_pct": 50.0})


def test_relative_tolerance() -> None:
    matcher = tolerance_matcher(rel=1e-4)
    assert matcher(1000.05, 1000.0) is True
    with pytest.raises(AssertionError, match=r"rel=0\.0001"):
        matcher(1001.0, 1000.0)


def test_sequence_inherits_key_tolerance() -> None:
    matcher = tolerance_matcher({"w_bess_kw": 0.5})
    assert matcher({"w_bess_kw": [1.1, 2.0]}, {"w_bess_kw": [1.0, 2.0]}) is True
    with pytest.raises(AssertionError, match=r"w_bess_kw\[0\]: golden=1 actual=3"):
        matcher({"w_bess_kw": [3.0, 2.0]}, {"w_bess_kw": [1.0, 2.0]})


def test_sequence_length_mismatch() -> None:
    matcher = tolerance_matcher()
    with pytest.raises(AssertionError, match="length 1 != golden 2"):
        matcher([1.0], [1.0, 2.0])


def test_report_limit_caps_rows() -> None:
    matcher = tolerance_matcher(report_limit=2)
    with pytest.raises(AssertionError) as excinfo:
        matcher([9.0] * 7, [0.0] * 7)
    message = str(excinfo.value)
    assert "value[0]" in message
    assert "value[1]" in message
    assert "value[2]" not in message
    assert "and 5 more rows beyond tolerance" in message


def test_missing_and_extra_keys() -> None:
    matcher = tolerance_matcher()
    with pytest.raises(AssertionError) as excinfo:
        matcher({"a": 1.0, "extra": 2.0}, {"a": 1.0, "missing": 3.0})
    message = str(excinfo.value)
    assert "missing: missing from actual" in message
    assert "extra: not in golden" in message


def test_nested_mapping_path() -> None:
    matcher = tolerance_matcher({"hz": 1e-3})
    with pytest.raises(AssertionError, match=r"nominal\.hz: golden=50"):
        matcher({"nominal": {"hz": 51.0}}, {"nominal": {"hz": 50.0}})


def test_non_numeric_values_compared_exactly() -> None:
    matcher = tolerance_matcher(default=10.0)
    assert matcher({"mode": "grid"}, {"mode": "grid"}) is True
    with pytest.raises(AssertionError, match="mode: golden='grid' actual='island'"):
        matcher({"mode": "island"}, {"mode": "grid"})


def test_bool_not_treated_as_number() -> None:
    matcher = tolerance_matcher(default=10.0)
    with pytest.raises(AssertionError, match="golden=False actual=True"):
        matcher({"on": True}, {"on": False})


def test_per_key_relative_tolerance() -> None:
    matcher = tolerance_matcher({"soc_pct": 0.1, "*_kw": (0.5, 1e-3)})
    # 10 MW grid power: 1e-3 rel gives 10 kW slack on top of 0.5 kW abs
    assert matcher({"w_grid_kw": 10008.0}, {"w_grid_kw": 10000.0}) is True
    # soc_pct stays purely absolute: 0.2 drift fails despite being tiny
    # relative to 50
    with pytest.raises(AssertionError, match=r"soc_pct:.*tol=0\.1"):
        matcher({"soc_pct": 50.2}, {"soc_pct": 50.0})


def test_per_key_rtol_overrides_global_rel() -> None:
    matcher = tolerance_matcher({"x": (0.0, 0.0)}, rel=1.0)
    with pytest.raises(AssertionError, match="x: golden=1"):
        matcher({"x": 1.1}, {"x": 1.0})


def test_bare_float_entries_use_global_rel() -> None:
    matcher = tolerance_matcher({"x": 0.0}, rel=1e-2)
    assert matcher({"x": 100.5}, {"x": 100.0}) is True


def test_per_key_rtol_in_failure_message() -> None:
    matcher = tolerance_matcher({"*_kw": (0.5, 1e-4)})
    with pytest.raises(AssertionError, match=r"tol=0\.5 rel=0\.0001"):
        matcher({"w_kw": 200.0}, {"w_kw": 100.0})


def test_nan_equals_nan_by_default() -> None:
    nan = math.nan
    matcher = tolerance_matcher({"w_bess_kw": 0.5})
    assert matcher({"w_bess_kw": [1.1, nan, 2.0]}, {"w_bess_kw": [1.0, nan, 2.0]})


def test_nan_vs_number_mismatches_regardless_of_tolerance() -> None:
    nan = math.nan
    matcher = tolerance_matcher(default=1e9)
    with pytest.raises(AssertionError, match=r"value\[0\]: golden=1 actual=nan"):
        matcher([nan], [1.0])
    with pytest.raises(AssertionError, match=r"value\[0\]: golden=nan actual=1"):
        matcher([1.0], [nan])


def test_nan_equal_false_rejects_nan_pairs() -> None:
    nan = math.nan
    matcher = tolerance_matcher(nan_equal=False)
    with pytest.raises(AssertionError, match=r"value: golden=nan actual=nan"):
        matcher(nan, nan)


def test_all_failures_reported_together() -> None:
    matcher = tolerance_matcher({"hz": 1e-3, "*_kw": 0.5})
    with pytest.raises(AssertionError) as excinfo:
        matcher({"hz": 51.0, "w_bess_kw": 9.0}, {"hz": 50.0, "w_bess_kw": 1.0})
    message = str(excinfo.value)
    assert "hz:" in message
    assert "w_bess_kw:" in message


def test_integration_with_check(pytester: pytest.Pytester) -> None:
    """tolerance_matcher plugs into check() via deserializer + matcher."""
    pytester.makepyfile(
        """
        import json
        from pytest_remaster import tolerance_matcher

        MATCHER = tolerance_matcher({"hz": 1e-3, "*_kw": 0.5})

        def test_metrics(golden_master, tmp_path):
            expected = tmp_path / "nominal.metrics.json"
            expected.write_text('{"hz": 50.0, "w_bess_kw": 1.0}\\n')
            golden_master.check(
                {"hz": 50.0005, "w_bess_kw": 1.4},
                expected,
                serializer=json.dumps,
                deserializer=json.loads,
                matcher=MATCHER,
            )
            golden_master.check(
                {"hz": 51.0, "w_bess_kw": 1.0},
                expected,
                serializer=json.dumps,
                deserializer=json.loads,
                matcher=MATCHER,
            )
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*Mismatch at *nominal.metrics.json:*",
        "*hz: golden=50 actual=51*tol=0.001*",
    ])


def test_total_limit_caps_overall_report() -> None:
    # 10 drifted single-value columns x default per-sequence cap would be
    # 10 lines; total_limit caps the overall report
    total_limit = 3
    matcher = tolerance_matcher(total_limit=total_limit)
    actual = {f"col_{i}": 9.0 for i in range(10)}
    golden = {f"col_{i}": 0.0 for i in range(10)}
    with pytest.raises(AssertionError) as excinfo:
        matcher(actual, golden)
    lines = str(excinfo.value).splitlines()
    assert len(lines) == total_limit + 1
    assert lines[-1] == "... and 7 more values beyond tolerance"


def test_total_limit_unlimited_by_default() -> None:
    matcher = tolerance_matcher()
    actual = {f"col_{i}": 9.0 for i in range(10)}
    golden = {f"col_{i}": 0.0 for i in range(10)}
    with pytest.raises(AssertionError) as excinfo:
        matcher(actual, golden)
    assert len(str(excinfo.value).splitlines()) == len(actual)


def test_tolerance_namedtuple_keyword_form() -> None:
    """Tolerance(atol=..., rtol=...) is interchangeable with a bare pair."""
    matcher = tolerance_matcher({"*_kw": Tolerance(atol=0.5, rtol=1e-4)})
    assert matcher({"w_kw": [10000.9]}, {"w_kw": [10000.0]})
    with pytest.raises(AssertionError, match=r"w_kw\[0\]"):
        matcher({"w_kw": [10002.0]}, {"w_kw": [10000.0]})


def test_tolerance_defaults_are_exact() -> None:
    """Single-term forms read as pure absolute or pure relative."""
    absolute = tolerance_matcher({"v": Tolerance(atol=0.5)})
    assert absolute({"v": 1.4}, {"v": 1.0})
    with pytest.raises(AssertionError):
        absolute({"v": 2.0}, {"v": 1.0})

    relative = tolerance_matcher({"v": Tolerance(rtol=1e-2)})
    assert relative({"v": 101.0}, {"v": 100.0})
    with pytest.raises(AssertionError):
        relative({"v": 105.0}, {"v": 100.0})


def test_tolerance_does_not_inherit_global_rel() -> None:
    """Like a bare pair, Tolerance opts out of rel=; bare floats keep it."""
    matcher = tolerance_matcher({"pinned": Tolerance(atol=0.1), "loose": 0.1}, rel=1e-2)
    assert matcher({"loose": 101.0}, {"loose": 100.0})  # bare float + rel
    with pytest.raises(AssertionError, match="pinned"):
        matcher({"pinned": 101.0}, {"pinned": 100.0})  # rtol stays 0.0
