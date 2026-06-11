"""Pandas serialization helpers for numeric golden masters.

Requires the ``pandas`` extra: ``pip install pytest-remaster[pandas]``.
The helpers pair with ``tolerance_matcher`` and ``roundtrip=True``:
the serializer writes a human-reviewable CSV at fixed precision, the
deserializer parses it back into the column → series mapping that
``tolerance_matcher`` recurses natively.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Hashable
from typing import Any

import pandas as pd


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
