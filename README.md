[![PyPI version](https://badge.fury.io/py/pytest-remaster.svg)](https://badge.fury.io/py/pytest-remaster)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytest-remaster)](https://pypi.org/project/pytest-remaster/)
[![PyPI - License](https://img.shields.io/pypi/l/pytest-remaster)](https://pypi.org/project/pytest-remaster/)

# pytest-remaster

Framework for golden master testing for pytest with automatic regeneration of the golden
master.

## Installation

```bash
pip install pytest-remaster
```

## Quick start

Create test case directories with input files and expected output files:

```
tests/cases/
  greet/hello/
    command          # input: "hello Alice"
    result_0         # expected: "[#general] :wave: Hello, Alice!"
  greet/goodbye/
    command          # input: "goodbye Bob"
    result_0         # expected: "[#general] :wave: Goodbye, Bob!"
    result_1         # expected: "[#general] :door: Bob has left the chat."
```

Write a parametrized test:

```python
from pathlib import Path

import pytest

from pytest_remaster import GoldenMaster, discover_test_cases

CASES_DIR = Path(__file__).parent / "cases"


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_command(case: Path, golden_master: GoldenMaster) -> None:
    cmd = (case / "command").read_text().strip()
    golden_master.check_all(lambda: run_command(cmd), directory=case)
```

`discover_test_cases` finds leaf directories and generates nice test IDs automatically
(e.g. `test_command[greet/hello]`).

## API

### `golden_master` fixture

**`check(actual, expected_path, serializer=str)`** — Compare one actual value (or
callable) against one expected file:

```python
golden_master.check(output, case / "expected.txt")
golden_master.check(data, case / "db.json", serializer=json.dumps)
golden_master.check(lambda: run(), case / "output.txt")
```

**`check_all(*actuals, directory, serializer=str)`** — Compare multiple values against
`result_0`, `result_1`, ... files in a directory:

```python
golden_master.check_all(*events, directory=case)
golden_master.check_all(lambda: run_command(cmd), directory=case)
```

### Discovery functions

**`discover_test_cases(base_dir)`** — Find leaf directories (directories containing only
files). Returns `pytest.param` objects with relative path IDs.

**`discover_test_files(base_dir, pattern)`** — Find files matching a glob pattern.
Returns `pytest.param` objects with relative path IDs.

### Behavior

- **`--remaster` (default)**: When output doesn't match, the expected file is updated
  and the test fails with _"please review and relaunch"_. Review the diff in git, then
  rerun.
- **`--no-remaster`**: When output doesn't match, the test fails with a unified diff. No
  files are modified.

The default can be changed in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
remaster-by-default = false
```
