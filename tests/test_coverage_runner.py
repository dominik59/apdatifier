"""Bootstrap checks use substitute interpreters, never pip or live environments."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class CoverageRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="apdatifier-bootstrap-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project with spaces"
        self.root.mkdir()
        self.root.joinpath("tests").mkdir()
        self.script = self.root / "tests/run_coverage.sh"
        source = Path(__file__).resolve().parent / "run_coverage.sh"
        shutil.copy2(source, self.script)
        self.requirements = self.root / "requirements-test.txt"
        self.requirements.write_text("coverage==7.17.0\n")
        self.log = self.root / "commands.jsonl"
        self.base = self.root / "base python"
        self.base.write_text(r'''#!/usr/bin/python3
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
with open(os.environ['APDATIFIER_BOOTSTRAP_LOG'], 'a') as stream:
    stream.write(json.dumps({'program': str(pathlib.Path(sys.argv[0]).resolve()), 'args': args}) + '\n')
if args[:2] == ['-m', 'venv']:
    if os.environ.get('APDATIFIER_BOOTSTRAP_CREATE_FAIL'):
        sys.exit(3)
    target = pathlib.Path(args[2])
    (target / 'bin').mkdir(parents=True)
    shutil.copy2(__file__, target / 'bin/python')
    (target / 'pyvenv.cfg').write_text('home = fixture\n')
    (target / 'pip-ready').touch()
elif args[:2] == ['-m', 'ensurepip']:
    pathlib.Path(__file__).resolve().parents[1].joinpath('pip-ready').touch()
elif args[:2] == ['-m', 'pip']:
    root = pathlib.Path(__file__).resolve().parents[1]
    if not (root / 'pip-ready').exists():
        sys.exit(1)
    if args[2:] == ['--version']:
        sys.exit(0)
    requirements = pathlib.Path(args[args.index('-r') + 1]).read_text()
    installed = root / 'installed-requirements'
    if '--dry-run' in args:
        assert '--no-index' in args
        sys.exit(0 if installed.exists() and installed.read_text() == requirements else 1)
    if os.environ.get('APDATIFIER_BOOTSTRAP_INSTALL_FAIL'):
        sys.exit(7)
    installed.write_text(requirements)
elif args[:3] == ['-m', 'coverage', 'run']:
    sys.exit(int(os.environ.get('APDATIFIER_BOOTSTRAP_TEST_EXIT', '0')))
''')
        self.base.chmod(0o700)
        self.node = self.root / "test node"
        self.node.write_text(r'''#!/usr/bin/python3
import json, os, sys
with open(os.environ['APDATIFIER_BOOTSTRAP_LOG'], 'a') as stream:
    stream.write(json.dumps({'program': 'node', 'args': sys.argv[1:]}) + '\n')
if sys.argv[1] == '-e' and os.environ.get('APDATIFIER_BOOTSTRAP_OLD_NODE'):
    sys.exit(2)
''')
        self.node.chmod(0o700)
        self.env = dict(os.environ, APDATIFIER_TEST_PYTHON=str(self.base), APDATIFIER_TEST_NODE=str(self.node),
                        APDATIFIER_BOOTSTRAP_LOG=str(self.log))
        for key in ("APDATIFIER_TEST_VENV", "APDATIFIER_BOOTSTRAP_CREATE_FAIL", "APDATIFIER_BOOTSTRAP_INSTALL_FAIL",
                    "APDATIFIER_BOOTSTRAP_OLD_NODE", "APDATIFIER_BOOTSTRAP_TEST_EXIT"):
            self.env.pop(key, None)

    def invoke(self):
        return subprocess.run(["bash", str(self.script)], cwd=self.root.parent, env=self.env,
                              capture_output=True, text=True, timeout=10)

    def commands(self, prefix):
        if not self.log.exists():
            return []
        return [entry for line in self.log.read_text().splitlines()
                if (entry := json.loads(line))["args"][:len(prefix)] == prefix]

    def test_fresh_environment_is_created_and_reused_without_reinstalling(self):
        for _ in range(2):
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.commands(["-m", "venv"])), 1)
        installs = [entry for entry in self.commands(["-m", "pip", "install"]) if "--dry-run" not in entry["args"]]
        self.assertEqual(len(installs), 1)
        runs = self.commands(["-m", "coverage", "run"])
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(entry["program"] == str(self.root / ".venv/bin/python") for entry in runs + installs))
        self.assertEqual(len(self.commands(["--test"])), 2)

    def test_requirement_changes_install_the_new_pin_inside_the_existing_environment(self):
        self.assertEqual(self.invoke().returncode, 0)
        self.requirements.write_text("coverage==7.18.0\n")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(len(self.commands(["-m", "venv"])), 1)
        installs = [entry for entry in self.commands(["-m", "pip", "install"]) if "--dry-run" not in entry["args"]]
        self.assertEqual(len(installs), 2)
        self.assertEqual((self.root / ".venv/installed-requirements").read_text(), self.requirements.read_text())

    def test_custom_environment_path_can_contain_spaces(self):
        target = self.root / "custom environment"
        self.env["APDATIFIER_TEST_VENV"] = str(target)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertTrue((target / "pyvenv.cfg").is_file())
        self.assertFalse((self.root / ".venv").exists())

    def test_creation_and_dependency_failures_stop_before_tests(self):
        for variable, expected in (("APDATIFIER_BOOTSTRAP_CREATE_FAIL", 3), ("APDATIFIER_BOOTSTRAP_INSTALL_FAIL", 7)):
            with self.subTest(variable=variable):
                self.env[variable] = "true"
                result = self.invoke()
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual(self.commands(["-m", "coverage", "run"]), [])
                self.assertEqual(self.commands(["--test"]), [])
                self.env.pop(variable)

    def test_incomplete_existing_environment_is_preserved(self):
        target = self.root / ".venv"
        target.mkdir()
        note = target / "keep-me"
        note.write_text("existing data")
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(note.read_text(), "existing data")
        self.assertEqual(self.commands(["-m", "venv"]), [])

    def test_missing_pip_is_repaired_only_inside_the_environment(self):
        self.assertEqual(self.invoke().returncode, 0)
        (self.root / ".venv/pip-ready").unlink()
        self.assertEqual(self.invoke().returncode, 0)
        repair = self.commands(["-m", "ensurepip"])
        self.assertEqual(len(repair), 1)
        self.assertEqual(repair[0]["program"], str(self.root / ".venv/bin/python"))

    def test_unsupported_node_stops_before_environment_creation(self):
        self.env["APDATIFIER_BOOTSTRAP_OLD_NODE"] = "true"
        self.assertEqual(self.invoke().returncode, 2)
        self.assertEqual(self.commands(["-m", "venv"]), [])

    def test_failed_tests_still_generate_reports_and_run_javascript(self):
        self.env["APDATIFIER_BOOTSTRAP_TEST_EXIT"] = "1"
        self.assertEqual(self.invoke().returncode, 1)
        for report in ("html", "xml", "json", "report"):
            self.assertEqual(len(self.commands(["-m", "coverage", report])), 1)
        self.assertEqual(len(self.commands(["--test"])), 1)


if __name__ == "__main__":
    unittest.main()
