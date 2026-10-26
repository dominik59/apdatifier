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
EXECUTABLE_NODES = {
    "command", "declaration_command", "variable_assignment", "test_command",
    "arithmetic_command", "for_statement", "c_style_for_statement", "case_statement",
}


def sources(root):
    return sorted(path for path in (root / SCOPE).iterdir()
                  if path.is_file() and path.name != "messages"
                  and re.match(rb"#![^\n]*\b(?:bash|sh)\b", path.read_bytes()))


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
        aliases = {source for source, snapshot in snapshots.items()
                   if Path(source.decode()).name == path.name and snapshot == contents.rstrip(b"\n")}
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
    return dict(schemaVersion=1, scope=SCOPE, measurement="Bash DEBUG command lines",
                files=files, covered=sum(file["covered"] for file in files), total=sum(file["total"] for file in files))


def write_reports(root, report):
    output = root / "coverage"
    output.mkdir(exist_ok=True)
    (output / "bash.json").write_text(json.dumps(report, indent=2) + "\n")
    lcov = []
    sections = []
    print("Bash command-line coverage (informational):")
    for file in report["files"]:
        lcov += ["SF:" + file["path"], *(f"DA:{line},{count}" for line, count in file["lines"].items()),
                 "LF:" + str(file["total"]), "LH:" + str(file["covered"]), "end_of_record"]
        percent = file["covered"] / file["total"] * 100 if file["total"] else 0
        print(f"  {file['path']}: {file['covered']}/{file['total']} ({percent:.2f}%)")
        rows = []
        for number, line in enumerate((root / file["path"]).read_text().splitlines(), 1):
            count = file["lines"].get(str(number))
            state = "neutral" if count is None else "covered" if count else "missed"
            rows.append(f'<tr class="{state}"><td>{number}</td><td>{"" if count is None else count}</td>'
                        f'<td><pre>{html.escape(line)}</pre></td></tr>')
        sections.append(f'<details><summary>{html.escape(file["path"])}: {percent:.2f}%</summary>'
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
        write_reports(args.root.resolve(), collect(args.root.resolve(), args.trace_dir))
        return 0
    except (OSError, ValueError, ImportError) as error:
        print("Cannot measure Bash coverage: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
