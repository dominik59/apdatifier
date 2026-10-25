#!/usr/bin/env bash
set -eu

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
test_base_python="${APDATIFIER_TEST_PYTHON:-python3}"
test_venv="${APDATIFIER_TEST_VENV:-.venv}"
test_node="${APDATIFIER_TEST_NODE:-node}"
export PYTHONDONTWRITEBYTECODE=1

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

if ! "$test_python" -m pip --version >/dev/null 2>&1; then
    "$test_python" -m ensurepip --upgrade
fi
# The dry run checks the pinned dependencies without contacting a package index.
if ! "$test_python" -m pip install --dry-run --no-index --disable-pip-version-check \
        -r requirements-test.txt >/dev/null 2>&1; then
    "$test_python" -m pip install --disable-pip-version-check -r requirements-test.txt
fi

mkdir -p coverage
"$test_python" -m coverage erase
test_status=0
"$test_python" -m coverage run -m unittest discover -s tests -v || test_status=1
for report in html xml json report; do
    "$test_python" -m coverage "$report" || test_status=1
done

"$test_node" --test --experimental-test-coverage \
    --test-coverage-include=package/contents/tools/tools.js \
    --test-coverage-lines=80 --test-coverage-branches=70 --test-coverage-functions=70 \
    --test-reporter=spec --test-reporter-destination=stdout \
    --test-reporter=lcov --test-reporter-destination=coverage/javascript.lcov \
    tests/test_*.js || test_status=1
exit "$test_status"
