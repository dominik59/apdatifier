"""Check shell fixtures with an interactive parent, as in a developer terminal."""

import os
from pathlib import Path
import pty
import signal
import subprocess
import sys
import tempfile
import unittest


class TerminalInputTests(unittest.TestCase):
    def test_shell_lifecycle_fixtures_do_not_read_the_parent_terminal(self):
        tests = Path(__file__).resolve().parent
        program = """
import os
import unittest

assert os.isatty(0), "The regression check needs terminal input."
suite = unittest.defaultTestLoader.loadTestsFromNames([
    "test_backends.ShellLifecycleTests.test_single_flatpak_update_preserves_its_native_reference_and_scope",
    "test_widgets.WidgetUpdateTests.test_terminal_lifecycle_records_archive_failure",
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
"""
        with tempfile.TemporaryDirectory(prefix="apdatifier-terminal-test-") as temporary:
            master, slave = pty.openpty()
            with os.fdopen(master, "rb"), os.fdopen(slave, "rb") as terminal:
                process = subprocess.Popen(
                    [sys.executable, "-c", program], cwd=tests, stdin=terminal,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    start_new_session=True,
                    env=dict(os.environ, TMPDIR=temporary, PYTHONDONTWRITEBYTECODE="1"),
                )
                try:
                    output, _ = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    output, _ = process.communicate(timeout=5)
                    self.fail("Shell fixtures waited for terminal input:\n" + output)
                self.assertEqual(process.returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
