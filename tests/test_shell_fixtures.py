"""Verify process cleanup for captured-output shell fixtures."""

import os
from pathlib import Path
import signal
import subprocess
import time

from shell_fixtures import ShellCase


class CapturedProcessCleanupTests(ShellCase):
    def assert_child_stopped(self, pid):
        status = Path(f'/proc/{pid}/stat')
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                if status.read_text().split()[2] in ('Z', 'X'):
                    return
            except FileNotFoundError:
                return
            time.sleep(.01)
        self.fail(f'Fixture child {pid} is still running')

    def child_case(self, method, wait):
        self.stub('long-child', 'import time; time.sleep(60)')
        marker = self.root / 'captured-child-pid'
        marker.unlink(missing_ok=True)
        body = (('long-child &\n' if wait else 'long-child >/dev/null 2>&1 &\n')
                + 'printf "%s\\n" "$!" > "$APDATIFIER_SHELL_ROOT/captured-child-pid"\n'
                + ('wait\n' if wait else 'printf finished\n'))
        if method == 'script':
            self.scripts.joinpath('cleanup-fixture').write_text('#!/bin/bash\n'+body)
            launch = lambda: self.run_script('cleanup-fixture', timeout=6 if wait else 15)
        else:
            launch = lambda: self.function(body, timeout=6 if wait else 15)
        try:
            if wait:
                with self.assertRaises(subprocess.TimeoutExpired):
                    launch()
            else:
                result = launch()
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, 'finished')
            self.assertTrue(marker.exists(), 'The background child was not started')
            self.assert_child_stopped(int(marker.read_text()))
        finally:
            if marker.exists():
                try:
                    os.kill(int(marker.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_timeout_stops_children_of_scripts_and_functions(self):
        for method in ('script', 'function'):
            with self.subTest(method=method):
                self.child_case(method, wait=True)

    def test_normal_completion_stops_remaining_background_children(self):
        for method in ('script', 'function'):
            with self.subTest(method=method):
                self.child_case(method, wait=False)
