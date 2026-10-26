"""Check report publication, failure states, and preservation of README content."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import update_coverage_readme as report


class CoverageReadmeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="apdatifier-readme-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.coverage = self.root / "coverage"
        self.coverage.mkdir()
        self.shell = self.root / 'package/contents/tools/sh/upgrade'
        self.shell.parent.mkdir(parents=True)
        self.shell.write_text('#!/bin/bash\nprintf covered\nprintf missed\n')
        self.configuration = self.root / ".coveragerc"
        self.configuration.write_text('[report]\nfail_under = 80\nprecision = 2\n')
        self.readme = self.root / "README.md"
        self.original = ('# Project\n\nUser text before badges.\n'
                         '<!-- coverage-badges:start -->\nOld badges\n<!-- coverage-badges:end -->\n'
                         '\nUser text between sections.\n\n### Coverage\n'
                         '<!-- coverage-summary:start -->\nOld table\n<!-- coverage-summary:end -->\n'
                         '\nUser text after sections: \u2603.\n')
        self.readme.write_text(self.original)
        self.data = {'meta': {'branch_coverage': True},
                     'totals': {'covered_lines': 90, 'num_statements': 100,
                                'covered_branches': 18, 'num_branches': 20}}
        self.write_reports()

    def write_reports(self):
        (self.coverage / "python.json").write_text(json.dumps(self.data))
        (self.coverage / "javascript.lcov").write_text(
            'SF:package/contents/tools/tools.js\nLF:100\nLH:94\nBRF:100\nBRH:75\n'
            'FNF:100\nFNH:91\nend_of_record\n')
        (self.coverage / 'bash.json').write_text(json.dumps({
            'schemaVersion': 1, 'scope': 'package/contents/tools/sh', 'covered': 2, 'total': 2,
            'files': [{'path': 'package/contents/tools/sh/upgrade',
                       'sha256': hashlib.sha256(self.shell.read_bytes()).hexdigest(),
                       'lines': {'2': 1, '3': 1}, 'covered': 2, 'total': 2}]}))

    def update(self, **overrides):
        arguments = dict(root=self.root, exit_code=0, phase="complete", python_status="passed",
                         javascript_status="passed", javascript_thresholds=[80, 70, 70], bash_status="passed")
        arguments.update(overrides)
        return report.update(**arguments)

    def test_metrics_badges_and_thresholds_come_from_reports_and_configuration(self):
        self.assertEqual(self.update(), 0)
        text = self.readme.read_text()
        self.assertIn('Last coverage run: **PASSED**', text)
        self.assertIn('| Python: statements and branches | 90.00% | 80% | PASS |', text)
        self.assertIn('| Python: branches | 90.00% | Not gated | Not gated |', text)
        self.assertIn('| JavaScript: lines | 94.00% | 80% | PASS |', text)
        self.assertIn('| JavaScript: branches | 75.00% | 70% | PASS |', text)
        self.assertIn('| JavaScript: functions | 91.00% | 70% | PASS |', text)
        self.assertIn('Python%20coverage-90.00%25-brightgreen?style=flat', text)
        self.assertIn('JavaScript%20lines-94.00%25-brightgreen?style=flat', text)
        self.assertIn('| Bash: lines | 100.00% | 80% | PASS |', text)
        self.assertIn('Bash%20lines-100.00%25-brightgreen?style=flat', text)
        self.configuration.write_text('[report]\nfail_under = 95\nprecision = 2\n')
        self.assertEqual(self.update(javascript_thresholds=[95, 80, 95]), 1)
        text = self.readme.read_text()
        self.assertIn('| Python: statements and branches | 90.00% | 95% | FAIL |', text)
        self.assertIn('| JavaScript: branches | 75.00% | 80% | FAIL |', text)
        self.assertIn('Python%20coverage-90.00%25-red', text)

    def test_combined_python_metric_is_weighted_by_counts(self):
        self.data['totals'].update(covered_lines=50, num_statements=100, covered_branches=10, num_branches=10)
        self.write_reports()
        self.assertEqual(self.update(exit_code=1, python_status="failed"), 0)
        self.assertIn('| Python: statements and branches | 54.55%', self.readme.read_text())

    def test_high_coverage_does_not_hide_a_failed_test_run(self):
        self.assertEqual(self.update(exit_code=1, python_status="failed"), 0)
        text = self.readme.read_text()
        self.assertIn('Last coverage run: **FAILED**', text)
        self.assertIn('Python checks: **FAILED**', text)
        self.assertIn('| Python: statements and branches | 90.00% | 80% | PASS |', text)

    def test_current_missing_or_invalid_report_keeps_only_independent_metrics(self):
        for content in (None, '{invalid', '[]', '{"meta":null}',
                        json.dumps({'meta': {'branch_coverage': False}})):
            with self.subTest(content=content):
                path = self.coverage / "python.json"
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(content)
                self.assertEqual(self.update(), 1)
                text = self.readme.read_text()
                self.assertIn('Last coverage run: **FAILED**', text)
                self.assertIn('| Python: statements and branches | Unavailable', text)
                self.assertIn('| JavaScript: lines | 94.00%', text)
                self.assertIn('Python coverage report is missing or invalid.', text)
                self.assertIn('Python%20coverage-unavailable-lightgrey', text)

    def test_setup_failure_and_interruption_do_not_reuse_old_reports(self):
        self.assertEqual(self.update(exit_code=2, phase="preparation", python_status="not-run",
                                     javascript_status="not-run", bash_status="not-run"), 0)
        text = self.readme.read_text()
        self.assertIn('Last coverage run: **NOT RUN**', text)
        self.assertNotIn('90.00%', text)
        self.assertNotIn('94.00%', text)
        self.assertEqual(self.update(exit_code=130, phase="python", interrupted=True,
                                     javascript_status="not-run", python_status="failed"), 0)
        self.assertIn('Last coverage run: **INTERRUPTED**', self.readme.read_text())

    def test_native_python_precision_and_exact_hundred_percent_requirement(self):
        self.data['totals'].update(covered_lines=79996, num_statements=99900,
                                  covered_branches=0, num_branches=100)
        self.write_reports()
        self.assertEqual(self.update(), 0)
        self.assertIn('| Python: statements and branches | 80.00% | 80% | PASS |', self.readme.read_text())
        self.configuration.write_text('[report]\nfail_under = 100\nprecision = 2\n')
        self.data['totals'].update(covered_lines=99999, num_statements=99999,
                                  covered_branches=0, num_branches=1)
        self.write_reports()
        self.assertEqual(self.update(), 1)
        self.assertIn('| Python: statements and branches | 100.00% | 100% | FAIL |', self.readme.read_text())

    def test_invalid_and_zero_counters_are_unavailable_instead_of_fabricated_percentages(self):
        for covered, total in ((-1, 100), (101, 100), (0, 0), (True, 100), ("90", 100)):
            with self.subTest(covered=covered, total=total):
                self.data['totals'].update(covered_lines=covered, num_statements=total)
                self.write_reports()
                self.assertEqual(self.update(), 1)
                self.assertIn('| Python: statements and branches | Unavailable', self.readme.read_text())

    def test_partial_wrong_scope_and_duplicate_lcov_counters_are_rejected(self):
        path = self.coverage / "javascript.lcov"
        original = path.read_text()
        for text in (original.replace('end_of_record\n', ''), original + original,
                     original.replace('tools/tools.js', 'ui/other.js'),
                     original.replace('LF:100', 'LF:100\nLF:100'),
                     original.replace('BRH:75', 'BRH:101'), original.replace('LH:94\n', '')):
            with self.subTest(lcov=text):
                path.write_text(text)
                self.assertEqual(self.update(), 1)
                self.assertIn('| JavaScript: lines | Unavailable', self.readme.read_text())
                self.assertIn('| Python: statements and branches | 90.00%', self.readme.read_text())

    def test_absolute_lcov_path_is_accepted_only_for_the_current_project(self):
        path = self.coverage / "javascript.lcov"
        text = path.read_text()
        path.write_text(text.replace('SF:package/', f'SF:{self.root}/package/'))
        self.assertEqual(self.update(), 0)
        path.write_text(text.replace('SF:package/', 'SF:/another/project/package/'))
        self.assertEqual(self.update(), 1)
        self.assertIn('| JavaScript: lines | Unavailable', self.readme.read_text())

    def test_readme_content_outside_markers_and_line_endings_are_preserved(self):
        for newline in ('\n', '\r\n'):
            with self.subTest(newline=newline):
                original = self.original.replace('\n', newline)
                self.readme.write_bytes(original.encode())
                self.assertEqual(self.update(), 0)
                text = self.readme.read_bytes().decode()
                def without_blocks(content):
                    for name in report.BLOCKS:
                        start, end = f'<!-- {name}:start -->', f'<!-- {name}:end -->'
                        first, last = content.index(start) + len(start), content.index(end)
                        content = content[:first] + content[last:]
                    return content
                self.assertEqual(without_blocks(text), without_blocks(original))
                if newline == '\r\n':
                    self.assertNotIn('\n', text.replace('\r\n', ''))

    def test_identical_results_do_not_rewrite_the_readme(self):
        self.assertEqual(self.update(), 0)
        before = self.readme.stat()
        with mock.patch.object(report.os, "replace", side_effect=AssertionError("Unexpected write")):
            self.assertEqual(self.update(), 0)
        self.assertEqual(self.readme.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(self.readme.stat().st_ino, before.st_ino)

    def test_invalid_marker_pairs_leave_the_entire_readme_unchanged(self):
        for text in (self.original.replace('<!-- coverage-summary:end -->', ''),
                     self.original + '<!-- coverage-badges:start -->',
                     self.original.replace('<!-- coverage-badges:start -->', '<!-- coverage-badges:end -->')
                     .replace('Old badges', '<!-- coverage-badges:start -->Old badges')
                     .replace('Old badges\n<!-- coverage-badges:end -->', 'Old badges')):
            with self.subTest(readme=text):
                self.readme.write_text(text)
                with self.assertRaises(ValueError):
                    self.update()
                self.assertEqual(self.readme.read_text(), text)

    def test_failed_atomic_replacement_keeps_previous_content_and_removes_temporary_file(self):
        with mock.patch.object(report.os, "replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                self.update()
        self.assertEqual(self.readme.read_text(), self.original)
        self.assertEqual(list(self.root.glob('.README.coverage.*')), [])

    def test_file_permissions_survive_a_successful_update(self):
        self.readme.chmod(0o640)
        self.assertEqual(self.update(), 0)
        self.assertEqual(self.readme.stat().st_mode & 0o777, 0o640)

    def test_cli_reports_a_missing_readme_without_a_traceback(self):
        self.readme.unlink()
        with contextlib.redirect_stderr(io.StringIO()) as error:
            code = report.main(['--root', str(self.root), '--exit-code', '0', '--phase', 'complete',
                                '--python-status', 'passed', '--javascript-status', 'passed',
                                '--javascript-thresholds', '80', '70', '70'])
        self.assertEqual(code, 1)
        self.assertIn('Cannot update README coverage status', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())

    def test_bash_gate_cannot_hide_low_coverage_or_a_measurement_failure(self):
        path = self.coverage / 'bash.json'
        data = json.loads(path.read_text())
        data['covered'] = data['files'][0]['covered'] = 0
        data['files'][0]['lines'] = {'2': 0, '3': 0}
        path.write_text(json.dumps(data))
        self.assertEqual(self.update(), 1)
        self.assertIn('| Bash: lines | 0.00% | 80% | FAIL |', self.readme.read_text())
        self.assertEqual(self.update(bash_status='failed'), 1)
        self.assertIn('Last coverage run: **FAILED**', self.readme.read_text())

    def test_invalid_bash_reports_preserve_independent_python_and_javascript_metrics(self):
        path = self.coverage / 'bash.json'
        original = json.loads(path.read_text())
        invalid = []
        for key, value in (('scope', '/another/project'), ('total', 99), ('schemaVersion', 9)):
            data = json.loads(json.dumps(original))
            data[key] = value
            invalid.append(json.dumps(data))
        data = json.loads(json.dumps(original))
        data['files'].append(data['files'][0])
        invalid.append(json.dumps(data))
        data = json.loads(json.dumps(original))
        data['files'][0]['lines']['2'] = -1
        invalid.append(json.dumps(data))
        invalid += [None, '{invalid', '[]']
        for content in invalid:
            with self.subTest(content=content):
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(content)
                self.assertEqual(self.update(), 1)
                text = self.readme.read_text()
                self.assertIn('| Bash: lines | Unavailable', text)
                self.assertIn('| Python: statements and branches | 90.00%', text)
                self.assertIn('| JavaScript: lines | 94.00%', text)

    def test_bash_report_cannot_omit_unexecuted_files_or_reuse_earlier_source_hashes(self):
        self.shell.with_name('unused').write_text('#!/bin/bash\nprintf never\n')
        self.assertEqual(self.update(), 1)
        self.assertIn('| Bash: lines | Unavailable', self.readme.read_text())
        self.shell.with_name('unused').unlink()
        self.shell.write_text(self.shell.read_text() + 'printf new\n')
        self.assertEqual(self.update(), 1)
        self.assertIn('| Bash: lines | Unavailable', self.readme.read_text())

    def test_altered_line_sets_cannot_reduce_the_denominator(self):
        path = self.coverage / 'bash.json'
        original = path.read_text()
        for action in ('omit', 'extra', 'replace'):
            with self.subTest(action=action):
                data = json.loads(original)
                file = data['files'][0]
                if action in ('omit', 'replace'):
                    del file['lines']['3']
                if action in ('extra', 'replace'):
                    file['lines']['1'] = 1
                data['total'] = file['total'] = len(file['lines'])
                data['covered'] = file['covered'] = sum(hit > 0 for hit in file['lines'].values())
                path.write_text(json.dumps(data))
                self.assertEqual(self.update(), 1)
                self.assertIn('| Bash: lines | Unavailable', self.readme.read_text())

    def test_high_total_cannot_hide_one_failed_file_and_rows_are_sorted(self):
        self.shell.write_text('#!/bin/bash\n'+'printf covered\\n\n'*100)
        unused = self.shell.with_name('aaa-unused')
        unused.write_text('#!/bin/bash\nprintf never\n')
        files = [dict(path=file.relative_to(self.root).as_posix(),
                      sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                      lines={str(n): hit for n in range(2, count+2)}, covered=count*hit, total=count)
                 for file,count,hit in [(self.shell,100,1),(unused,1,0)]]
        self.coverage.joinpath('bash.json').write_text(json.dumps(dict(
            schemaVersion=1, scope='package/contents/tools/sh', files=files, covered=100, total=101)))
        self.assertEqual(self.update(), 1)
        text = self.readme.read_text()
        self.assertIn('Bash%20lines-99.01%25-red', text)
        self.assertIn('**1/2**', text)
        self.assertLess(text.index('`package/contents/tools/sh/aaa-unused`'),
                        text.index('`package/contents/tools/sh/upgrade`'))

    def test_missing_parser_is_unavailable_but_preparation_needs_no_parser(self):
        with mock.patch.object(report, 'validate', side_effect=ImportError('parser absent')):
            self.assertEqual(self.update(), 1)
            self.assertIn('Bash%20lines-unavailable-lightgrey', self.readme.read_text())
            self.assertIn('| Python: statements and branches | 90.00%', self.readme.read_text())
        with mock.patch.object(report, 'validate', side_effect=AssertionError('Unexpected parser use')):
            self.assertEqual(self.update(exit_code=2, phase='preparation', python_status='not-run',
                                         javascript_status='not-run', bash_status='not-run'), 0)


if __name__ == '__main__':
    unittest.main()
