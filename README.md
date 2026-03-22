[![PyPI version](https://badge.fury.io/py/pytest-remaster.svg)](https://badge.fury.io/py/pytest-remaster)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytest-remaster)](https://pypi.org/project/pytest-remaster/)
[![PyPI - License](https://img.shields.io/pypi/l/pytest-remaster)](https://pypi.org/project/pytest-remaster/)

# pytest-remaster

Pytest plugin for golden master (characterisation) testing with automatic expected file
regeneration.

## Example 1: directory per test case

Each test case is a directory with input files and numbered expected outputs:

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
from pytest_remaster import CaseData, GoldenMaster, discover_test_cases

CASES_DIR = Path(__file__).parent / "cases"

@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_command(case: CaseData, golden_master: GoldenMaster) -> None:
    cmd = (case.input / "command").read_text().strip()
    golden_master.check_all(lambda: my_app(cmd), case.input, suffix=".txt")
```

## Example 2: one file per test case

Each test case is a source file, with expected output derived from the filename:

```
tests/functional/
  arguments.py          # input (source to lint)
  arguments.txt         # expected output
  anomalous.py
  anomalous.txt
```

```python
import pytest
from pytest_remaster import CaseData, GoldenMaster, discover_test_files

FUNC_DIR = Path(__file__).parent / "functional"

@pytest.mark.parametrize("case", discover_test_files(FUNC_DIR, "*.py"))
def test_lint(case: CaseData, golden_master: GoldenMaster) -> None:
    golden_master.check(lambda: lint(case.input), case.expected(suffix=".txt"))
```

Both examples auto-update expected files on mismatch. Review the diff in git, rerun.
Pass `--no-remaster` for strict comparison.

## API

### `golden_master.check(actual, expected_path)`

Compare one value against one expected file:

```python
golden_master.check(output, case.expected(suffix=".txt"))
golden_master.check(data, path / "db.json", normalizer=json_normalizer)
```

Options: `serializer=str`, `normalizer=None`.

### `golden_master.check_all(actuals, directory)`

Compare a list against `expected_0`, `expected_1`, ... files in a directory:

```python
golden_master.check_all(lambda: my_app(cmd), case.input, suffix=".txt")
```

Options: `serializer=str`, `normalizer=None`, `suffix=""`.

### Discovery

```python
discover_test_cases(base_dir)               # leaf directories → CaseData
discover_test_files(base_dir, "*.py")       # files by pattern → CaseData
```

`CaseData.input` is the source path. `CaseData.expected(index, suffix)` derives expected
file paths.

### `FilePatchRegistry`

Auto-load fixture files from case directories and patch mock targets:

```python
from pytest_remaster import FilePatchRegistry

patcher = FilePatchRegistry()
patcher.register("command", loader=str.strip)
patcher.register("salt.json", target="pepper.Pepper", attr="return_value.low.side_effect")
patcher.register("tiger.json", target="requests.get", attr="return_value.json.side_effect", default=[])
patcher.register("user.json", default={"name": "default"})

@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_command(case, golden_master):
    with patcher.mock(case) as loaded:
        events = run_command(loaded["command"], loaded["user.json"])
        golden_master.check_all(events, case.input)
```

Options: `target=None` (load only), `attr="return_value"` (nested mock attribute path),
`loader=json.loads`, `default=None`.

## Configuration

```toml
[tool.pytest.ini_options]
remaster-by-default = false  # default: true
```
