# Development checks

[Back to README](../README.md)

Run commands from the repository root. Node.js and coverage.py are development
tools; the installed application's APT and Snap helpers use only the Python
standard library.

## Coverage

You need Python 3.11 or later with venv support and Node.js 22.8 or later.
Run both suites with one command:

```bash
./tests/run_coverage.sh
```

The script creates `.venv` when absent and installs pinned development
dependencies from [requirements-test.txt](../requirements-test.txt). It selects
that environment's Python automatically. Later runs reuse the environment and
check installed requirements without an index request. Missing or changed
requirements trigger installation inside that environment.

An incomplete existing environment produces an error and remains unchanged.
No manual activation or global pip installation is needed.

| Setting | Purpose |
| --- | --- |
| `APDATIFIER_TEST_PYTHON` | Python interpreter used to create the environment |
| `APDATIFIER_TEST_VENV` | Alternative environment directory |
| `APDATIFIER_TEST_NODE` | Node.js executable for the test runner |

Python coverage uses coverage.py. JavaScript coverage uses the built-in Node.js
test runner and V8; no npm package is required.

## README status

Each invocation updates the [README badges and table](../README.md#coverage)
from that run's Python JSON and JavaScript LCOV reports. Failed checks retain a
failed run status even when measured coverage is high. Missing or invalid
reports show unavailable results, rather than earlier percentages.

The updater distinguishes passed, failed, not-run, and interrupted states.
Its exit handler handles normal exits and SIGINT or SIGTERM. Publication
requires an available Python interpreter and a writable README; forced
termination that bypasses exit handlers cannot publish a new status.

The generator replaces only the contents of these marker pairs:

```html
<!-- coverage-badges:start -->
<!-- coverage-badges:end -->

<!-- coverage-summary:start -->
<!-- coverage-summary:end -->
```

Keep each pair unique and preserve the README `#coverage` anchor when editing
documentation. Other README content remains unchanged. Identical results do not
rewrite the file. Invalid markers produce an error without overwriting user text.

The summary includes test execution, report generation, and coverage gates.
The badge colors describe coverage gates; the overall run status appears
separately. Badge images use Shields URLs. Report generation does not contact
Shields or upload reports to an external coverage service.

Commit and push README to publish changed results on GitHub. The coverage
command does not create commits or push changes.

## Reports and thresholds

The script writes these ignored reports, with paths relative to the repository root:

| Report | Location |
| --- | --- |
| Python HTML, including missing lines and branches | `coverage/python/index.html` |
| Python XML | `coverage/python.xml` |
| Python JSON | `coverage/python.json` |
| JavaScript LCOV | `coverage/javascript.lcov` |
| Test results and coverage summaries | Terminal output and GitHub Actions logs |

[.coveragerc](../.coveragerc) enforces 80% combined statement and branch coverage
for `package/contents/tools/backends.py`. JavaScript requires 80% lines, 70%
branches, and 70% functions for the complete `package/contents/tools/tools.js`.
Either gate can fail the command. Menu and CLI code are included in the measurement.

The percentages cover the Python helper and JavaScript application logic.
Bash line coverage and QML execution coverage are not measured. The Python suite
does test Bash operations through substitute commands and local archives.

## Individual checks

No additional Python modules are needed for the unit tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --test tests/test_*.js
python3 -B tests/check_qml.py
```

The optional QML check uses an existing PyQt6 installation and skips when the
development binding is absent. It compiles components without creating a live
applet. Compilation does not verify interactive desktop behavior.

Native APT regression fixtures use temporary local repositories and simulation.
They do not install or remove host packages. Snap API tests use a temporary Unix
socket. Some restricted environments need permission for local sockets, HTTP
servers, or child processes to run these cases.

Widget tests use local tar.xz and ZIP archives with substitute downloads and
installers. They cover missing tools, invalid packages, HTTP errors, installer
failures, and partial batch failures without installing live widgets.

Shell tests disconnect child standard input so terminal prompts do not block the
suite. A regression test uses a pseudoterminal to verify this behavior when a
developer starts the suite from an interactive terminal.

## Continuous integration and acceptance

The [test workflow](../.github/workflows/tests.yml) selects Python 3.12 and 3.14
with Node.js 24. It uploads coverage reports after success or failure.
The [release workflow](../.github/workflows/build.yml) uses the same coverage
command before packaging.

Full desktop, package-manager, and distribution acceptance remains separate.
Real privileged APT and Snap operations require acceptance in approved disposable
systems before complete platform support can be claimed.

The [change request](change-request/2026-10-25_CHANGE_REQUEST_APT_SNAP.md) records the implementation,
acceptance criteria, local evidence, and open verification work.
