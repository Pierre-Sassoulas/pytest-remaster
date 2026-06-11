"""Ready-made parametrized golden-master tests over case directories."""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from pytest_remaster.discovery import CaseData, discover_test_cases
from pytest_remaster.golden_master import GoldenMaster, Output


def golden_case_test(
    cases_dir: str | Path,
    runner: Callable[[], Mapping[str, Any]],
    *,
    extractors: dict[str, Callable[[Any], Any] | Output],
    serializer: Callable[[Any], str] = str,
    normalizer: Callable[[str], str] | None = None,
    deserializer: Callable[[str], Any] | None = None,
    matcher: Callable[[Any, Any], bool] | None = None,
    roundtrip: bool = False,
) -> Callable[[CaseData, GoldenMaster], None]:
    """Build a parametrized golden-master test over case directories.

    Assign the result to a ``test_*`` name at module level::

        test_scenarios = golden_case_test(
            Path(__file__).parent / "scenarios",
            run_validation_notebook,  # () -> {case_name: result}
            extractors={
                ".csv": Output(
                    lambda r: r.df,
                    serializer=dataframe_serializer(),
                    deserializer=dataframe_deserializer(),
                    matcher=tolerance_matcher(TOLERANCES),
                    roundtrip=True,
                    name=lambda case: f"{case.input.name}.csv",
                ),
            },
        )

    Each leaf directory under *cases_dir* becomes one pytest node, so a
    drifting case never hides failures in the others, and adding a case
    is adding a directory. *runner* computes every case's result, keyed
    by directory name, and runs at most once per process however many
    cases exist. Goldens live inside each case directory (default
    ``expected{suffix}``; use ``Output.name`` for ``<case>.csv``-style
    conventions). Within one case, every output is checked before a
    single aggregated failure (:meth:`GoldenMaster.collecting`). A
    directory with no entry in the runner's result fails with the list
    of names the runner did produce.

    The shared keyword arguments (*serializer*, *normalizer*,
    *deserializer*, *matcher*, *roundtrip*) are defaults for the
    extractors, exactly as in :meth:`GoldenMaster.check_each`.
    """
    cases_dir = Path(cases_dir)
    cached_runner = functools.cache(runner)

    @pytest.mark.parametrize("case", discover_test_cases(cases_dir))
    def test_golden_case(case: CaseData, golden_master: GoldenMaster) -> None:
        results = cached_runner()
        if (name := case.input.name) not in results:
            pytest.fail(
                f"runner produced no result for case '{name}' "
                f"(got: {sorted(results)}); the directories under "
                f"{cases_dir} drive the test list.",
                pytrace=False,
            )
        with golden_master.collecting():
            golden_master.check_each(
                case,
                runner=lambda c: results[c.input.name],
                extractors=extractors,
                serializer=serializer,
                normalizer=normalizer,
                deserializer=deserializer,
                matcher=matcher,
                roundtrip=roundtrip,
            )

    return test_golden_case
