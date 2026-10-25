#!/usr/bin/env python3
"""Publish the current local coverage run in marked README sections."""

import argparse
import configparser
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from urllib.parse import quote


BLOCKS = ("coverage-badges", "coverage-summary")
STATES = ("not-run", "passed", "failed")


def percentage(covered, total):
    if any(type(value) is not int for value in (covered, total)):
        raise ValueError("Coverage counters must be integers.")
    if total <= 0 or not 0 <= covered <= total:
        raise ValueError("Coverage counters are outside their valid range.")
    return covered / total * 100


def python_metrics(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["meta"]["branch_coverage"] is not True:
        raise ValueError("The Python report must include branches.")
    totals = data["totals"]
    statements = percentage(totals["covered_lines"], totals["num_statements"])
    branches = percentage(totals["covered_branches"], totals["num_branches"])
    combined = percentage(totals["covered_lines"] + totals["covered_branches"],
                          totals["num_statements"] + totals["num_branches"])
    return [combined, statements, branches]


def javascript_metrics(path):
    records = []
    record = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            if record is not None:
                raise ValueError("The LCOV record is incomplete.")
            record = {"source": line[3:].replace("\\", "/")}
        elif line == "end_of_record":
            if record is None:
                raise ValueError("The LCOV record has no source.")
            records.append(record)
            record = None
        elif record is not None:
            name, separator, value = line.partition(":")
            if separator and name in ("LF", "LH", "BRF", "BRH", "FNF", "FNH"):
                if name in record:
                    raise ValueError("The LCOV record has duplicate counters.")
                record[name] = int(value)
    if record is not None or len(records) != 1:
        raise ValueError("Expected one complete tools.js coverage record.")
    record = records[0]
    expected = Path("package/contents/tools/tools.js")
    source = Path(record["source"])
    if source != expected and source != (path.parent.parent / expected).resolve():
        raise ValueError("The LCOV source is outside the measured scope.")
    return [percentage(record[hit], record[found])
            for hit, found in (("LH", "LF"), ("BRH", "BRF"), ("FNH", "FNF"))]


def badge(label, value, passed):
    message = "unavailable" if value is None else f"{value:.2f}%"
    color = "lightgrey" if value is None else "brightgreen" if passed else "red"
    url = f"https://img.shields.io/badge/{quote(label)}-{quote(message)}-{color}?style=flat"
    return f"[![{label}: {message}]({url})](#coverage)"


def replace_blocks(text, blocks):
    newline = "\r\n" if "\r\n" in text else "\n"
    replacements = []
    for name, content in blocks.items():
        start = f"<!-- {name}:start -->"
        end = f"<!-- {name}:end -->"
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError(f"README needs one matching {name} marker pair.")
        first, last = text.index(start) + len(start), text.index(end)
        if first > last:
            raise ValueError(f"The {name} markers are reversed.")
        replacements.append((first, last, newline + content.replace("\n", newline) + newline))
    replacements.sort()
    if any(left[1] > right[0] for left, right in zip(replacements, replacements[1:])):
        raise ValueError("The README coverage sections overlap.")
    for first, last, content in reversed(replacements):
        text = text[:first] + content + text[last:]
    return text


def atomic_write(path, text):
    previous = path.read_bytes()
    updated = text.encode("utf-8")
    if updated == previous:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".README.coverage.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def update(root, exit_code, phase, python_status, javascript_status, javascript_thresholds, interrupted=False):
    configuration = configparser.ConfigParser()
    with (root / ".coveragerc").open(encoding="utf-8") as stream:
        configuration.read_file(stream)
    python_threshold = configuration.getfloat("report", "fail_under", fallback=0)
    precision = configuration.getint("report", "precision", fallback=0)
    if not 0 <= python_threshold <= 100 or not 0 <= precision <= 9:
        raise ValueError("The Python coverage threshold or precision is invalid.")
    if any(not 0 <= value <= 100 for value in javascript_thresholds):
        raise ValueError("The JavaScript coverage thresholds are invalid.")

    diagnostics = []
    results = []
    for name, status, path, loader in (
        ("Python", python_status, root / "coverage/python.json", python_metrics),
        ("JavaScript", javascript_status, root / "coverage/javascript.lcov", javascript_metrics),
    ):
        if status == "not-run":
            results.append([None] * 3)
            continue
        try:
            results.append(loader(path))
        except (OSError, ValueError, KeyError, TypeError):
            results.append([None] * 3)
            diagnostics.append(f"{name} coverage report is missing or invalid.")
    python, javascript = results
    # Match coverage.py's configured precision and its exact 100% requirement.
    python_passed = python[0] is not None and (
        python[0] == 100 if python_threshold == 100 else round(python[0], precision) >= python_threshold)
    javascript_passed = [value is not None and value >= minimum
                         for value, minimum in zip(javascript, javascript_thresholds)]
    complete = python_status != "not-run" and javascript_status != "not-run"
    passed = (exit_code == 0 and complete and python_status == javascript_status == "passed"
              and python_passed and all(javascript_passed) and not diagnostics)
    status = "INTERRUPTED" if interrupted else "NOT RUN" if phase == "preparation" else "PASSED" if passed else "FAILED"
    badges = "\n".join((badge("Python coverage", python[0], python_passed),
                        badge("JavaScript lines", javascript[0], javascript_passed[0])))
    lines = [f"Last coverage run: **{status}**.", "",
             f"Python checks: **{python_status.upper().replace('-', ' ')}**. "
             f"JavaScript checks: **{javascript_status.upper().replace('-', ' ')}**.", "",
             "| Metric | Coverage | Minimum | Coverage gate |",
             "| --- | ---: | ---: | --- |"]
    metrics = list(zip(("Python: statements and branches", "Python: statements", "Python: branches"),
                       python, (python_threshold, None, None), (python_passed, None, None)))
    metrics += list(zip(("JavaScript: lines", "JavaScript: branches", "JavaScript: functions"),
                        javascript, javascript_thresholds, javascript_passed))
    for label, value, minimum, met in metrics:
        display = "Unavailable" if value is None else f"{value:.2f}%"
        threshold = "Not gated" if minimum is None else f"{minimum:g}%"
        gate = "Not gated" if minimum is None else "Unavailable" if value is None else "PASS" if met else "FAIL"
        lines.append(f"| {label} | {display} | {threshold} | {gate} |")
    lines += ["", "Measured scope: `package/contents/tools/backends.py` and `package/contents/tools/tools.js`."]
    if phase == "preparation":
        lines += ["", "Environment preparation did not complete; no current coverage results are available."]
    if diagnostics:
        lines += ["", " ".join(diagnostics)]
    readme = root / "README.md"
    text = readme.read_bytes().decode("utf-8")
    atomic_write(readme, replace_blocks(text, dict(zip(BLOCKS, (badges, "\n".join(lines))))))
    return 0 if passed or exit_code != 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--phase", choices=("preparation", "python", "javascript", "complete"), required=True)
    parser.add_argument("--python-status", choices=STATES, required=True)
    parser.add_argument("--javascript-status", choices=STATES, required=True)
    parser.add_argument("--javascript-thresholds", type=float, nargs=3, required=True)
    parser.add_argument("--interrupted", action="store_true")
    args = parser.parse_args(argv)
    try:
        return update(args.root, args.exit_code, args.phase, args.python_status,
                      args.javascript_status, args.javascript_thresholds, args.interrupted)
    except (OSError, ValueError, configparser.Error) as error:
        print(f"Cannot update README coverage status: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
