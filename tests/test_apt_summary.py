"""APT reports use captured plans; native tests use only private package databases."""

import ast
import contextlib
import gettext
import io
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import time
import unittest
from unittest import mock

import test_backends as test_support
from test_backends import b, completed, INSTALLED, TemporaryCase, UPGRADE


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/apt/2026-10-28-upgrade-preview.txt"
SUMMARY = "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n"
REPORT_MESSAGES = (
    "Install", "Upgrade", "Downgrade", "Reinstall", "Remove", "Configure",
    "including configuration files", "Optional cleanup", "Candidate list unavailable", "Not applicable",
    "These packages will not be removed during this operation.",
    "You can remove them with a separate autoremove operation.",
    "Deferred because of phasing", "Deferred updates", "Transaction total", "No package operations are planned.",
    "APT messages", "Run this APT operation?",
    "The plan installs earlier package versions. Allow these version decreases?",
    "Packages that will receive an earlier version: ",
    "An earlier version can need different dependencies. Continue?",
    "The local file can install an earlier version. Continue?", "Local package: ",
    "This operation removes downloaded package archives.",
    "The APT transaction contains an unknown record.", "Cannot compare the selected APT versions.",
    "APT did not identify the package architecture.",
)


def native_runner(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def capture_report(changes, info=None, inventory=None, **kwargs):
    groups = b.apt_operation_groups(changes, mock.Mock(run=native_runner))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        b.print_apt_summary(groups, info or b.apt_information(SUMMARY), inventory or {}, **kwargs)
    return groups, output.getvalue()


def catalog_messages(path):
    """Read singular entries without introducing a test dependency on gettext tools."""
    messages, fuzzy = {}, set()
    for block in path.read_text().split("\n\n"):
        values, field = {}, None
        if "msgctxt " in block or "msgid_plural " in block:
            continue
        for line in block.splitlines():
            if line.startswith(("msgid ", "msgstr ")):
                field, literal = line.split(" ", 1)
                values[field] = ast.literal_eval(literal)
            elif line.startswith('"') and field:
                values[field] += ast.literal_eval(line)
        if "msgid" in values and "msgstr" in values:
            messages[values["msgid"]] = values["msgstr"]
            if any(line.startswith("#,") and "fuzzy" in line for line in block.splitlines()):
                fuzzy.add(values["msgid"])
    return messages, fuzzy


def write_catalog(path, messages):
    """Compile a small singular-message fixture in the documented GNU MO format."""
    keys = sorted(messages)
    sources = [key.encode() for key in keys]
    targets = [messages[key].encode() for key in keys]
    start = 28 + 16 * len(keys)
    original, translated = [], []
    source_data = b"\0".join(sources) + b"\0"
    offset = start
    for value in sources:
        original.extend((len(value), offset))
        offset += len(value) + 1
    for value in targets:
        translated.extend((len(value), offset))
        offset += len(value) + 1
    header = [0x950412de, 0, len(keys), 28, 28 + 8 * len(keys), 0, 0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack('<' + 'I' * (7 + 4 * len(keys)), *(header + original + translated)) +
                     source_data + b"\0".join(targets) + b"\0")


class AptSummaryTests(TemporaryCase):
    def test_supplied_log_drives_operations_candidates_and_phasing(self):
        text = FIXTURE.read_text()
        changes = b.parse_simulation(text, {}, configure=True)
        info = b.apt_information(text)
        inventory = dict((item["nativeId"], item) for item in changes)
        # The log omits these fields; this additional metadata is synthetic.
        for name in info["autoremove"]:
            arch = "all" if name == "linux-headers-7.0.0-38" else "amd64"
            pkg = b.package_record("apt", name + ":" + arch, name, "7.0.0-38.38", architecture=arch)
            inventory[pkg["nativeId"]] = pkg
        groups, output = capture_report(changes, info, inventory)
        self.assertEqual([len(groups[key]) for key in groups], [8, 12, 0, 0, 0, 0])
        self.assertEqual(len(info["autoremove"]), 7)
        self.assertEqual(len(info["phased"]), 6)
        self.assertIn("Transaction total: 20", output)
        self.assertIn("Optional cleanup: 7", output)
        self.assertIn("These packages will not be removed during this operation.", output)
        self.assertIn("You can remove them with a separate autoremove operation.", output)
        for row in changes:
            self.assertEqual(sum(line.startswith("  " + row["nativeId"] + " ") for line in output.splitlines()), 1)
            self.assertIn(row["candidateVersion"], output)
        self.assertNotIn("Inst ", output)
        self.assertNotIn("Conf ", output)

    def test_all_operation_kinds_and_debian_version_order(self):
        text = ("Inst new-package (1 Test:stable [all])\n"
                "Inst example [1.0-1] (1:1~rc1 Test:stable [amd64])\n"
                "Inst decrease [2] (1.9 Test:stable [amd64])\n"
                "Inst same [1.0] (1.0-0 Test:stable [amd64])\n"
                "Purg other [1]\nConf pending (9 Test:stable [amd64])\n")
        data = dict(INSTALLED)
        data["pending:amd64"] = b.package_record("apt", "pending:amd64", "pending", "3", architecture="amd64", dpkgState="unpacked")
        changes = b.parse_simulation(text, INSTALLED, configure=True, package_data=data)
        groups, output = capture_report(changes)
        self.assertEqual([len(rows) for rows in groups.values()], [1, 1, 1, 1, 1, 1])
        self.assertIn("other:amd64 1 (including configuration files)", output)
        self.assertIn("pending:amd64 3", output)
        self.assertNotIn("pending:amd64 9", output)
        for candidate, current, order in (("1.10", "1.9", 1), ("1~rc1", "1", -1), ("1", "1-0", 0), ("1", "1", 0)):
            self.assertEqual(b.apt_version_order(candidate, current, mock.Mock(run=native_runner)), order)

    def test_purge_and_configuration_state_validation(self):
        text = "Purg old-config\n"
        data = {"old-config:amd64": b.package_record("apt", "old-config:amd64", "old-config", "1", architecture="amd64", dpkgState="config-files")}
        changes = b.parse_simulation(text, {}, package_data=data)
        self.assertEqual(changes[0]["installedVersion"], "1")
        for safe, excluded in ((True, set()), (False, {"old-config:amd64"})):
            with self.assertRaises(b.BackendError):
                b.assert_plan(changes, excluded, safe)
        for state in ({}, {"pending:amd64": dict(data["old-config:amd64"], name="pending", nativeId="pending:amd64")}):
            with self.assertRaises(b.BackendError):
                b.parse_simulation("Conf pending (2 Test:stable [amd64])\n", {}, configure=True, package_data=state)
        for text in (UPGRADE + "Inst example [1.0-1] (3 Test:stable [amd64])\n", "Purg example ???\n"):
            with self.assertRaises(b.BackendError):
                b.parse_simulation(text, INSTALLED)

    def test_full_report_and_diagnostics_are_not_truncated(self):
        text = ''.join(f"Inst package-{i:04} (1 Test:stable [amd64])\n" for i in range(300))
        changes = b.parse_simulation(text, {})
        info = b.apt_information(SUMMARY + "Warning: https://user:secret@example.invalid/repo\n" + "X" * 7000 + "\n")
        _, output = capture_report(changes, info)
        self.assertIn("package-0000:amd64", output)
        self.assertIn("package-0299:amd64", output)
        self.assertEqual(len(re.findall(r'^  package-', output, re.M)), 300)
        self.assertNotIn("secret", output)
        self.assertIn("X" * 7000, output)
        self.assertEqual(len(b.redact("X" * 7000)), 6000)

    def test_candidate_lists_and_availability(self):
        heading = "The following packages were automatically installed and are no longer required:\n"
        for rows in ("  example\n  other\n", "  example   other\n", "  example\n    other\n"):
            info = b.apt_information(heading + rows + "Use 'sudo apt autoremove' to remove them.\n" + SUMMARY)
            _, output = capture_report([], info, INSTALLED)
            self.assertIn("Optional cleanup: 2", output)
            self.assertIn("These packages will not be removed during this operation.", output)
        _, output = capture_report([], zero_verified=True)
        self.assertIn("Optional cleanup: 0", output)
        self.assertNotIn("These packages will not be removed during this operation.", output)
        for text in ("", "unfamiliar summary\n", "2 packages were automatically installed and are no longer required.\n" + SUMMARY,
                     heading + "  invalid/name\n" + SUMMARY, heading + SUMMARY, heading + "  example\n"):
            _, output = capture_report([], b.apt_information(text), INSTALLED, zero_verified=True)
            self.assertIn("Candidate list unavailable", output)
            self.assertNotIn("You can remove them with a separate autoremove operation.", output)
        _, output = capture_report([], b.apt_information(SUMMARY), zero_verified=False)
        self.assertIn("Candidate list unavailable", output)
        _, output = capture_report([], autoremove=True)
        self.assertIn("Not applicable", output)
        self.assertNotIn("These packages will not be removed during this operation.", output)
        _, output = capture_report(b.parse_simulation('Remv other [1]\n', INSTALLED), autoremove=True)
        self.assertIn('Remove (1)', output)
        self.assertNotIn('These packages will not be removed during this operation.', output)
        self.assertIsNone(b.apt_candidate_rows(["unknown"], INSTALLED))
        data = dict(INSTALLED, **{"example:i386": dict(INSTALLED["example:amd64"], nativeId="example:i386", architecture="i386")})
        self.assertIsNone(b.apt_candidate_rows(["example"], data))

    def test_unfamiliar_messages_and_deferred_reasons_remain_visible(self):
        text = ("The following upgrades have been deferred due to phasing:\n  example\n"
                "The following packages have been kept back:\n  other\n"
                "Future explanation:\n  relevant details\n")
        _, output = capture_report([], b.apt_information(text))
        self.assertIn("Deferred because of phasing (1)", output)
        self.assertIn("Deferred updates (1)", output)
        self.assertIn("Future explanation:\n  relevant details", output)

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_foreground_uses_one_preview_and_keeps_real_command(self, installed, confirm):
        self.runner.run.side_effect = lambda argv, **kw: native_runner(argv) if "--compare-versions" in argv else completed(argv, UPGRADE if "--simulate" in argv else "")
        with contextlib.redirect_stdout(io.StringIO()):
            b.apt_foreground(self.paths, "upgrade", [], self.runner)
        calls = [call.args[0] for call in self.runner.run.call_args_list]
        previews = [argv for argv in calls if "--simulate" in argv]
        self.assertEqual(len(previews), 1)
        for option in b.APT_PREVIEW_OPTIONS[1::2]:
            self.assertIn(option, previews[0])
            self.assertNotIn(option, calls[-1])
        self.assertEqual(calls[-1][-3:], ["--no-remove", "--with-new-pkgs", "upgrade"])
        confirm.assert_called_once_with("Run this APT operation?")

    def test_comparison_failure_and_consent_prevent_execution(self):
        with self.assertRaises(b.BackendError):
            b.apt_version_order("2", "1", mock.Mock(run=lambda *a, **kw: completed(code=2)))
        with mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED), \
                mock.patch.object(b, "confirm", side_effect=b.BackendError("Canceled", "canceled", 130)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.runner.run.side_effect = lambda argv, **kw: native_runner(argv) if "--compare-versions" in argv else completed(stdout=UPGRADE if "--simulate" in argv else "")
            with self.assertRaises(b.BackendError):
                b.apt_foreground(self.paths, "upgrade", [], self.runner)
        self.assertFalse(any("upgrade" in call.args[0] and "--simulate" not in call.args[0] for call in self.runner.run.call_args_list))

    def test_comparisons_are_reused_and_incomplete_plans_are_rejected(self):
        text = UPGRADE + "Inst other [1.0-1] (2.0-1 Test:stable [amd64])\n"
        changes = b.parse_simulation(text, {})
        runner = mock.Mock()
        runner.run.side_effect = native_runner
        b.apt_operation_groups(changes, runner)
        self.assertEqual(runner.run.call_count, 1)
        with mock.patch.object(b.AptBackend, 'installed', return_value=INSTALLED), \
                mock.patch.object(b, 'confirm') as confirm, contextlib.redirect_stdout(io.StringIO()):
            self.runner.run.side_effect = lambda argv, **kw: completed(stdout=SUMMARY + UPGRADE if '--simulate' in argv else '')
            with self.assertRaises(b.BackendError):
                b.apt_foreground(self.paths, 'upgrade', [], self.runner)
            confirm.assert_not_called()

    @mock.patch.object(b.AptBackend, 'installed', return_value=INSTALLED)
    def test_each_foreground_action_reports_before_confirmation(self, installed):
        archive = self.root / 'local package.deb'
        archive.touch()
        for action, values in [('upgrade', []), ('upgrade-package', ['example:amd64']),
                               ('install', ['example:amd64']), ('install-version', ['example:amd64', '2.0-1']),
                               ('local-install', [str(archive)]), ('remove', ['other:amd64']),
                               ('purge', ['other:amd64']), ('autoremove', []), ('clean', []), ('autoclean', [])]:
            with self.subTest(action=action):
                output = io.StringIO()
                expected = 'This operation removes downloaded package archives.' if action in ('clean', 'autoclean') else 'Transaction total:'
                def confirm(message):
                    if message == 'Run this APT operation?':
                        self.assertIn(expected, output.getvalue())
                def run(argv, **kwargs):
                    if '--compare-versions' in argv:
                        return native_runner(argv)
                    if '--field' in argv:
                        return completed(stdout='Package: example\nVersion: 2.0-1\nArchitecture: amd64\n')
                    if '--simulate' in argv:
                        return completed(stdout=('Purg other [1]\n' if action == 'purge' else
                                                 'Remv other [1]\n' if action in ('remove', 'autoremove') else UPGRADE))
                    return completed()
                self.runner.reset_mock()
                self.runner.run.side_effect = run
                with mock.patch.object(b, 'confirm', side_effect=confirm), \
                        mock.patch.object(b.AptBackend, 'marks', return_value=set()), \
                        mock.patch.object(b.AptBackend, 'package_states', return_value={key: dict(value, dpkgState='installed') for key, value in INSTALLED.items()}), \
                        mock.patch.object(b.AptBackend, 'metadata', return_value=[{'Package': 'example', 'Version': '2.0-1', 'Architecture': 'amd64'}]), \
                        contextlib.redirect_stdout(output):
                    b.apt_foreground(self.paths, action, values, self.runner)
                if action != 'autoremove':
                    self.assertFalse(any('autoremove' in call.args[0] for call in self.runner.run.call_args_list))

    @mock.patch.object(b.AptBackend, 'installed', return_value=INSTALLED)
    def test_foreground_configuration_uses_one_batched_state_read(self, installed):
        pending = {'pending:amd64': b.package_record('apt', 'pending:amd64', 'pending', '1.0-1', architecture='amd64', dpkgState='unpacked')}
        for architecture in ('amd64', 'all'):
            with self.subTest(candidate_architecture=architecture):
                preview = 'Conf pending (2.0-1 Test:stable [' + architecture + '])\n'
                self.runner.run.side_effect = lambda argv, **kw: completed(stdout=preview if '--simulate' in argv else '')
                output = io.StringIO()
                with mock.patch.object(b.AptBackend, 'package_states', return_value=pending) as states, \
                        mock.patch.object(b, 'confirm'), contextlib.redirect_stdout(output):
                    b.apt_foreground(self.paths, 'upgrade', [], self.runner)
                states.assert_called_once_with()
                self.assertIn('pending:amd64 1.0-1', output.getvalue())
                self.assertNotIn('2.0-1', output.getvalue())

    def test_standalone_configuration_uses_dpkg_architecture_and_rejects_ambiguity(self):
        pending = dict(INSTALLED['example:amd64'], dpkgState='unpacked')
        for identifier in ('example', 'example:amd64'):
            for remaining_config in (False, True):
                with self.subTest(identifier=identifier, remaining_config=remaining_config):
                    data = {'example:amd64': pending}
                    if remaining_config:
                        data['example:all'] = dict(pending, nativeId='example:all', architecture='all', dpkgState='config-files')
                    text = 'Conf ' + identifier + ' (2.0-1 Test:stable [all])\n'
                    changes = b.parse_simulation(text, {}, configure=True, package_data=data)
                    self.assertEqual([(row['nativeId'], row['architecture'], row['candidateVersion']) for row in changes],
                                     [('example:amd64', 'amd64', '1.0-1')])
        data = {'example:amd64': pending,
                'example:i386': dict(pending, nativeId='example:i386', architecture='i386')}
        with self.assertRaises(b.BackendError):
            b.parse_simulation('Conf example (2.0-1 Test:stable [all])\n', {}, configure=True, package_data=data)

    def test_matching_install_keeps_selected_architecture(self):
        data = {'example:amd64': dict(INSTALLED['example:amd64'], dpkgState='unpacked')}
        records = ['Inst example [1.0-1] (2.0-1 Test:stable [all])\n',
                   'Conf example (2.0-1 Test:stable [all])\n']
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                changes = b.parse_simulation(''.join(reversed(records) if reverse else records), {},
                                             configure=True, package_data=data)
                self.assertEqual([(row['action'], row['nativeId'], row['candidateVersion']) for row in changes],
                                 [('Inst', 'example:all', '2.0-1')])

    def test_other_architecture_install_preserves_standalone_configuration(self):
        data = {'example:amd64': dict(INSTALLED['example:amd64'], dpkgState='unpacked')}
        text = ('Inst example:i386 (2.0-1 Test:stable [i386])\n'
                'Conf example (2.0-1 Test:stable [all])\n'
                'Conf example:i386 (2.0-1 Test:stable [i386])\n')
        changes = b.parse_simulation(text, {}, configure=True, package_data=data)
        groups, output = capture_report(changes)
        self.assertEqual([row['nativeId'] for row in groups['install']], ['example:i386'])
        self.assertEqual([row['nativeId'] for row in groups['configure']], ['example:amd64'])
        self.assertIn('example:amd64 1.0-1', output)

    @mock.patch.object(b.AptBackend, 'installed', return_value=INSTALLED)
    def test_config_files_metadata_does_not_turn_install_into_downgrade(self, installed):
        data = {
            'remaining-config:amd64': b.package_record('apt', 'remaining-config:amd64', 'remaining-config',
                                                       '3.0-1', architecture='amd64', dpkgState='config-files'),
            'pending:amd64': b.package_record('apt', 'pending:amd64', 'pending', '1.0-1',
                                              architecture='amd64', dpkgState='unpacked'),
        }
        preview = ('Inst remaining-config (2.0-1 Test:stable [amd64])\n'
                   'Conf remaining-config (2.0-1 Test:stable [amd64])\n'
                   'Conf pending (1.0-1 Test:stable [amd64])\n')
        self.runner.run.side_effect = lambda argv, **kw: native_runner(argv) if '--compare-versions' in argv else completed(stdout=preview if '--simulate' in argv else '')
        output = io.StringIO()
        with mock.patch.object(b.AptBackend, 'package_states', return_value=data) as states, \
                mock.patch.object(b, 'confirm') as confirm, contextlib.redirect_stdout(output):
            b.apt_foreground(self.paths, 'upgrade', [], self.runner)
        states.assert_called_once_with()
        self.assertIn('Install (1)', output.getvalue())
        self.assertIn('Downgrade (0)', output.getvalue())
        self.assertIn('remaining-config:amd64 -> 2.0-1', output.getvalue())
        confirm.assert_called_once_with('Run this APT operation?')

    @mock.patch.object(b.AptBackend, 'installed', return_value=INSTALLED)
    def test_removal_with_configuration_is_rejected_before_confirmation(self, installed):
        states = {key: dict(value, dpkgState='installed') for key, value in INSTALLED.items()}
        for operation, action in (('Remv', 'remove'), ('Purg', 'purge')):
            for reverse in (False, True):
                with self.subTest(operation=operation, reverse=reverse):
                    records = [operation + ' other [1]\n', 'Conf other (1 Test:stable [amd64])\n']
                    preview = ''.join(reversed(records) if reverse else records)
                    self.runner.reset_mock()
                    self.runner.run.side_effect = lambda argv, **kw: completed(stdout=preview if '--simulate' in argv else '')
                    with mock.patch.object(b.AptBackend, 'package_states', return_value=states), \
                            mock.patch.object(b, 'confirm') as confirm, contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(b.BackendError) as raised:
                            b.apt_foreground(self.paths, action, ['other:amd64'], self.runner)
                    self.assertEqual(raised.exception.category, 'invalid-output')
                    confirm.assert_not_called()
                    self.assertFalse(any(action in call.args[0] and '--simulate' not in call.args[0]
                                         for call in self.runner.run.call_args_list))

    @mock.patch.object(b.AptBackend, 'installed', return_value=INSTALLED)
    def test_preview_stderr_is_redacted_at_the_process_boundary(self, installed):
        for action in ('upgrade', 'upgrade-package'):
            for exit_code in (0, 100):
                with self.subTest(action=action, exit_code=exit_code):
                    warning = ('preview-warning password=fixture-password token=fixture-token '
                               'https://user:fixture-credential@example.invalid/repo\n')
                    program = ('import sys\nsys.stdout.write(' + repr(UPGRADE) + ')\n'
                               'sys.stderr.write(' + repr(warning) + ')\nsys.exit(' + str(exit_code) + ')\n')
                    class PreviewRunner(b.Runner):
                        def run(self, argv, **kwargs):
                            if argv[0] == 'sudo':
                                if '--simulate' in argv:
                                    return super().run(['/usr/bin/python3', '-c', program], **kwargs)
                                return completed()
                            return super().run(argv, **kwargs)

                    output = io.StringIO()
                    diagnostic = ''
                    with (self.root / 'preview-stderr.txt').open('w+') as terminal_errors:
                        saved_stderr = os.dup(2)
                        try:
                            os.dup2(terminal_errors.fileno(), 2)
                            with mock.patch.object(b.AptBackend, 'marks', return_value=set()), \
                                    mock.patch.object(b, 'confirm') as confirm, contextlib.redirect_stdout(output):
                                values = ['example:amd64'] if action == 'upgrade-package' else []
                                if exit_code:
                                    with self.assertRaises(b.BackendError) as raised:
                                        b.apt_foreground(self.paths, action, values, PreviewRunner())
                                    diagnostic = str(raised.exception)
                                    confirm.assert_not_called()
                                else:
                                    b.apt_foreground(self.paths, action, values, PreviewRunner())
                        finally:
                            os.dup2(saved_stderr, 2)
                            os.close(saved_stderr)
                        terminal_errors.seek(0)
                        combined = output.getvalue() + terminal_errors.read() + diagnostic
                    for secret in ('fixture-password', 'fixture-token', 'fixture-credential'):
                        self.assertNotIn(secret, combined)
                    self.assertIn('preview-warning', combined)
                    self.assertIn('[redacted]', combined)

    def test_captured_stderr_keeps_controlling_terminal_input_available(self):
        authentication = (
            "import os, sys\n"
            "terminal = os.open('/dev/tty', os.O_RDWR)\n"
            "os.write(terminal, b'fixture-auth> ')\n"
            "assert os.read(terminal, 100).strip() == b'fixture-answer'\n"
            "os.close(terminal)\n"
            "print('authenticated')\n"
            "sys.stderr.write('captured-warning\\n')\n"
        )
        program = (
            "import fcntl, sys, termios\n"
            "from test_backends import b\n"
            "fcntl.ioctl(0, termios.TIOCSCTTY, 0)\n"
            "result = b.Runner().run([sys.executable, '-c', " + repr(authentication) + "], "
            "foreground=True, capture=True, capture_stderr=True, timeout=5)\n"
            "assert result.stdout == 'authenticated\\n'\n"
            "assert result.stderr == 'captured-warning\\n'\n"
            "print('fixture-done')\n"
        )
        master, slave = pty.openpty()
        with os.fdopen(master, 'rb', buffering=0) as terminal, os.fdopen(slave, 'rb') as input_terminal:
            process = subprocess.Popen(
                [sys.executable, '-c', program], cwd=ROOT / 'tests', stdin=input_terminal,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            )
            try:
                prompt = b''
                deadline = time.monotonic() + 5
                while b'fixture-auth> ' not in prompt and time.monotonic() < deadline:
                    ready, _, _ = select.select([terminal], [], [], max(0, deadline - time.monotonic()))
                    if ready:
                        prompt += os.read(terminal.fileno(), 4096)
                self.assertIn(b'fixture-auth> ', prompt)
                os.write(terminal.fileno(), b'fixture-answer\n')
                output, _ = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, output)
                self.assertIn('fixture-done', output)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate(timeout=5)


