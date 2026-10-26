#!/usr/bin/env python3
"""Report Bash line coverage from DEBUG locations and Tree-sitter syntax trees.

Only byte-identical source snapshots can contribute hits to project files.
This includes temporary copies used by the terminal fixtures. Modified copies,
test programs, configuration files, and the messages data resource cannot.
"""

import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
import sys


SCOPE = "package/contents/tools/sh"
MINIMUM = 80
EXECUTABLE_NODES = {
    "command", "declaration_command", "variable_assignment", "test_command",
    "arithmetic_command", "for_statement", "c_style_for_statement", "case_statement",
}


def sources(root):
    directory = root / SCOPE
    return sorted(path for path in directory.rglob('*')
                  if path.is_file() and path not in (directory / 'messages', directory / 'widgets-id')
                  and re.match(rb"#![^\n]*\b(?:bash|sh)\b", path.read_bytes()))


def passes(covered, total):
    return (type(covered) is int and type(total) is int and total > 0
            and 0 <= covered <= total and 100 * covered >= MINIMUM * total)


def validate(root, report):
    """Validate the full denominator against the same bytes used for the hash."""
    if (not isinstance(report, dict) or type(report.get('schemaVersion')) is not int
            or report['schemaVersion'] != 1 or report.get('scope') != SCOPE):
        raise ValueError('The Bash report has an unknown schema or scope.')
    expected = {path.relative_to(root).as_posix(): path for path in sources(root)}
    if not expected or not isinstance(report.get('files'), list):
        raise ValueError('The Bash source scope is empty or invalid.')
    seen = set()
    covered_sum = total_sum = 0
    for record in report['files']:
        if not isinstance(record, dict):
            raise ValueError('The Bash source record is invalid.')
        name = record['path']
        if name not in expected or name in seen:
            raise ValueError(f'{name}: duplicate or unexpected Bash source.')
        seen.add(name)
        contents = expected[name].read_bytes()
        if record['sha256'] != hashlib.sha256(contents).hexdigest():
            raise ValueError(f'{name}: the source hash is obsolete.')
        keys = {str(line) for line in executable_lines(contents)}
        counts = record['lines']
        if not isinstance(counts, dict) or set(counts) != keys:
            raise ValueError(f'{name}: executable line set is incomplete or contains nonexecutable lines.')
        if not keys or any(type(hit) is not int or hit < 0 for hit in counts.values()):
            raise ValueError(f'{name}: invalid or empty Bash line counters.')
        covered, total = sum(hit > 0 for hit in counts.values()), len(keys)
        if (type(record['covered']) is not int or type(record['total']) is not int
                or (record['covered'], record['total']) != (covered, total)):
            raise ValueError(f'{name}: file totals do not match line counters.')
        covered_sum += covered
        total_sum += total
    if (seen != set(expected) or type(report['covered']) is not int or type(report['total']) is not int
            or (report['covered'], report['total']) != (covered_sum, total_sum)):
        raise ValueError('The Bash report omits sources or has inconsistent totals.')
    return report


def executable_lines(contents):
    # The parser is a development dependency, never imported by the applet.
    from tree_sitter import Language, Parser
    import tree_sitter_bash

    language = Language(tree_sitter_bash.language())
    parser = Parser(language)
    # The grammar rejects ${value:$index:1}, which Bash accepts. Removing the
    # optional dollar preserves command structure; padding keeps byte offsets.
    parsed = re.sub(rb"\$\{\w+:\$\w+:\d+\}",
                    lambda match: match[0].replace(b":$", b":", 1) + b" ", contents)
    tree = parser.parse(parsed)
    if tree.root_node.has_error:
        raise ValueError("The Bash parser rejected a source file.")
    lines = set()
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type in EXECUTABLE_NODES:
            # Prefix assignments belong to their command, not separate commands.
            if node.type != "variable_assignment" or node.parent.type not in ("command", "declaration_command"):
                lines.add(contents.count(b"\n", 0, node.start_byte) + 1)
        pending.extend(node.named_children)
    return lines


def read_trace(directory):
    snapshots = {}
    hits = Counter()
    for path in sorted(directory.glob("trace-*")):
        fields = path.read_bytes().split(b"\0")
        if fields[-1] or (len(fields) - 1) % 3:
            raise ValueError("A Bash trace is incomplete.")
        for index in range(0, len(fields) - 1, 3):
            kind, source, value = fields[index:index + 3]
            if kind == b"S":
                if source in snapshots and snapshots[source] != value:
                    raise ValueError("A Bash source changed during collection.")
                snapshots[source] = value
            elif kind == b"L" and value.isdigit() and int(value) > 0:
                hits[source, int(value)] += 1
            else:
                raise ValueError("A Bash trace record is invalid.")
    return snapshots, hits


