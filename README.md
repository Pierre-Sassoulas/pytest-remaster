[![PyPI version](https://badge.fury.io/py/pytest-remaster.svg)](https://badge.fury.io/py/pytest-remaster)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytest-remaster)](https://pypi.org/project/pytest-remaster/)
[![PyPI - License](https://img.shields.io/pypi/l/pytest-remaster)](https://pypi.org/project/pytest-remaster/)

# pytest-remaster

Pytest plugin for golden master (characterization) testing with automatic expected file
regeneration.

## Installation

```bash
pip install pytest-remaster
```

## Configuration

```toml
[tool.pytest.ini_options]
remaster-by-default = false  # default: true
```

## Example 1: directory per test case

`discover_test_cases(base_dir)` finds leaf directories and returns `CaseData` with
`.input` pointing to each directory. Each test case has input files and numbered
expected outputs:

```
tests/cases/
  greet/hello/
    command             # input
    expected_0.txt      # first expected output
  help/unknown/
    command
    expected_0.txt
    expected_1.txt      # multiple outputs supported
```

```python
import pytest
from pathlib import Path
from pytest_remaster import CaseData, GoldenMaster, discover_test_cases

CASES_DIR = Path(__file__).parent / "cases"


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_command(case: CaseData, golden_master: GoldenMaster) -> None:
    cmd = (case.input / "command").read_text().strip()
    golden_master.check_all(lambda: my_app(cmd), case.input, suffix=".txt")
```

## Example 2: one file per test case

`discover_test_files(base_dir, pattern)` finds files matching a glob and returns
`CaseData` with `.input` pointing to each file. Expected output is derived from the
filename:

```
tests/functional/
  arguments.py          # input (source to lint)
  arguments.txt         # expected output
  anomalous.py
  anomalous.txt
```

```python
import pytest
from pathlib import Path
from pytest_remaster import CaseData, GoldenMaster, discover_test_files

from my_linter import lint

FUNC_DIR = Path(__file__).parent / "functional"


@pytest.mark.parametrize("case", discover_test_files(FUNC_DIR, "*.py"))
def test_lint(case: CaseData, golden_master: GoldenMaster) -> None:
    golden_master.check(lambda: lint(case.input), case.expected(suffix=".txt"))
```

## Example 3: capture stdout and stderr

Run a CLI in-process and golden-master each output stream with `check_each`:

```
tests/cases/
  greet/
    command             # input: "greet Alice"
    expected.stdout     # expected stdout
  divide-by-zero/
    command
    expected.stderr     # only present when stderr is non-empty
```

```python
import pytest
from pathlib import Path

from my_app import main

from pytest_remaster import CaseData, GoldenMaster, discover_test_cases

CASES_DIR = Path(__file__).parent / "cases"


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_cli(
    case: CaseData, golden_master: GoldenMaster, capsys: pytest.CaptureFixture[str]
) -> None:
    def run(case: CaseData) -> pytest.CaptureResult[str]:
        cmd = (case.input / "command").read_text().strip()
        main(cmd)
        return capsys.readouterr()

    golden_master.check_each(
        case,
        runner=run,
        extractors={".stdout": lambda r: r.out, ".stderr": lambda r: r.err},
    )
```

All examples auto-update expected files on mismatch. Review the diff in git, rerun. Pass
`--no-remaster` for strict comparison.

## Numeric tolerance with `matcher` and `deserializer`

When outputs contain floats, exact string comparison churns the golden files on every
solver/float noise. Replace string equality with a comparison on deserialized values:

- `serializer` still controls what is written to the golden file (e.g. fixed `%.6g`
  precision, human-reviewable);
- `deserializer` parses the golden file text back into a value;
- `matcher(actual_value, expected_value)` decides equality — e.g. `np.isclose` with a
  per-quantity tolerance. Within tolerance, the golden file is never rewritten, even in
  remaster mode. Beyond tolerance, `--remaster` re-blesses the golden as usual.

A matcher may raise `AssertionError` instead of returning `False`; its message replaces
the string diff in the failure output (e.g. to report exactly which column/row moved and
by how much).

The built-in `tolerance_matcher` covers the common case — per-key absolute tolerances
with `fnmatch` patterns, recursing through mappings and sequences (e.g. column →
series), reporting every value beyond tolerance:

```python
from pytest_remaster import GoldenMaster, tolerance_matcher

MATCHER = tolerance_matcher({"hz": 1e-3, "*_kw": 0.5, "*_kvar": 1.0, "soc_pct": 0.1})


def test_metrics(golden_master: GoldenMaster) -> None:
    metrics = run_simulation()
    golden_master.check(
        metrics,
        Path(__file__).parent / "goldens" / "nominal.metrics.json",
        serializer=json_serializer(),  # indent=2, sort_keys=True
        deserializer=json.loads,
        matcher=MATCHER,
        roundtrip=True,
    )
```

Keys resolve exact-match first, then `fnmatch` patterns in declaration order, then
`default` (0.0 — exact). A table value is an absolute tolerance, or a
`Tolerance(atol=..., rtol=...)` when a wide-range quantity needs a relative tolerance
alongside purely absolute keys (e.g.
`{"soc_pct": 0.1, "*_kw": Tolerance(atol=0.5, rtol=1e-3)}`). `Tolerance` is a
`NamedTuple`, so a bare `(atol, rtol)` pair is accepted too; `rel=` sets the relative
tolerance for bare-float entries (a `Tolerance`/pair opts out of it — its `rtol` is
exactly what it says). Non-numeric values compare with equality. Failures read
`key[row]: golden=… actual=… |Δ|=… tol=…`, capped per sequence by `report_limit=5` and
overall by `total_limit=` (unlimited by default). NaN compares equal to NaN by default
(a reproduced gap in a time series is a match) and never equal to a number; pass
`nan_equal=False` for raw `math.isclose` behavior.

Two mechanisms keep storage precision out of the tolerance table (no `rtol` fudge factor
needed to absorb the write→parse rounding of the golden file):

- If the serialized actual equals the golden file text, the values match without
  consulting the matcher — an unchanged run can never trip a tight tolerance.
- `roundtrip=True` passes `deserializer(serializer(actual))` to the matcher instead of
  the raw value, so both sides carry the storage precision and a reported failure can be
  reproduced from the committed golden plus the printed actual alone.

`matcher` is mutually exclusive with `normalizer` (they are alternative comparison
strategies), `deserializer` requires `matcher`, and `roundtrip` requires both. All are
also accepted by `check_all()` and `check_each()`.

### DataFrame goldens with the `pandas` extra

`pip install pytest-remaster[pandas]` adds the serializer/deserializer pair every
numeric consumer otherwise rewrites — CSV at fixed precision out, column → series
mapping back in (the shape `tolerance_matcher` recurses natively):

```python
from pytest_remaster import dataframe_deserializer, dataframe_serializer

golden_master.check(
    df,  # pandas DataFrame
    golden_dir / "nominal.csv",
    serializer=dataframe_serializer(),  # to_csv, float_format="%.6g"
    deserializer=dataframe_deserializer(),  # read_csv → to_dict("list")
    matcher=tolerance_matcher({"hz": 1e-3, "*_kw": 0.5}),
    roundtrip=True,
)
```

`dataframe_serializer(float_format=...)` and `dataframe_deserializer(index_col=...)`
parametrize precision and index handling. The core package stays stdlib-pure: the
helpers import pandas only when first used.

**Index footgun:** with the default `index_col=0` the index is _excluded_ from
comparison — a time axis that shifts while values stay identical passes silently. To
compare it, name the index (`df.index.name = "t_s"`) and pass
`dataframe_deserializer(index_col=None)`: the index then round-trips as a regular `t_s`
column and gets its own tolerance key. An unnamed index under `index_col=None` appears
as an `Unnamed: 0` column with the default tolerance — name it instead.

### Heterogeneous outputs with `Output`

When one run produces outputs needing different serialization — a CSV time series next
to JSON metrics — give `check_each` a per-suffix `Output` spec instead of a bare
extractor:

```python
from pytest_remaster import Output, json_serializer

golden_master.check_each(
    case,
    runner=run_scenario,
    extractors={
        ".csv": Output(
            lambda r: r.df,
            serializer=dataframe_serializer(),
            deserializer=dataframe_deserializer(),
            matcher=tolerance_matcher(TOLERANCES),
            roundtrip=True,
            name=lambda case: f"{case.input.name}.csv",  # default: expected.csv
        ),
        ".metrics.json": Output(
            lambda r: r.metrics,
            serializer=json_serializer(),
            deserializer=json.loads,
            matcher=tolerance_matcher(TOLERANCES),
            roundtrip=True,
        ),
        ".stdout": lambda r: r.out,  # bare callables still work
    },
)
```

`serializer` and `name` fall back individually to the shared keyword arguments. The
comparison fields (`normalizer`, `deserializer`, `matcher`, `roundtrip`) inherit as a
unit: an `Output` that sets any of them replaces the shared comparison entirely.

## Collecting failures across multiple checks

Without `--remaster`, the first mismatching `check()` fails the test immediately and
hides the remaining comparisons. When one expensive run produces many files to check,
wrap the checks in `collecting()` to run them all and get a single failure listing every
mismatch:

```python
def test_scenarios(golden_master: GoldenMaster) -> None:
    results = run_expensive_simulation()
    with golden_master.collecting():
        for name, (df, metrics) in results.items():
            golden_master.check(df, GOLDEN_DIR / f"{name}.csv", ...)
            golden_master.check(metrics, GOLDEN_DIR / f"{name}.metrics.json", ...)
```

Remaster mode is unaffected: it already aggregates, updating every file and reporting
them all at fixture teardown.

## Version-specific expected files with `dimensions`

When expected output varies by Python version, platform, or implementation, use
`dimensions` to let pytest-remaster resolve the right file automatically.

### How it works

Given a base file and a set of dimensions, `check()` generates a priority-ordered chain
of override paths and uses the most specific existing file for comparison. Remastering
writes to the most specific path, keeping less specific files untouched. Redundant
overrides (identical to a less specific file) are deleted automatically.

```
tests/functional/
  arguments.py                # source to lint
  arguments.txt               # generic expected output
  arguments.312.txt           # Python 3.12 override
  arguments.312.linux.txt     # Python 3.12 on Linux
```

The resolution chain for `dimensions={"version": "312", "platform": "linux"}`:

1. `arguments.312.linux.txt` (most specific)
2. `arguments.312.txt` (version only)
3. `arguments.linux.txt` (platform only)
4. `arguments.txt` (generic base)

The first existing file is used for comparison. If none match, the base is used.

### Example: linter with version-dependent output

```python
import sys

import pytest
from pathlib import Path

from my_linter import lint

from pytest_remaster import CaseData, GoldenMaster, discover_test_files

FUNC_DIR = Path(__file__).parent / "functional"


@pytest.mark.parametrize("case", discover_test_files(FUNC_DIR, "*.py"))
def test_lint(case: CaseData, golden_master: GoldenMaster) -> None:
    actual = lint(case.input)
    golden_master.check(
        actual,
        case.expected(suffix=".txt"),
        dimensions={
            "version": f"{sys.version_info[0]}{sys.version_info[1]}",
            "platform": sys.platform,
        },
    )
```

On mismatch, `--remaster` creates the most specific override (e.g.
`arguments.312.linux.txt`). If the new file is identical to a less specific one (e.g.
`arguments.312.txt`), it is removed as redundant. This way, only the files that truly
differ between environments are kept.

### Input file resolution with `resolve_with_override`

`resolve_with_override(base, override)` returns `override` if it exists on disk,
otherwise `base`. Useful for resolving input files (e.g. config files) that follow the
same override pattern but are never remastered:

```python
from pytest_remaster import resolve_with_override

rc_file = resolve_with_override("test.rc", override="test.312.rc")
```

### Patching with `PatchRegistry`

Load fixture files and set up mock patches:

```python
import pytest
from pathlib import Path

from my_app import run_command

from pytest_remaster import PatchRegistry, discover_test_cases

CASES_DIR = Path(__file__).parent / "cases"

patcher = PatchRegistry()
patcher.add_file_patch("command", loader=str.strip)
patcher.add_file_patch(
    "salt.json", target="pepper.Pepper", attr="return_value.low.side_effect"
)
patcher.add_file_patch("user.json", default={"name": "default"})
patcher.add_patch("subprocess.run")


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_command(case, golden_master):
    with patcher.mock(case) as ctx:
        events = run_command(ctx["command"], ctx["user.json"])
        golden_master.check_all(events, case.input)
```

`add_file_patch(filename)`: load a file from the case directory, optionally patch a
target. Options: `target`, `attr="return_value"`, `loader=json.loads`, `default=None`.

`add_patch(target)`: patch a target without loading a file. The mock object is available
in the context dict. Options: `name` (dict key, defaults to target), `**kwargs` passed
to `unittest.mock.patch`.