@unittest.skipUnless(shutil.which("apt-get"), "APT is not installed.")
class NativeSummaryTests(TemporaryCase):
    def setUp(self):
        self.fixture = test_support.NativeAptTests()
        self.fixture.setUp()
        for name in ("tmp", "root", "paths", "runner", "repo", "config"):
            setattr(self, name, getattr(self.fixture, name))

    native = test_support.NativeAptTests.native

    def test_standalone_configuration_uses_actual_unpacked_version(self):
        status = self.root / "status"
        status.write_text(status.read_text().replace("install ok installed", "install ok unpacked", 1))
        result = self.native(["--simulate", "install", "other:amd64"], check=True)
        self.assertIn("Conf example (2.0-1", result.stdout)
        self.assertNotIn("Inst example", result.stdout)
        data = {"example:amd64": dict(INSTALLED["example:amd64"], dpkgState="unpacked")}
        changes = b.parse_simulation(result.stdout, {}, configure=True, package_data=data)
        groups, output = capture_report(changes)
        self.assertEqual(groups["configure"][0]["candidateVersion"], "1.0-1")
        self.assertFalse(groups["upgrade"] or groups["downgrade"])
        self.assertIn("example:amd64 1.0-1", output)

    def test_standalone_configuration_uses_actual_architecture_when_candidate_changes(self):
        status = self.root / 'status'
        status.write_text(status.read_text().replace('install ok installed', 'install ok unpacked', 1))
        packages = self.repo / 'dists/stable/main/binary-amd64/Packages'
        packages.write_text(packages.read_text().replace('Architecture: amd64', 'Architecture: all', 1))
        self.native(['--error-on=any', 'update'], check=True)
        result = self.native(['--simulate', 'install', 'other:amd64'], check=True)
        self.assertRegex(result.stdout, r'Conf example \(2\.0-1 .*\[all\]\)')
        self.assertNotIn('Inst example', result.stdout)
        data = {'example:amd64': dict(INSTALLED['example:amd64'], dpkgState='unpacked')}
        changes = b.parse_simulation(result.stdout, {}, configure=True, package_data=data)
        groups, output = capture_report(changes)
        self.assertEqual([(row['nativeId'], row['candidateVersion']) for row in groups['configure']],
                         [('example:amd64', '1.0-1')])
        self.assertFalse(groups['install'] or groups['upgrade'] or groups['downgrade'])
        self.assertIn('example:amd64 1.0-1', output)
        self.assertNotIn('example:all', output)

    def test_config_files_reinstall_with_pending_configuration_is_install(self):
        status = self.root / 'status'
        status.write_text(status.read_text().replace('install ok installed', 'install ok unpacked', 1) +
                          'Package: remaining-config\nStatus: deinstall ok config-files\n'
                          'Architecture: amd64\nVersion: 3.0-1\nDescription: Remaining configuration\n\n')
        packages = self.repo / 'dists/stable/main/binary-amd64/Packages'
        with packages.open('a') as stream:
            stream.write('Package: remaining-config\nVersion: 2.0-1\nArchitecture: amd64\n'
                         'Maintainer: Test <test@example.invalid>\nFilename: remaining-config.deb\n'
                         'Size: 1\nMD5sum: 00000000000000000000000000000000\nDescription: Reinstall fixture\n\n')
        self.native(['--error-on=any', 'update'], check=True)
        result = self.native([*b.APT_PREVIEW_OPTIONS, '--simulate', '--no-remove', 'install', 'remaining-config:amd64'], check=True)
        self.assertIn('Inst remaining-config (2.0-1', result.stdout)
        self.assertIn('Conf example (2.0-1', result.stdout)
        self.assertNotIn('Inst example', result.stdout)
        data = {
            'example:amd64': dict(INSTALLED['example:amd64'], dpkgState='unpacked'),
            'remaining-config:amd64': b.package_record('apt', 'remaining-config:amd64', 'remaining-config',
                                                       '3.0-1', architecture='amd64', dpkgState='config-files'),
        }
        changes = b.parse_simulation(result.stdout, {'other:amd64': INSTALLED['other:amd64']},
                                     configure=True, package_data=data)
        groups, output = capture_report(changes)
        self.assertEqual(len(groups['install']), 1)
        self.assertFalse(groups['downgrade'])
        self.assertIn('remaining-config:amd64 -> 2.0-1', output)

    def test_quiet_can_hide_nonempty_candidates_and_normalization_restores_them(self):
        args = [*b.APT_PREVIEW_OPTIONS, "--simulate", "--no-remove", "--with-new-pkgs", "upgrade"]
        empty = self.native(args, check=True)
        self.assertNotIn("no longer required", empty.stdout)
        self.assertTrue(b.apt_information(empty.stdout)["summary"])
        with (self.root / "status").open('a') as stream:
            stream.write("Package: unused-example\nStatus: install ok installed\nArchitecture: amd64\nVersion: 1\nDescription: Unused fixture\n\n")
        (self.root / "extended_states").write_text("Package: unused-example\nArchitecture: amd64\nAuto-Installed: 1\n\n")
        hidden = self.native(["-o", "quiet=2", "-o", "APT::Get::HideAutoRemove=false", "--simulate", "upgrade"], check=True)
        self.assertNotIn("unused-example", hidden.stdout)
        _, output = capture_report([], b.apt_information(hidden.stdout))
        self.assertIn("Candidate list unavailable", output)
        for inherited in ("true", "small"):
            shown = self.native(["-o", "quiet=2", "-o", "APT::Get::HideAutoRemove=" + inherited, *args], check=True)
            self.assertEqual(b.apt_information(shown.stdout)["autoremove"], ["unused-example"])

    def test_native_cleanup_policy_and_explicit_autoremove(self):
        apt_version = subprocess.run(["apt-get", "--version"], capture_output=True, text=True, check=True).stdout.split()[1]
        installed = {"apt:amd64": b.package_record("apt", "apt:amd64", "apt", apt_version, architecture="amd64")}
        runner = b.Runner()
        settings = {"sudoBin": "/usr/bin/env"}
        pins = ["-c", str(self.config)]
        self.assertEqual(b.apt_preview_policy(installed, pins, settings, runner), apt_version == "3.2.0")
        with self.config.open('a') as stream:
            stream.write('APT::Get::AutomaticRemove "true";\n')
        self.assertFalse(b.apt_preview_policy(installed, pins, settings, runner))
        result = self.native([*b.APT_PREVIEW_OPTIONS, "--simulate", "autoremove"], check=True)
        _, output = capture_report(b.parse_simulation(result.stdout, INSTALLED), b.apt_information(result.stdout), autoremove=True)
        self.assertIn("Optional cleanup: Not applicable", output)


