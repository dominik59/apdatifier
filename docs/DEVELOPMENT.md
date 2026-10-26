# Development checks

[Back to README](../README.md)

Run commands from the repository root. Node.js, coverage.py, and the Tree-sitter
parsers are development tools; the installed application's APT and Snap helpers use only the Python
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
test runner and V8; no npm package is required. Bash coverage uses Bash's DEBUG
trace and the pinned Tree-sitter Python packages installed in the same `.venv`.
It does not require Ruby, kcov, or a change to installed application dependencies.

## README status

Each invocation updates the [README badges and table](../README.md#coverage)
from that run's Python JSON, JavaScript LCOV, and Bash JSON reports. Failed checks retain a
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
| Bash HTML with source lines and hit counts | `coverage/bash/index.html` |
| Bash JSON | `coverage/bash.json` |
| Bash LCOV | `coverage/bash.lcov` |
| Test results and coverage summaries | Terminal output |

[.coveragerc](../.coveragerc) enforces 80% combined statement and branch coverage
for `package/contents/tools/backends.py`. JavaScript requires 80% lines, 70%
branches, and 70% functions for the complete `package/contents/tools/tools.js`.
Either gate can fail the command. Menu and CLI code are included in the measurement.

The percentages cover the Python helper, JavaScript application logic, and every
Bash script in `package/contents/tools/sh`. The `messages` translation resource
and `widgets-id` identifier list are data and are excluded from Bash coverage. Unexecuted
scripts remain in the Bash denominator. Bash coverage is informational, with no
minimum threshold; a missing or invalid measurement still fails the command.
Its badge is blue to distinguish it from the Python and JavaScript coverage gates.

QML execution coverage is not measured. The Python suite tests Bash operations
through substitute commands and local archives.

## Bash measurement

The runner enables a test-only `BASH_ENV` hook for the Python suite. Bash's
DEBUG trap records source locations, including sourced files, functions, and
subshells. Tree-sitter identifies command lines without counting comments,
function declarations, continuation-only lines, or heredoc text as commands.
This is line coverage, not branch coverage: two commands on one line do not
provide separate branch results.

The hook writes locations and source snapshots to `coverage/bash-traces`.
It does not record expanded commands or arguments. Temporary fixture copies
contribute hits only when their names and source bytes match current application
scripts. Modified copies are excluded. The README updater checks source hashes,
file completeness, and counters before publishing the result.

Every invocation clears earlier Bash reports and traces. Reporting still runs
when tests fail, and independent JavaScript checks continue if Bash reporting
fails. Reports stay local; no upload is required.

References: [Bash startup files](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html),
[Bash trap builtin](https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html),
and [Tree-sitter Python bindings](https://tree-sitter.github.io/py-tree-sitter/).

## Individual checks

The standard helper tests need no additional Python modules. Bash collector tests
use the pinned development parsers and skip when those parsers are absent:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --test tests/test_*.js
python3 -B tests/check_qml.py
```

The optional QML check uses an existing PyQt6 installation and skips when the
development binding is absent. It compiles components without creating a live
applet. Compilation does not verify interactive desktop behavior.

The Python suite also checks delayed callbacks with the system Python's existing
PyQt6 binding. These two tests skip if that binding is absent. They create a small,
isolated QML object and verify completion without a visual parent and after
reparenting. They do not create a live applet or execute package commands.

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

## Local checks and acceptance

Run `./tests/run_coverage.sh` locally before sharing changes. The owner removed
the GitHub Actions test and release workflows. Coverage reports remain local,
and README results are published through an explicit commit and push.

Full desktop, package-manager, and distribution acceptance remains separate.
Real privileged APT and Snap operations require acceptance in approved disposable
systems before complete platform support can be claimed.

The [change request](change-request/2026-10-25_CHANGE_REQUEST_APT_SNAP.md) records the implementation,
acceptance criteria, local evidence, and open verification work.
