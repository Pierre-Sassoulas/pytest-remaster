"""Pandas serialization helpers for numeric golden masters.

Requires the ``pandas`` extra: ``pip install pytest-remaster[pandas]``.
The helpers pair with ``tolerance_matcher`` and ``roundtrip=True``:
the serializer writes a human-reviewable CSV at fixed precision, the
deserializer parses it back into the column → series mapping that
``tolerance_matcher`` recurses natively.
"""

from __future__ import annotations

import io
import json
import operator
from collections.abc import Callable, Hashable
from typing import Any

import pandas as pd

from pytest_remaster.golden_master import Output, json_serializer


def dataframe_serializer(float_format: str = "%.6g") -> Callable[[pd.DataFrame], str]:
    """Return a serializer writing a DataFrame as CSV at fixed precision.

    Usage::

        golden_master.check(
            df,
            golden_dir / "nominal.csv",
            serializer=dataframe_serializer(),
            deserializer=dataframe_deserializer(),
            matcher=tolerance_matcher({"hz": 1e-3, "*_kw": 0.5}),
            roundtrip=True,
        )

    Args:
        float_format: ``printf``-style float format for ``to_csv``.
            Default ``"%.6g"`` — 6 significant figures, human-reviewable.

    """

    def _serialize(df: pd.DataFrame) -> str:
        return df.to_csv(float_format=float_format)

    return _serialize


def dataframe_deserializer(
    index_col: int | str | None = 0,
) -> Callable[[str], dict[Hashable, list[Any]]]:
    """Return a deserializer parsing golden CSV text into column → series.

    The resulting ``dict[column, list]`` is the shape ``tolerance_matcher``
    recurses natively, resolving each column's tolerance by name.

    Args:
        index_col: Column to treat as the index (excluded from comparison).
            Default ``0`` — matches the index written by
            :func:`dataframe_serializer`. Pass ``None`` to compare it too;
            name the index (``df.index.name = "t_s"``) so it becomes a
            proper column with its own tolerance key, otherwise a shifted
            time axis with identical values passes silently.

    """

    def _deserialize(text: str) -> dict[Hashable, list[Any]]:
        return pd.read_csv(io.StringIO(text), index_col=index_col).to_dict("list")

    return _deserialize


def scenario_outputs(
    matcher: Callable[[Any, Any], bool],
    *,
    df_suffix: str = ".csv",
    metrics_suffix: str = ".metrics.json",
    float_format: str = "%.6g",
    index_col: int | str | None = 0,
) -> dict[str, Output]:
    """Per-suffix outputs for the (DataFrame, metrics-dict) scenario shape.

    For runners returning ``{case_name: (df, metrics)}`` — a time-series
    DataFrame plus a dict of scalar metrics per case, the common shape of
    numeric simulations. The DataFrame golden is ``<case><df_suffix>``
    (CSV at fixed precision), the metrics golden is
    ``<case><metrics_suffix>`` (JSON); both compare through *matcher*
    with ``roundtrip=True``, so the tolerance table holds pure physics
    and storage rounding can never trip a tight tolerance.

    Usage::

        test_scenarios = golden_case_test(
            SCENARIOS_DIR,
            run_simulation,  # () -> {name: (df, metrics)}
            extractors=scenario_outputs(tolerance_matcher({"*_kw": 0.5})),
        )

    Args:
        matcher: Comparison hook for both files, typically
            :func:`~pytest_remaster.tolerance_matcher`.
        df_suffix: Suffix (and extractors key) of the DataFrame golden.
        metrics_suffix: Suffix of the metrics golden.
        float_format: Passed to :func:`dataframe_serializer`.
        index_col: Passed to :func:`dataframe_deserializer`.

    """
    return {
        df_suffix: Output(
            operator.itemgetter(0),
            serializer=dataframe_serializer(float_format),
            deserializer=dataframe_deserializer(index_col),
            matcher=matcher,
            roundtrip=True,
            name=lambda case: f"{case.input.name}{df_suffix}",
        ),
        metrics_suffix: Output(
            operator.itemgetter(1),
            serializer=json_serializer(),
            deserializer=json.loads,
            matcher=matcher,
            roundtrip=True,
            name=lambda case: f"{case.input.name}{metrics_suffix}",
        ),
    }