class SummaryTranslationTests(TemporaryCase):
    def test_all_catalogs_translate_affected_messages_and_keep_counts(self):
        paths = sorted((ROOT / 'package/translate/po').glob('*.po'))
        self.assertEqual(len(paths), 14)
        for path in paths:
            with self.subTest(locale=path.stem):
                messages, fuzzy = catalog_messages(path)
                for message in REPORT_MESSAGES:
                    self.assertTrue(messages.get(message), (path, message))
                    self.assertNotIn(message, fuzzy)
                mo = self.root / path.stem / 'LC_MESSAGES/report.mo'
                write_catalog(mo, {key: messages[key] for key in ('', *REPORT_MESSAGES)})
                with mo.open('rb') as stream:
                    translator = gettext.GNUTranslations(stream)
                for count in (0, 1, 2, 5, 22):
                    text = '\n'.join(f"Inst package-{i} (1 Test:stable [all])" for i in range(count))
                    with mock.patch.object(b, '_', translator.gettext):
                        _, output = capture_report(b.parse_simulation(text, {}))
                    self.assertIn(messages['Install'] + f' ({count})', output)
                info = b.apt_information("The following package was automatically installed and is no longer required:\n"
                                         "  example\nUse 'sudo apt autoremove' to remove it.\n" + SUMMARY)
                with mock.patch.object(b, '_', translator.gettext):
                    _, output = capture_report([], info, INSTALLED)
                for message in ('Optional cleanup', 'These packages will not be removed during this operation.',
                                'You can remove them with a separate autoremove operation.'):
                    self.assertIn(messages[message], output)

    def test_session_preferences_regional_fallback_and_new_language(self):
        for language, value in (("de", "Installieren"), ("pl", "Instalacja"), ("eo", "Instali")):
            write_catalog(self.root / language / 'LC_MESSAGES/report.mo',
                          {'': 'Content-Type: text/plain; charset=UTF-8\n', 'Install': value})
        for preference, expected in (("de_DE:pl", "Installieren"), ("zz:pl_PL", "Instalacja"), ("eo", "Instali"), ("zz", "Install")):
            with mock.patch.dict(os.environ, {'LANGUAGE': preference, 'LC_ALL': 'C', 'LANG': 'C'}):
                translator = gettext.translation('report', self.root, fallback=True)
                with mock.patch.object(b, '_', translator.gettext):
                    _, output = capture_report([])
                self.assertIn(expected + ' (0)', output)
                self.assertIn('Candidate list unavailable', output)
        with mock.patch.dict(os.environ, {'LANGUAGE': 'pl_PL', 'LC_ALL': 'pl_PL.UTF-8'}):
            result = b.Runner().run(['/usr/bin/python3', '-c', 'import os; print(os.environ["LC_ALL"], os.environ["LANGUAGE"])'], foreground=True)
            self.assertEqual(result.stdout.strip(), 'C C')
            self.assertEqual(os.environ['LANGUAGE'], 'pl_PL')
