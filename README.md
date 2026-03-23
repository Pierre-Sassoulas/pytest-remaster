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
        extractors={
            ".stdout": lambda r: r.out,
            ".stderr": lambda r: r.err,
        },
    )
```

All examples auto-update expected files on mismatch. Review the diff in git, rerun. Pass
`--no-remaster` for strict comparison.

### Patching with `FilePatchRegistry`

Autoload fixture files from case directories and patch mock targets:

```python
import pytest

from pytest_remaster import FilePatchRegistry, discover_test_cases
from pathlib import Path

from my_app import run_command

CASES_DIR = Path(__file__).parent / "cases"

patcher = FilePatchRegistry()
patcher.register("command", loader=str.strip)
patcher.register(
    "salt.json", target="pepper.Pepper", attr="return_value.low.side_effect"
)
patcher.register(
    "mywebapp.json",
    target="requests.get",
    attr="return_value.json.side_effect",
    default=[],
)
patcher.register("user.json", default={"name": "default"})


@pytest.mark.parametrize("case", discover_test_cases(CASES_DIR))
def test_command(case, golden_master):
    with patcher.mock(case) as loaded:
        events = run_command(loaded["command"], loaded["user.json"])
        golden_master.check_all(events, case.input)
```

Options: `target=None` (load only), `attr="return_value"` (nested mock attribute path),
`loader=json.loads`, `default=None`.
