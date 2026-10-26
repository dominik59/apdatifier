#!/usr/bin/env bash
set -eu

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
test_base_python="${APDATIFIER_TEST_PYTHON:-python3}"
test_venv="${APDATIFIER_TEST_VENV:-.venv}"
test_node="${APDATIFIER_TEST_NODE:-node}"
export PYTHONDONTWRITEBYTECODE=1

test_report_python="$test_base_python"
test_phase=preparation
test_python_status=not-run
test_javascript_status=not-run
test_bash_status=not-run
test_interrupted=false
test_javascript_lines=80
test_javascript_branches=70
test_javascript_functions=70

update_readme() {
    local test_exit_status=$?
    trap - EXIT INT TERM
    set +e
    local test_report_flags=()
    [[ "$test_interrupted" == true ]] && test_report_flags+=(--interrupted)
    "$test_report_python" tests/update_coverage_readme.py \
        --exit-code "$test_exit_status" --phase "$test_phase" \
        --python-status "$test_python_status" --javascript-status "$test_javascript_status" \
        --bash-status "$test_bash_status" \
        --javascript-thresholds "$test_javascript_lines" "$test_javascript_branches" "$test_javascript_functions" \
        "${test_report_flags[@]}"
    local test_report_status=$?
    if [[ "$test_report_status" -ne 0 ]]; then
        printf 'README coverage status could not be fully updated.\n' >&2
        [[ "$test_exit_status" -eq 0 ]] && test_exit_status=1
    fi
    exit "$test_exit_status"
}
trap update_readme EXIT
trap 'test_interrupted=true; exit 130' INT
trap 'test_interrupted=true; exit 143' TERM

# Only reports produced by this invocation may be published in the README.
mkdir -p coverage
rm -f -- coverage/python.json coverage/javascript.lcov coverage/bash.json coverage/bash.lcov
test_bash_trace="$PWD/coverage/bash-traces"
rm -rf -- "$test_bash_trace"
mkdir -p -- "$test_bash_trace"

"$test_node" -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 8)) { console.error("Coverage needs Node.js 22.8 or later."); process.exit(2); }'

if [[ ! -e "$test_venv" ]]; then
    "$test_base_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Coverage needs Python 3.11 or later.")'
    printf 'Creating development virtual environment: %s\n' "$test_venv"
    "$test_base_python" -m venv "$test_venv"
fi

test_python="$test_venv/bin/python"
if [[ ! -x "$test_python" || ! -f "$test_venv/pyvenv.cfg" ]]; then
    printf 'The existing environment at %s is incomplete. Choose another APDATIFIER_TEST_VENV or repair it.\n' "$test_venv" >&2
    exit 2
fi
"$test_python" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix and sys.version_info >= (3, 11) else "Coverage needs a Python 3.11+ virtual environment.")'
test_report_python="$test_python"

if ! "$test_python" -m pip --version >/dev/null 2>&1; then
    "$test_python" -m ensurepip --upgrade
fi
# The dry run checks the pinned dependencies without contacting a package index.
if ! "$test_python" -m pip install --dry-run --no-index --disable-pip-version-check \
        -r requirements-test.txt >/dev/null 2>&1; then
    "$test_python" -m pip install --disable-pip-version-check -r requirements-test.txt
fi

"$test_python" -m coverage erase
test_status=0
test_phase=python
test_python_status=failed
if APDATIFIER_BASH_COVERAGE_DIR="$test_bash_trace" BASH_ENV="$PWD/tests/bash_coverage.sh" \
        "$test_python" -m coverage run -m unittest discover -s tests -v; then
    test_python_status=passed
else
    test_status=1
fi
for report in html xml json report; do
    if ! "$test_python" -m coverage "$report"; then
        test_python_status=failed
        test_status=1
    fi
done

test_phase=bash
test_bash_status=failed
if "$test_python" tests/bash_coverage.py --trace-dir "$test_bash_trace"; then
    test_bash_status=passed
else
    test_status=1
fi

test_phase=javascript
test_javascript_status=failed
if "$test_node" --test --experimental-test-coverage \
    --test-coverage-include=package/contents/tools/tools.js \
    --test-coverage-lines="$test_javascript_lines" \
    --test-coverage-branches="$test_javascript_branches" --test-coverage-functions="$test_javascript_functions" \
    --test-reporter=spec --test-reporter-destination=stdout \
    --test-reporter=lcov --test-reporter-destination=coverage/javascript.lcov \
    tests/test_*.js; then
    test_javascript_status=passed
else
    test_status=1
fi
test_phase=complete
exit "$test_status"
