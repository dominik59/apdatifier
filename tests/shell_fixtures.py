"""Run unchanged application scripts with private files and recorded command stubs."""

import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import shlex
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest


PROJECT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def bash_command(script, *arguments):
    """Preserve BASH_ENV and use ordinary Bash even for a sh shebang."""
    return ['bash', '--noprofile', '--norc', '--', str(script), *map(str, arguments)]


def compatible_results(bash_result, native_result, bash_files, native_files):
    """Compare observable results; Bash coverage alone is not native-sh evidence."""
    return ((bash_result.returncode, bash_result.stdout, bash_result.stderr, bash_files)
            == (native_result.returncode, native_result.stdout, native_result.stderr, native_files))


def stop_process_group(process):
    """Stop children even when their group leader has already exited."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


class ShellCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='apdatifier-shell-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.applet = self.root / 'applet'
        self.scripts = self.applet / 'contents/tools/sh'
        shutil.copytree(PROJECT / 'package/contents/tools/sh', self.scripts)
        assets = self.applet / 'contents/ui/assets/icons'
        shutil.copytree(PROJECT / 'package/contents/ui/assets/icons', assets)
        self.applet.joinpath('metadata.json').write_text(json.dumps({'KPlugin': {'Description': 'fixture'}}))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in ('bash', 'dirname', 'readlink', 'grep', 'sed', 'cat', 'find', 'head', 'tail', 'uniq',
                     'jq', 'mkdir', 'rm', 'mktemp', 'mv', 'tr', 'paste', 'seq', 'basename', 'tar',
                     'unzip', 'xz', 'date', 'cut', 'awk', 'sort', 'ln', 'uname', 'stty', 'touch', 'cp', 'rmdir'):
            target = shutil.which(name)
            if target:
                self.bin.joinpath(name).symlink_to(target)
        self.config = self.root / 'config'
        self.cache = self.root / 'cache'
        self.local = self.root / 'local'
        for directory in (self.config, self.cache, self.local):
            directory.mkdir()
        self.log = self.root / 'commands.jsonl'
        self.env = dict(os.environ, PATH=str(self.bin), TERM='dumb', TMPDIR=str(self.root),
                        APDATIFIER_CONFIG_DIR=str(self.config), APDATIFIER_CACHE_DIR=str(self.cache),
                        XDG_LOCAL_HOME=str(self.local), APDATIFIER_SHELL_ROOT=str(self.root),
                        APDATIFIER_SHELL_LOG=str(self.log),
                        APDATIFIER_MIRRORLIST_FILE=str(self.root / 'mirrorlist'),
                        APDATIFIER_PACMAN_LOG_FILE=str(self.root / 'pacman.log'))
        self.env.pop('POSIXLY_CORRECT', None)
        self.settings()
        for name in ('pacman', 'pacman-conf', 'flatpak', 'fwupdmgr', 'curl', 'xmllint', 'git',
                     'kpackagetool6', 'sudo', 'qdbus6', 'tmux', 'systemd-inhibit'):
            self.stub(name, "root.joinpath('unexpected-command').write_text(name+' '+repr(args))\n"
                            "raise SystemExit('UNEXPECTED native command: '+name+' '+repr(args))")
        for name in ('sleep', 'tput', 'clear'):
            self.stub(name, 'pass')
        self.stub('gettext', 'print(args[0], end="")')
        self.stub('column', 'sys.stdout.write(sys.stdin.read())')
        self.stub('getent', 'print("127.0.0.1 fixture.invalid")')
        self.stub('qdbus6', 'print("false" if any("visible" in a for a in args) else "42")')
        self.scripts.parent.joinpath('backends.py').write_text('''import json, os, pathlib, sys
with open(os.environ['APDATIFIER_SHELL_LOG'], 'a') as stream:
    stream.write(json.dumps({'name': 'helper', 'args': sys.argv[1:]})+'\\n')
sys.exit(0)
''')

    def settings(self, **overrides):
        values = dict(termFont='false', terminal='konsole', tmuxSession='false', sudoBin='sudo',
                      arch='false', aur='false', flatpak='false', widgets='false', fwupd='false',
                      apt='false', snap='false', mirrors='false', restartShell='false',
                      rebootSystem='false', idleInhibit='false', wrapper='', archFlags='',
                      flatpakFlags='', flatpakRemoveUnused='false', mngHideFlatpak='false',
                      mngHideHeaders='false', mngHideNums='false', mngHideHelp='false',
                      widgetConfirmation='false', mirrorProgress='true', mirrorCount='2',
                      mirrorsAge='1', dynamicUrl='https://fixture.invalid/mirrors', feedsFetchCount='2')
        values.update(overrides)
        self.config.joinpath('config.conf').write_text(''.join(f'{key}={shlex.quote(str(value))}\n'
                                                            for key, value in values.items()))

    def tearDown(self):
        marker = self.root / 'unexpected-command'
        self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else '')

    def stub(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()
        path.write_text('''#!/usr/bin/python3
import json, os, pathlib, shutil, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
root = pathlib.Path(os.environ['APDATIFIER_SHELL_ROOT'])
with open(os.environ['APDATIFIER_SHELL_LOG'], 'a') as stream:
    stream.write(json.dumps({'name': name, 'args': args})+'\\n')
''' + body + '\n')
        path.chmod(0o700)

    def calls(self, name):
        return [entry['args'] for line in self.log.read_text().splitlines()
                if (entry := json.loads(line))['name'] == name] if self.log.exists() else []

    def run_script(self, name, *args, input='', env=None, timeout=15):
        return self.capture(bash_command(self.scripts / name, *args), input=input,
                            env=dict(self.env, **(env or {})), timeout=timeout)

    def function(self, body, input='', timeout=15):
        return self.capture(['bash', '--noprofile', '--norc', '-c', 'source "$0"\n'+body,
                             str(self.scripts / 'utils')], input=input, env=self.env, timeout=timeout)

    def capture(self, command, *, input, env, timeout):
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=env, cwd=self.root,
                              start_new_session=True) as process:
            try:
                stdout, stderr = process.communicate(input=input, timeout=timeout)
            finally:
                stop_process_group(process)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        self.assertNotIn('UNEXPECTED native command', result.stdout + result.stderr)
        return result

    def interact(self, name, arguments, steps, rows=40, timeout=15):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, 140, 0, 0))
        process = subprocess.Popen(bash_command(self.scripts / name, *arguments), stdin=slave,
                                   stdout=slave, stderr=slave, env=self.env, cwd=self.root,
                                   start_new_session=True)
        os.close(slave)
        output = b''
        cursor = 0
        deadline = time.monotonic() + timeout
        pending = iter(steps)
        step = next(pending, None)
        try:
            while True:
                clean = ANSI.sub('', output.decode(errors='replace')).replace('\r', '')
                if step and (position := clean.find(step[0], cursor)) >= 0:
                    cursor = position + len(step[0])
                    os.write(master, step[1].encode())
                    step = next(pending, None)
                    continue
                if time.monotonic() > deadline:
                    self.fail(f'Terminal timeout waiting for {step!r}:\n{clean[-3000:]}')
                if select.select([master], [], [], .05)[0]:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    if not data:
                        break
                    output += data
                elif process.poll() is not None:
                    break
            self.assertIsNone(step, f'Unconsumed terminal step {step!r}')
            code = process.wait(timeout=2)
            clean = ANSI.sub('', output.decode(errors='replace')).replace('\r', '')
            self.assertNotIn('UNEXPECTED native command', clean)
            return subprocess.CompletedProcess(process.args, code, clean, '')
        finally:
            stop_process_group(process)
            os.close(master)
