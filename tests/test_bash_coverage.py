"""Exercise tracing against real Bash, including return codes and fixture copies."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import bash_coverage as report


@unittest.skipUnless(importlib.util.find_spec('tree_sitter') and importlib.util.find_spec('tree_sitter_bash'),
                     'Bash coverage parser tests need requirements-test.txt in the development environment.')
class BashCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='apdatifier-bash-coverage-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'project with spaces'
        self.scripts = self.root / report.SCOPE
        self.scripts.mkdir(parents=True)
        self.trace = self.root / 'traces'
        self.trace.mkdir()
        self.hook = Path(__file__).with_name('bash_coverage.sh').resolve()
        self.source = self.scripts / 'upgrade'
        self.source.write_text('''#!/usr/bin/env bash
set -e
unused() {
    printf 'uncovered\\n'
}
show() {
    local value="three words"
    if [[ "$1" == yes ]]; then
        printf '%s\\n' "$value"
    else
        printf 'wrong\\n'
    fi
}
show yes
set +e
false
printf 'status:%s\\n' "$?"
for i in a b; do
    printf '%s\\n' "$i"
done
cat <<'DOC'
printf 'heredoc text'
DOC
(printf 'subshell\\n')
printf '%s\\n' "$COV_SECRET"
''')

    def run_shell(self, source=None):
        for path in self.trace.glob('trace-*'):
            path.unlink()
        env = dict(os.environ, COV_SECRET='PRIVATE_EXPANDED_VALUE_94723')
        env.pop('BASH_ENV', None)
        env.pop('APDATIFIER_BASH_COVERAGE_DIR', None)
        command = ['bash', str(source or self.source)]
        ordinary = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=10, env=env)
        traced = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                                env=dict(env, BASH_ENV=str(self.hook), APDATIFIER_BASH_COVERAGE_DIR=str(self.trace)))
        self.assertEqual((traced.returncode, traced.stdout, traced.stderr),
                         (ordinary.returncode, ordinary.stdout, ordinary.stderr))
        return report.collect(self.root, self.trace)

    def line(self, text):
        return str(next(number for number, line in enumerate(self.source.read_text().splitlines(), 1) if text in line))

    def test_real_execution_preserves_output_and_status_without_logging_expanded_values(self):
        data = self.run_shell()
        lines = data['files'][0]['lines']
        self.assertGreater(lines[self.line('"$value"')], 0)
        self.assertEqual(lines[self.line('uncovered')], 0)
        self.assertEqual(lines[self.line('wrong')], 0)
        self.assertNotIn(self.line('heredoc text'), lines)
        self.assertGreater(lines[self.line("subshell")], 0)
        for trace in self.trace.glob('trace-*'):
            self.assertNotIn(b'PRIVATE_EXPANDED_VALUE_94723', trace.read_bytes())

    def test_unexecuted_scripts_remain_in_the_denominator_but_messages_is_data(self):
        self.source.with_name('never').write_text('#!/bin/bash\nprintf never\n')
        self.source.with_name('messages').write_text('not executable shell data\n')
        data = self.run_shell()
        files = {Path(file['path']).name: file for file in data['files']}
        self.assertEqual(set(files), {'upgrade', 'never'})
        self.assertEqual(files['never']['covered'], 0)
        self.assertGreater(files['never']['total'], 0)
        self.assertEqual(data['total'], sum(file['total'] for file in files.values()))

    def test_identical_temporary_copies_count_but_modified_copies_do_not(self):
        copy = self.root / 'fixture/contents/tools/sh/upgrade'
        copy.parent.mkdir(parents=True)
        copy.write_bytes(self.source.read_bytes())
        data = self.run_shell(copy)
        self.assertGreater(data['covered'], 0)
        copy.write_text(copy.read_text().replace('three words', 'different text'))
        with self.assertRaisesRegex(ValueError, 'No Bash execution matched'):
            self.run_shell(copy)

    def test_bad_or_missing_trace_data_cannot_produce_a_successful_report(self):
        with self.assertRaisesRegex(ValueError, 'No Bash execution matched'):
            report.collect(self.root, self.trace)
        (self.trace / 'trace-broken').write_bytes(b'L\0some-path\0')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            report.collect(self.root, self.trace)
        (self.trace / 'trace-broken').write_bytes(b'X\0some-path\0bad\0')
        with self.assertRaisesRegex(ValueError, 'invalid'):
            report.collect(self.root, self.trace)

    def test_dynamic_substring_offsets_and_multiline_commands_have_stable_line_numbers(self):
        self.source.write_text('''#!/bin/bash
value=abc
position=1
printf '%s\\n' \\
    "${value:$position:1}"
''')
        data = self.run_shell()
        self.assertEqual(set(data['files'][0]['lines']), {'2', '3', '4'})
        self.assertEqual(data['covered'], 3)

    def test_reports_include_unexecuted_files_and_escape_html_source(self):
        self.source.write_text('#!/bin/bash\nprintf "<script>literal</script>\\n"\n')
        self.source.with_name('never').write_text('#!/bin/bash\nprintf never\n')
        data = self.run_shell()
        with contextlib.redirect_stdout(io.StringIO()):
            report.write_reports(self.root, data)
        page = (self.root / 'coverage/bash/index.html').read_text()
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>', page)
        lcov = (self.root / 'coverage/bash.lcov').read_text()
        self.assertIn('SF:package/contents/tools/sh/never\nDA:2,0\n', lcov)
        self.assertTrue((self.root / 'coverage/bash.json').is_file())


if __name__ == '__main__':
    unittest.main()
