"""Tests for the pandas serialization helpers (pytest-remaster[pandas])."""

from __future__ import annotations

import math

import pytest

import pytest_remaster

pd = pytest.importorskip("pandas")

# pylint: disable-next=wrong-import-position
from pytest_remaster import dataframe_deserializer, dataframe_serializer  # noqa: E402


def test_serializer_writes_csv_at_fixed_precision() -> None:
    df = pd.DataFrame({"w_bess_kw": [1234.5678, 2.0]})
    text = dataframe_serializer()(df)
    assert "1234.57" in text  # %.6g
    assert "1234.5678" not in text


def test_round_trip_yields_column_mapping() -> None:
    df = pd.DataFrame({"w_bess_kw": [1.25, 2.0], "hz": [50.0, 50.001]})
    columns = dataframe_deserializer()(dataframe_serializer()(df))
    assert columns == {"w_bess_kw": [1.25, 2.0], "hz": [50.0, 50.001]}


def test_round_trip_preserves_nan_gaps() -> None:
    df = pd.DataFrame({"w_bess_kw": [1.0, math.nan, 2.0]})
    columns = dataframe_deserializer()(dataframe_serializer()(df))
    series = columns["w_bess_kw"]
    assert [series[0], series[2]] == [1.0, 2.0]
    assert math.isnan(series[1])


def test_unknown_attribute_still_raises() -> None:
    with pytest.raises(AttributeError, match="no attribute 'nonsense'"):
        _ = pytest_remaster.nonsense


def test_nan_gap_golden_end_to_end(pytester: pytest.Pytester) -> None:
    """A time-series gap survives the full golden cycle.

    Bless stores the gap as an empty CSV cell; a within-tolerance drift
    elsewhere breaks the string fast path so the matcher actually runs,
    and the gap row compares equal. A number appearing in the gap fails
    regardless of tolerance — no silent hole-masking.
    """
    pytester.makepyfile(
        """
        import math
        import pandas as pd
        from pytest_remaster import (
            GoldenMaster,
            dataframe_deserializer,
            dataframe_serializer,
            tolerance_matcher,
        )

        KWARGS = dict(
            serializer=dataframe_serializer(),
            deserializer=dataframe_deserializer(),
            matcher=tolerance_matcher({"*_kw": 0.5}),
            roundtrip=True,
        )

        def test_gap(tmp_path):
            golden = tmp_path / "nominal.csv"
            GoldenMaster(remaster=True).check(
                pd.DataFrame({"w_bess_kw": [1.0, math.nan, 2.0]}), golden, **KWARGS
            )
            # The gap is stored as an empty cell, read back as NaN
            assert "\\n1,\\n" in golden.read_text()

            checker = GoldenMaster(remaster=False)
            # Drift within tolerance elsewhere: fast path broken, matcher
            # runs, the gap row compares equal — scenario stays green
            checker.check(
                pd.DataFrame({"w_bess_kw": [1.1, math.nan, 2.0]}), golden, **KWARGS
            )

            # A number in the gap fails regardless of tolerance
            try:
                checker.check(
                    pd.DataFrame({"w_bess_kw": [1.0, 7.0, 2.0]}), golden, **KWARGS
                )
                raise RuntimeError("should have failed")
            except BaseException as exc:
                assert "w_bess_kw[1]" in str(exc)
                assert "golden=nan actual=7" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_integration_with_check(pytester: pytest.Pytester) -> None:
    """DataFrame golden: bless, drift within tolerance, drift beyond."""
    pytester.makepyfile(
        """
        import math
        import pandas as pd
        from pytest_remaster import (
            GoldenMaster,
            dataframe_deserializer,
            dataframe_serializer,
            tolerance_matcher,
        )

        KWARGS = dict(
            serializer=dataframe_serializer(),
            deserializer=dataframe_deserializer(),
            matcher=tolerance_matcher({"hz": 1e-3, "*_kw": 0.5}),
            roundtrip=True,
        )

        def test_dataframe_golden(tmp_path):
            golden = tmp_path / "nominal.csv"
            df = pd.DataFrame({"w_bess_kw": [1.0, math.nan], "hz": [50.0, 50.0]})

            GoldenMaster(remaster=True).check(df, golden, **KWARGS)
            assert golden.exists()

            checker = GoldenMaster(remaster=False)
            drifted = pd.DataFrame(
                {"w_bess_kw": [1.4, math.nan], "hz": [50.0005, 50.0]}
            )
            checker.check(drifted, golden, **KWARGS)

            broken = pd.DataFrame({"w_bess_kw": [9.0, math.nan], "hz": [50.0, 50.0]})
            try:
                checker.check(broken, golden, **KWARGS)
                raise RuntimeError("should have failed")
            except BaseException as exc:
                assert "w_bess_kw[0]" in str(exc)
                assert "tol=0.5" in str(exc)
        """
    )
    result = pytester.runpytest("--no-remaster")
    result.assert_outcomes(passed=1)


def test_named_index_compared_with_index_col_none() -> None:
    """Naming the index makes the time axis comparable.

    With index_col=None it round-trips as a regular column under its own
    tolerance key — the documented escape from the index footgun.
    """
    df = pd.DataFrame({"w_bess_kw": [1.0, 2.0]}, index=[0.0, 0.5])
    df.index.name = "t_s"
    columns = dataframe_deserializer(index_col=None)(dataframe_serializer()(df))
    assert columns == {"t_s": [0.0, 0.5], "w_bess_kw": [1.0, 2.0]}
