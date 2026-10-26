"""Exercise tracing against real Bash, including return codes and fixture copies."""

import contextlib
import copy
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import bash_coverage as report
from shell_fixtures import bash_command, compatible_results


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

    def test_integer_boundary_does_not_accept_a_rounded_percentage(self):
        self.assertTrue(report.passes(80, 100))
        self.assertEqual(f'{19999 / 25000 * 100:.2f}', '80.00')
        self.assertFalse(report.passes(19999, 25000))
        for counts in ((0, 0), (True, 1), (2, 1), (-1, 1)):
            self.assertFalse(report.passes(*counts))

    def test_exact_line_sets_reject_omissions_extras_and_equal_size_replacements(self):
        original = self.run_shell()
        missing = self.line('uncovered')
        for action in ('omit', 'extra', 'replace'):
            with self.subTest(action=action):
                data = copy.deepcopy(original)
                file = data['files'][0]
                if action in ('omit', 'replace'):
                    del file['lines'][missing]
                if action in ('extra', 'replace'):
                    file['lines']['1'] = 1
                file['total'] = data['total'] = len(file['lines'])
                file['covered'] = data['covered'] = sum(hit > 0 for hit in file['lines'].values())
                with self.assertRaisesRegex(ValueError, 'upgrade: executable line set'):
                    report.validate(self.root, data)

    def test_nested_sources_do_not_share_hits_with_identical_names_and_contents(self):
        self.source.write_text('#!/bin/bash\nprintf control\\n\n')
        nested = self.scripts / 'nested/upgrade'
        nested.parent.mkdir()
        nested.write_bytes(self.source.read_bytes())
        data = self.run_shell()
        self.assertEqual([file['covered'] for file in data['files']], [0, 1])
        self.assertEqual(len(report.sources(self.root)), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(report.main(['--root', str(self.root), '--trace-dir', str(self.trace)]), 1)
        self.assertTrue((self.root / 'coverage/bash.json').exists())
        self.assertTrue((self.root / 'coverage/bash.lcov').exists())
        self.assertTrue((self.root / 'coverage/bash/index.html').exists())

    def test_empty_script_scope_and_parser_failure_are_measurement_errors(self):
        self.source.write_text('#!/bin/bash\n# no commands\n')
        data = dict(schemaVersion=1, scope=report.SCOPE, files=[dict(
            path=self.source.relative_to(self.root).as_posix(),
            sha256=report.hashlib.sha256(self.source.read_bytes()).hexdigest(),
            lines={}, covered=0, total=0)], covered=0, total=0)
        with self.assertRaisesRegex(ValueError, 'empty Bash line counters'):
            report.validate(self.root, data)
        self.source.write_text('#!/bin/bash\nprintf okay\n')
        data = self.run_shell()
        with mock.patch.object(report, 'executable_lines', side_effect=ImportError('parser absent')):
            with self.assertRaises(ImportError):
                report.validate(self.root, data)
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, 'scope is empty'):
            report.collect(self.root, self.trace)

    def test_sh_measurement_uses_bash_and_native_results_are_compared(self):
        self.source.write_text('#!/bin/sh\nprintf "%s" "$1"\nprintf warning >&2\nexit 7\n')
        self.source.chmod(0o700)
        env = dict(os.environ, BASH_ENV=str(self.hook), APDATIFIER_BASH_COVERAGE_DIR=str(self.trace))
        native = subprocess.run([str(self.source), 'literal $()'], capture_output=True, timeout=10, env=env)
        self.assertFalse(list(self.trace.glob('trace-*')))
        command = bash_command(self.source, 'literal $()')
        self.assertEqual(command[:4], ['bash', '--noprofile', '--norc', '--'])
        measured = subprocess.run(command, capture_output=True, timeout=10, env=env)
        self.assertTrue(compatible_results(measured, native, {}, {}))
        self.assertFalse(compatible_results(measured, native, {'changed': True}, {}))
        data = report.collect(self.root, self.trace)
        self.assertEqual(data['covered'], data['total'])
        for trace in self.trace.glob('trace-*'):
            trace.unlink()
        control = self.scripts / 'control'
        control.write_text('#!/bin/bash\nprintf control\n')
        subprocess.run(bash_command(control), capture_output=True, timeout=10, env=env, check=True)
        subprocess.run([str(self.source), 'literal $()'], capture_output=True, timeout=10, env=env)
        files = {Path(file['path']).name: file for file in report.collect(self.root, self.trace)['files']}
        self.assertEqual(files['upgrade']['covered'], 0)
        self.assertFalse(report.passes(files['upgrade']['covered'], files['upgrade']['total']))


if __name__ == '__main__':
    unittest.main()
