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

```python
import math

TOLERANCES = {"hz": 1e-3, "w_bess_kw": 0.5}


def within_tolerance(actual: dict[str, float], expected: dict[str, float]) -> bool:
    if actual.keys() != expected.keys():
        return False
    failures = [
        f"{key}: golden={expected[key]:.6g} actual={actual[key]:.6g} tol={tol:g}"
        for key, tol in ((k, TOLERANCES.get(k, 1e-6)) for k in expected)
        if not math.isclose(actual[key], expected[key], abs_tol=tol, rel_tol=1e-4)
    ]
    if failures:
        raise AssertionError("\n".join(failures))
    return True


def test_metrics(golden_master: GoldenMaster) -> None:
    metrics = run_simulation()
    golden_master.check(
        metrics,
        Path(__file__).parent / "goldens" / "nominal.metrics.json",
        serializer=lambda m: json.dumps(m, indent=2, sort_keys=True),
        deserializer=json.loads,
        matcher=within_tolerance,
    )
```

`matcher` is mutually exclusive with `normalizer` (they are alternative comparison
strategies), and `deserializer` requires `matcher`. Both are also accepted by
`check_all()` and `check_each()`.

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