def collect(root, directory):
    source_paths = sources(root)
    if not source_paths:
        raise ValueError("The Bash source scope is empty.")
    snapshots, traced = read_trace(directory)
    files = []
    matched_hits = 0
    for path in source_paths:
        contents = path.read_bytes()
        statements = executable_lines(contents)
        relative = path.relative_to(root / SCOPE).as_posix()
        aliases = {source for source, snapshot in snapshots.items()
                   if source.decode().partition('/contents/tools/sh/')[2] == relative
                   and snapshot == contents.rstrip(b"\n")}
        hits = Counter()
        for (source, line), count in traced.items():
            if source in aliases and line in statements:
                hits[line] += count
        matched_hits += sum(hits.values())
        files.append(dict(path=path.relative_to(root).as_posix(), sha256=hashlib.sha256(contents).hexdigest(),
                          lines={str(line): hits[line] for line in sorted(statements)},
                          covered=sum(hits[line] > 0 for line in statements), total=len(statements)))
    if not matched_hits:
        raise ValueError("No Bash execution matched the current project sources.")
    return validate(root, dict(schemaVersion=1, scope=SCOPE, measurement="Bash DEBUG command lines",
                              files=files, covered=sum(file["covered"] for file in files),
                              total=sum(file["total"] for file in files)))


def write_reports(root, report):
    output = root / "coverage"
    output.mkdir(exist_ok=True)
    (output / "bash.json").write_text(json.dumps(report, indent=2) + "\n")
    lcov = []
    sections = []
    print(f"Bash command-line coverage (minimum {MINIMUM}% for each file):")
    for file in report["files"]:
        lcov += ["SF:" + file["path"], *(f"DA:{line},{count}" for line, count in file["lines"].items()),
                 "LF:" + str(file["total"]), "LH:" + str(file["covered"]), "end_of_record"]
        percent = file["covered"] / file["total"] * 100 if file["total"] else 0
        gate = 'PASS' if passes(file['covered'], file['total']) else 'FAIL'
        print(f"  {file['path']}: {file['covered']}/{file['total']} ({percent:.2f}%) {gate}")
        rows = []
        for number, line in enumerate((root / file["path"]).read_text().splitlines(), 1):
            count = file["lines"].get(str(number))
            state = "neutral" if count is None else "covered" if count else "missed"
            rows.append(f'<tr class="{state}"><td>{number}</td><td>{"" if count is None else count}</td>'
                        f'<td><pre>{html.escape(line)}</pre></td></tr>')
        sections.append(f'<details><summary>{html.escape(file["path"])}: {percent:.2f}% {gate}</summary>'
                        '<table><tr><th>Line</th><th>Hits</th><th>Source</th></tr>' + "".join(rows) + '</table></details>')
    (output / "bash.lcov").write_text("\n".join(lcov) + "\n")
    percent = report["covered"] / report["total"] * 100
    folder = output / "bash"
    folder.mkdir(exist_ok=True)
    (folder / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Bash coverage</title>'
        '<style>body{font:16px system-ui;margin:2rem}table{border-collapse:collapse;width:100%}'
        'td,th{padding:.1rem .5rem;text-align:left}pre{margin:0;white-space:pre-wrap}'
        '.covered{background:#dcfce7}.missed{background:#fee2e2}.neutral{color:#64748b}'
        'details{margin:1rem 0}summary{cursor:pointer}</style>'
        f'<h1>Bash coverage: {percent:.2f}%</h1><p>{report["covered"]} of {report["total"]} command lines.</p>'
        '<p>All application shell scripts are included. The messages data resource is excluded. '
        'This is line coverage, not branch coverage. Only identical fixture copies contribute hits.</p>'
        + "".join(sections) + '</html>\n')
    print(f"  TOTAL: {report['covered']}/{report['total']} ({percent:.2f}%)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--trace-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = collect(args.root.resolve(), args.trace_dir)
        write_reports(args.root.resolve(), report)
        return 0 if all(passes(file['covered'], file['total']) for file in report['files']) else 1
    except (OSError, ValueError, ImportError, KeyError, TypeError) as error:
        print("Cannot measure Bash coverage: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
