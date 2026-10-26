"""Filesystem setup, terminal launch boundaries, and mirror ranking regressions."""

import json
import os
from pathlib import Path
import shlex
import time

from shell_fixtures import ShellCase


class SetupAndTerminalTests(ShellCase):
    def test_terminal_timeout_stops_its_background_child(self):
        script = self.scripts / 'timeout-fixture'
        script.write_text('''#!/bin/bash
/usr/bin/python3 -c 'import os,pathlib,time; pathlib.Path(os.environ["APDATIFIER_SHELL_ROOT"],"child-pid").write_text(str(os.getpid())); print("ready",flush=True); time.sleep(60)' &
wait
''')
        with self.assertRaisesRegex(AssertionError, 'Terminal timeout'):
            self.interact('timeout-fixture', [], [('never printed','q')], timeout=.5)
        pid = int(self.root.joinpath('child-pid').read_text())
        status = Path(f'/proc/{pid}/stat')
        deadline = time.monotonic()+1
        while status.exists() and time.monotonic()<deadline:
            if status.read_text().split()[2] in ('Z','X'):
                break
            time.sleep(.01)
        self.assertTrue(not status.exists() or status.read_text().split()[2] in ('Z','X'))

    def test_setup_migrates_cache_and_preserves_existing_files(self):
        self.config.joinpath('updates.json').write_text('[1]')
        self.config.joinpath('news.json').write_text('[2]')
        result = self.run_script('init')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cache.joinpath('updates.json').read_text(), '[1]')
        self.assertEqual(self.cache.joinpath('news.json').read_text(), '[2]')
        icons = self.local / 'icons/breeze/status/22'
        self.assertEqual(len(list(icons.glob('*.svg'))), 4)
        icon = icons / 'apdatifier-plasmoid.svg'
        icon.write_text('custom icon')
        self.config.joinpath('updates.json').write_text('[3]')
        self.assertEqual(self.run_script('init').returncode, 0)
        self.assertEqual(icon.read_text(), 'custom icon')
        self.assertEqual(self.cache.joinpath('updates.json').read_text(), '[1]')
        self.assertIn('Action=Popup|Sound', self.local.joinpath('knotifications6/apdatifier.notifyrc').read_text())

    def test_first_setup_creates_missing_directories_and_configuration(self):
        self.config.joinpath('config.conf').unlink()
        self.config.rmdir()
        self.cache.rmdir()
        result = self.run_script('init')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.config.joinpath('config.conf').is_file())
        self.assertTrue(self.cache.is_dir())

    def test_terminal_variants_quote_script_arguments_as_data(self):
        values = ['apt-pkg', 'name with spaces', "quote'\"", '$(touch forbidden)']
        for terminal, separator in [('konsole', '-e'), ('gnome-terminal', '--'),
                                    ('ptyxis', '--'), ('terminator', '-x')]:
            with self.subTest(terminal=terminal):
                self.settings(terminal=terminal)
                self.stub(terminal, 'pass')
                self.assertEqual(self.run_script('terminal', 'upgrade', *values).returncode, 0)
                args = self.calls(terminal)[-1]
                self.assertEqual(args[:3], [separator, 'bash', '-c'])
                self.assertEqual(shlex.split(args[3]), [str(self.scripts / 'upgrade'), *values])
        self.assertEqual(self.run_script('terminal', 'invalid').returncode, 2)
        self.assertFalse(self.root.joinpath('forbidden').exists())

    def test_flatpak_terminal_and_yakuake_preserve_native_arguments(self):
        self.settings(terminal='flatpak://org.example.Terminal/konsole')
        self.stub('flatpak', 'pass')
        result = self.run_script('terminal', 'management', 'apt')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('flatpak')[-1][:4], ['run', '--command=konsole', 'org.example.Terminal', '-e'])
        self.settings(terminal='yakuake')
        self.assertEqual(self.run_script('terminal', 'upgrade', 'snap').returncode, 0)
        commands = self.calls('qdbus6')
        self.assertTrue(any('runCommandInTerminal' in a for a in commands))
        self.assertTrue(any('org.kde.yakuake.toggleWindowState' in a for a in commands))

    def test_tmux_creates_only_missing_sessions_and_windows(self):
        self.stub('konsole', 'pass')
        for mode, operation, terminal in [('absent', 'new-session', 'konsole'),
                                          ('window', 'new-window', 'konsole'),
                                          ('existing', None, 'konsole'), ('absent', 'new-session', 'yakuake')]:
            with self.subTest(mode=mode, terminal=terminal):
                self.log.unlink(missing_ok=True)
                self.settings(terminal=terminal, tmuxSession='true')
                self.stub('tmux', f'''if args[0] == 'has-session': sys.exit({1 if mode == 'absent' else 0})
if args[0] == 'list-windows': print({'Upgrade' if mode == 'existing' else 'Other'!r})''')
                self.assertEqual(self.run_script('terminal', 'upgrade', 'snap').returncode, 0)
                created = [a[0] for a in self.calls('tmux') if a[0] in ('new-session', 'new-window')]
                self.assertEqual(created, [operation] if operation else [])

    def test_icon_font_and_translations_load_without_executing_values(self):
        self.settings(termFont='true')
        self.stub('gettext', 'print("translated:"+args[0], end="")')
        result = self.function('printf "%s\\n%s\\n" "$ICO_ERR" "$MNG_HEADER"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('translated:Management', result.stdout)
        self.assertNotIn('✘', result.stdout)


class UpgradeBoundaryTests(ShellCase):
    def test_critical_package_changes_request_reboot_without_rebooting_the_host(self):
        self.settings(rebootSystem='true')
        self.stub('pacman', '''if args == ['-Qq']: print('linux')
elif args[0] == '-Q': print(args[1], '2' if root.joinpath('upgraded').exists() else '1')''')
        self.stub('sudo', "if '-Syu' in args: root.joinpath('upgraded').touch()")
        result = self.run_script('upgrade','system',input='n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('linux', result.stdout)
        self.assertFalse(self.calls('qdbus6'))
        self.root.joinpath('upgraded').unlink()
        result = self.run_script('upgrade','system',input='y\n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['org.kde.Shutdown','/Shutdown','logoutAndReboot'], self.calls('qdbus6'))

    def test_idle_inhibition_wraps_widget_and_firmware_stages(self):
        self.settings(widgets='true', fwupd='true', idleInhibit='true')
        self.stub('sudo', 'pass')
        self.stub('systemd-inhibit', '''index = next(i for i,arg in enumerate(args) if not arg.startswith('--'))
command = args[index:]
assert pathlib.Path(command[0]).is_relative_to(root) or command[0] == 'sudo'
os.execvp(command[0], command)''')
        result = self.run_script('upgrade','full')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls('systemd-inhibit')), 2)
        self.assertIn(['fwupdmgr','update'], self.calls('sudo'))

    def test_terminal_close_and_canceled_hook_preserve_completion(self):
        self.settings(terminal='yakuake')
        result = self.interact('upgrade',['apt'], [('Press Enter to close','\n')])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(any('removeSession' in args for args in self.calls('qdbus6')))
        self.settings(preExec='exit 130', postExec='printf done > "$APDATIFIER_SHELL_ROOT/post-hook"')
        result = self.run_script('upgrade','apt')
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual(self.root.joinpath('post-hook').read_text(), 'done')
        self.assertFalse(any(a[0] == 'foreground' for a in self.calls('helper')[-5:]))


class MirrorTests(ShellCase):
    def setUp(self):
        super().setUp()
        self.settings(mirrors='force')
        self.mirror = self.root / 'mirrorlist'
        self.responses = self.root / 'mirror-responses.json'
        self.data = self.root / 'mirror-data'
        self.stub('curl', '''if '-w' in args:
    from urllib.parse import urlparse
    host = urlparse(args[args.index('-w')+2]).hostname
    response = json.loads(root.joinpath('mirror-responses.json').read_text())[host]
    print(response[0], end='')
    sys.exit(response[1])
pathlib.Path(args[args.index('-o')+1]).write_text(root.joinpath('mirror-data').read_text())
''')
        self.stub('sudo', '''if args == ['-n', 'true']: sys.exit(0)
assert args[0] == 'tee', args
target = pathlib.Path(args[1])
if not target.is_relative_to(root): raise SystemExit('Unsafe mirror target')
if root.joinpath('write-failure').exists(): sys.exit(13)
target.write_text(sys.stdin.read())''')

    def mirrors(self, entries):
        self.responses.write_text(json.dumps(entries))
        self.data.write_text('\n'.join(f'Server = https://{host}/$repo/os/$arch' for host in entries)+'\n')

    def test_bad_server_does_not_hide_a_later_success_and_results_are_sorted(self):
        self.mirrors({'bad.invalid': ['0.1 503', 0], 'slow.invalid': ['0.5 200', 0],
                      'fast.invalid': ['0.01 200', 0], 'third.invalid': ['0.7 200', 0]})
        result = self.run_script('mirrorlist')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        servers = [line for line in self.mirror.read_text().splitlines() if line.startswith('Server')]
        self.assertEqual(len(servers), 2)
        self.assertIn('fast.invalid', servers[0])
        self.assertIn('slow.invalid', servers[1])
        self.assertNotIn('bad.invalid', self.mirror.read_text())

    def test_curl_exit_code_blocks_a_partial_success_response(self):
        self.mirrors({'partial.invalid': ['0.01 200', 18], 'good.invalid': ['0.02 200', 0]})
        result = self.run_script('mirrorlist')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('partial.invalid', self.mirror.read_text())
        self.assertIn('good.invalid', self.mirror.read_text())

    def test_fresh_age_policy_and_declined_confirmation_do_not_download(self):
        self.mirror.write_text('existing')
        self.settings(mirrors='age')
        self.assertEqual(self.run_script('mirrorlist').returncode, 0)
        self.assertFalse(self.calls('curl'))
        self.settings(mirrors='ask')
        self.assertEqual(self.run_script('mirrorlist', input='n\n').returncode, 0)
        self.assertEqual(self.mirror.read_text(), 'existing')
        self.assertFalse(self.calls('sudo'))

    def test_invalid_list_write_failure_and_background_progress(self):
        self.mirror.write_text('existing')
        self.data.write_text('not a mirror list')
        self.assertNotEqual(self.run_script('mirrorlist').returncode, 0)
        self.assertEqual(self.mirror.read_text(), 'existing')
        self.mirrors({'good.invalid': ['0.02 200', 0]})
        self.root.joinpath('write-failure').touch()
        self.settings(mirrors='force', mirrorProgress='false')
        self.assertNotEqual(self.run_script('mirrorlist').returncode, 0)
        self.assertEqual(self.mirror.read_text(), 'existing')
        self.root.joinpath('write-failure').unlink()
        self.assertEqual(self.run_script('mirrorlist').returncode, 0)

    def test_old_list_confirmation_and_return_to_management(self):
        self.mirror.write_text('old')
        os.utime(self.mirror, (1, 1))
        self.mirrors({'good.invalid': ['0.02 200', 0]})
        self.settings(mirrors='age')
        self.assertEqual(self.run_script('mirrorlist', input='what\ny\n').returncode, 0)
        result = self.run_script('mirrorlist', 'menu', '7', input='n\n\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(['management', '7'], self.calls('helper'))
