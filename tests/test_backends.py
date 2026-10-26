"""Run with: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v."""

import contextlib
import ast
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "backends", Path(__file__).resolve().parents[1] / "package/contents/tools/backends.py")
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)
INSTALLED = {
    "example:amd64": b.package_record("apt", "example:amd64", "example", "1.0-1", architecture="amd64"),
    "other:amd64": b.package_record("apt", "other:amd64", "other", "1", architecture="amd64"),
}
UPGRADE = "Inst example [1.0-1] (2.0-1 Ubuntu:stable [amd64])\nConf example (2.0-1 Ubuntu:stable [amd64])\n"
REMOVAL = "Remv other [1]\n" + UPGRADE


def completed(argv=(), stdout="", code=0):
    return subprocess.CompletedProcess(argv, code, stdout, "")


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="apdatifier-test-")
        self.root = Path(self.tmp.name)
        self.paths = b.Paths(self.root / "config", self.root / "cache")
        self.paths.config.mkdir()
        (self.paths.config / "config.conf").write_text('sudoBin="sudo"\naptUpgradeMode="safe"\n')
        self.runner = mock.Mock(spec=b.Runner)
        self.runner.run.return_value = completed()

    def tearDown(self):
        self.tmp.cleanup()

    def apt(self, mode="safe"):
        return b.AptBackend(self.paths, self.runner, mode, {"ID": "debian"})


class SelectorTests(TemporaryCase):
    def test_configuration_escapes_are_read_without_execution(self):
        (self.paths.config / "config.conf").write_text(
            'sudoBin="sudo"\npreExec="echo \\"hello\\" \\$PATH \\$(printf injected)"\n')
        self.assertEqual(self.paths.settings()["preExec"], 'echo "hello" $PATH $(printf injected)')

    def test_runtime_helper_imports_only_standard_library_modules(self):
        tree = ast.parse(Path(b.__file__).read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports <= sys.stdlib_module_names)
    def test_fields_form_one_native_selector(self):
        self.assertEqual(b.apt_selector("example", "amd64", "1:2.0~rc1-3"),
                         "example:amd64=1:2.0~rc1-3")

    def test_invalid_fields_cannot_add_options_patterns_or_arguments(self):
        for args in [
            ("--remove", "amd64", "1"), ("example*", "amd64", "1"),
            ("example", "amd64 other", "1"), ("example", "amd64", "1 --allow-unauthenticated"),
            ("example", "amd64", "1\nPin-Priority: 1001"),
            ("example", "amd64", "$(printf injected)"), ("example;id", "amd64", "1"),
        ]:
            with self.subTest(args=args), self.assertRaises(b.BackendError):
                b.apt_selector(*args)

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    @mock.patch.object(b.AptBackend, "metadata", return_value=[
        {"Package": "example", "Architecture": "amd64", "Version": "1:2.0~rc1-3"}])
    def test_selector_is_one_argument_at_subprocess_boundary(self, metadata, installed, confirm):
        self.runner.run.side_effect = lambda argv, **kw: completed(argv, UPGRADE if "--simulate" in argv else "")
        with contextlib.redirect_stdout(io.StringIO()):
            b.apt_foreground(self.paths, "install-version", ["example:amd64", "1:2.0~rc1-3"], self.runner)
        calls = [call.args[0] for call in self.runner.run.call_args_list if "install" in call.args[0]]
        self.assertEqual(len(calls), 2)
        for argv in calls:
            self.assertIn("example:amd64=1:2.0~rc1-3", argv)
            self.assertNotIn("amd64", argv)
            self.assertNotIn("1:2.0~rc1-3", argv)
            self.assertIn("--no-remove", argv)


class AptPlanTests(TemporaryCase):
    def test_translated_control_description_is_not_lost(self):
        records = b.control_records(
            "Package: example\nVersion: 1\nDescription-en: Useful package\n More details.\nDescription-md5: 123\n")
        self.assertEqual(b.package_description(records[0]), "Useful package\nMore details.")

    def test_plan_distinguishes_new_dependencies_and_removals(self):
        plan = b.parse_simulation(REMOVAL + "Inst new-dependency (1:2.0~rc1-3 Debian:stable [all])\n", INSTALLED)
        self.assertEqual([entry["action"] for entry in plan], ["Remv", "Inst", "Inst"])
        self.assertEqual(plan[-1]["nativeId"], "new-dependency:all")
        self.assertEqual(plan[-1]["installedVersion"], "")

    def test_multiarch_versions_and_architecture_identity(self):
        installed = dict(INSTALLED)
        installed["example:i386"] = b.package_record("apt", "example:i386", "example", "1", architecture="i386")
        plan = b.parse_simulation("Inst example:i386 [1] (1:2.0~rc1-3 Debian:stable [i386])\n", installed)
        self.assertEqual(plan[0]["nativeId"], "example:i386")
        self.assertEqual(plan[0]["candidateVersion"], "1:2.0~rc1-3")

    def test_multiple_dependency_annotations_keep_native_versions_and_architectures(self):
        installed = {}
        for name, architectures in (("libsystemd0", ("amd64", "i386")),
                                     ("libsystemd-shared", ("amd64",)), ("libudev1", ("amd64", "i386"))):
            for architecture in architectures:
                identifier = name + ":" + architecture
                installed[identifier] = b.package_record("apt", identifier, name, "259.5-0ubuntu3.4",
                                                          architecture=architecture)
        text = (
            "Inst libsystemd0:i386 [259.5-0ubuntu3.4] (259.9-0ubuntu0.1 Ubuntu:26.04/resolute-updates [i386])"
            " [libsystemd0:amd64 on libsystemd0:i386] [libsystemd0:i386 on libsystemd0:amd64] [libsystemd0:amd64 ]\n"
            "Inst libsystemd-shared [259.5-0ubuntu3.4] (259.9-0ubuntu0.1 Ubuntu:26.04/resolute-updates [amd64])"
            " [systemd:amd64 on libsystemd-shared:amd64] [udev:amd64 systemd:amd64 ]\n"
            "Inst libudev1 [259.5-0ubuntu3.4] (259.9-0ubuntu0.1 Ubuntu:26.04/resolute-updates [amd64])"
            " [libudev1:amd64 on libudev1:i386] [libudev1:i386 on libudev1:amd64] [libudev1:i386 ]\n"
            "Conf libsystemd0:i386 (259.9-0ubuntu0.1 Ubuntu:26.04/resolute-updates [i386])"
            " [libsystemd0:amd64 ] []\n")
        changes = b.parse_simulation(text, installed)
        self.assertEqual([item["nativeId"] for item in changes],
                         ["libsystemd0:i386", "libsystemd-shared:amd64", "libudev1:amd64"])
        self.assertTrue(all(item["installedVersion"] == "259.5-0ubuntu3.4" for item in changes))
        self.assertTrue(all(item["candidateVersion"] == "259.9-0ubuntu0.1" for item in changes))
        self.assertTrue(all(" on " not in item["repository"] for item in changes))

    def test_annotated_removals_still_obey_safe_mode_and_operation_exclusions(self):
        text = "Remv other [1] [example:amd64 on other:amd64] [example:amd64 ]\n"
        self.runner.run.return_value = completed(stdout=text)
        for mode, excluded in (("safe", set()), ("full", {"other:amd64"})):
            with self.subTest(mode=mode), self.assertRaises(b.BackendError) as error:
                self.apt(mode).plan(INSTALLED, excluded=excluded)
            self.assertEqual(error.exception.category, "blocked")
        _, changes = self.apt("full").plan(INSTALLED)
        self.assertEqual([(item["action"], item["nativeId"]) for item in changes], [("Remv", "other:amd64")])

    def test_malformed_annotations_fail_and_diagnostics_redact_credentials(self):
        for suffix in (" [example:amd64 ] unexpected", " [example:amd64", " [nested [annotation]]"):
            with self.subTest(suffix=suffix), self.assertRaises(b.BackendError) as error:
                b.parse_simulation(UPGRADE.splitlines()[0] + suffix, INSTALLED)
            self.assertEqual(error.exception.category, "invalid-output")
        text = "Inst example (2 https://user:secret@example.invalid/repo [amd64]) unsupported"
        with self.assertRaises(b.BackendError) as error:
            b.parse_simulation(text, INSTALLED)
        self.assertIn("Inst example", str(error.exception))
        self.assertNotIn("secret", str(error.exception))

    def test_ambiguous_and_unknown_records_are_not_silently_ignored(self):
        for text in ("Inst example ???", "Remv unknown [1]", "Inst new-package (not-a-version [amd64])"):
            with self.subTest(text=text), self.assertRaises(b.BackendError):
                b.parse_simulation(text, INSTALLED)

    def test_safe_flags_for_bulk_and_single_operations(self):
        for action in ("upgrade", "upgrade-package", "install-version"):
            with self.subTest(action=action):
                self.assertIn("--no-remove", self.apt().command(action, ["example:amd64"]))
        self.assertNotIn("--no-remove", self.apt("full").command("upgrade-package", ["example:amd64"]))

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b.AptBackend, "marks", return_value=set())
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_safe_single_upgrade_stops_if_plan_removes_another_package(self, installed, marks, confirm):
        responses = iter([completed(), completed(stdout=UPGRADE), completed(stdout=REMOVAL)])
        self.runner.run.side_effect = lambda *args, **kw: next(responses)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(b.BackendError) as error:
            b.apt_foreground(self.paths, "upgrade-package", ["example:amd64"], self.runner)
        self.assertEqual(error.exception.category, "blocked")
        confirm.assert_not_called()
        commands = [call.args[0] for call in self.runner.run.call_args_list]
        self.assertTrue(all("--no-remove" in argv for argv in commands if "--simulate" in argv))
        self.assertFalse(any("install" in argv and "--simulate" not in argv for argv in commands))

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b.AptBackend, "marks", return_value=set())
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_safe_guard_remains_on_execution_after_a_successful_preview(self, installed, marks, confirm):
        self.runner.run.side_effect = lambda argv, **kw: completed(argv, UPGRADE if "--simulate" in argv else "")
        with contextlib.redirect_stdout(io.StringIO()):
            b.apt_foreground(self.paths, "upgrade-package", ["example:amd64"], self.runner)
        install = [call.args[0] for call in self.runner.run.call_args_list
                   if "install" in call.args[0] and "--simulate" not in call.args[0]]
        self.assertEqual(len(install), 1)
        self.assertIn("--no-remove", install[0])
        self.assertIn("--only-upgrade", install[0])

    def test_neon_auto_requires_full(self):
        self.assertEqual(b.AptBackend(self.paths, mode="auto", release={"ID": "neon"}).mode, "full")
        with self.assertRaises(b.BackendError):
            b.AptBackend(self.paths, mode="safe", release={"ID": "neon"})

    @mock.patch.object(b, "confirm", side_effect=b.BackendError("Not approved", "canceled", 130))
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_a_native_policy_downgrade_needs_explicit_consent(self, installed, confirm):
        preview = "Inst example [1.0-1] (0.9-1 Ubuntu:stable [amd64])\n"
        self.runner.run.side_effect = lambda argv, **kw: completed(argv, preview if "--simulate" in argv else "")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(b.BackendError):
            b.apt_foreground(self.paths, "upgrade", [], self.runner)
        confirm.assert_called_once_with("The plan installs earlier package versions. Allow these version decreases?")
        commands = [call.args[0] for call in self.runner.run.call_args_list]
        self.assertIn(["/usr/bin/dpkg", "--compare-versions", "0.9-1", "lt", "1.0-1"], commands)
        self.assertFalse(any("upgrade" in argv and "--simulate" not in argv for argv in commands))

    def test_excluded_package_change_blocks_execution(self):
        with self.assertRaises(b.BackendError):
            b.assert_plan(b.parse_simulation(UPGRADE, INSTALLED), {"example:amd64"}, False)

    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    @mock.patch.object(b.AptBackend, "metadata", return_value=[
        {"Package": "other-name", "Architecture": "amd64", "Version": "1"}])
    def test_nonexistent_name_cannot_fall_back_to_an_apt_pattern(self, metadata, installed):
        with self.assertRaises(b.BackendError):
            b.apt_foreground(self.paths, "install", ["not.a.real.name:amd64"], self.runner)
        self.assertFalse(any("install" in call.args[0] for call in self.runner.run.call_args_list))

    def test_constraints_keep_system_preferences_and_do_not_change_holds(self):
        original = self.root / "preferences"
        original.write_text("Package: existing\nPin: version *\nPin-Priority: 42\n")
        parts = self.root / "preferences.d"
        parts.mkdir()
        (parts / "custom.pref").write_text("Package: another\nPin: version *\nPin-Priority: 90\n")
        self.runner.run.return_value = completed(stdout=f"PREF='{original}'\nPARTS='{parts}'\n")
        with self.apt().constraints(INSTALLED, ["example"]) as (options, excluded):
            pin_file = Path(options[1].split("=", 1)[1])
            text = pin_file.read_text()
            self.assertTrue(text.startswith("Package: example:amd64\nPin: version 1.0-1\n"))
            self.assertIn(original.read_text().strip(), text)
            self.assertIn("Package: another", text)
            self.assertEqual(excluded, {"example:amd64"})
        self.assertFalse(pin_file.exists())
        self.assertFalse(any("hold" in str(call.args[0]) for call in self.runner.run.call_args_list))


class RefreshTests(TemporaryCase):
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_private_transient_refresh_failure_stops_before_plan(self, installed):
        self.runner.run.side_effect = b.BackendError("Source A succeeded; source B: temporary download failure", code=100)
        with mock.patch.object(b.AptBackend, "audit_indexes"), mock.patch.object(b.AptBackend, "audit_sources"), self.assertRaises(b.BackendError):
            self.apt().check()
        argv = self.runner.run.call_args.args[0]
        self.assertIn("--error-on=any", argv)
        self.assertEqual(argv[-1], "update")
        self.assertEqual(self.runner.run.call_count, 1)

    def test_foreground_partial_refresh_stops_install_or_upgrade(self):
        for action, values in (("upgrade", []), ("install", ["example:amd64"])):
            runner = mock.Mock(spec=b.Runner)
            runner.run.side_effect = b.BackendError("Source A succeeded; source B: transient error", code=100)
            with self.subTest(action=action), self.assertRaises(b.BackendError):
                b.apt_foreground(self.paths, action, values, runner)
            self.assertEqual(runner.run.call_count, 1)
            self.assertEqual(runner.run.call_args.args[0][-2:], ["--error-on=any", "update"])

    @mock.patch.object(b.AptBackend, "check", side_effect=b.BackendError("Transient error", code=100))
    def test_failure_keeps_last_complete_result_and_timestamp(self, check):
        previous = dict(schemaVersion=1, backend="apt", items=[INSTALLED["example:amd64"]], synchronizedAt=123)
        target = self.paths.cache / "apt-result.json"
        b.atomic_json(target, previous)
        result = b.check_backend("apt", self.paths)
        self.assertFalse(result["metadataCurrent"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["synchronizedAt"], 123)
        self.assertEqual(result["items"], previous["items"])
        self.assertEqual(b.read_json(target), previous)

    @mock.patch.object(b.AptBackend, "check", return_value=[])
    def test_invalid_previous_metadata_does_not_block_a_new_complete_check(self, check):
        b.private_dir(self.paths.cache)
        for text in ('{invalid JSON', '["invalid"]', '{"schemaVersion": 999}', '{"items": "invalid"}'):
            with self.subTest(previous=text):
                (self.paths.cache / "apt-result.json").write_text(text)
                result = b.check_backend("apt", self.paths)
                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["metadataCurrent"])

    def test_private_configuration_does_not_redirect_system_dpkg_state(self):
        with mock.patch.object(b.AptBackend, "audit_indexes"), self.apt().indexes() as options:
            config = Path(options[1]).read_text()
            self.assertIn(str(self.paths.cache / "apt/lists"), config)
            self.assertIn("#clear APT::Update::Post-Invoke;", config)
            self.assertNotIn('Dir::State::status', config)
            self.assertNotIn('RootDir', config)
            self.assertNotIn("AllowUnauthenticated", config)

    def test_custom_system_log_path_cannot_escape_the_private_cache(self):
        root = self.paths.cache / "apt"
        self.runner.run.return_value = completed(stdout="\n".join([
            "STATUS='/var/lib/dpkg/status'", f"LISTS='{root / 'lists'}'",
            f"ARCHIVES='{root / 'archives'}'", f"LOG='{root / 'log'}'",
            "HISTORY='/var/log/apt/history.log'", f"TERMINAL='{root / 'log/term.log'}'",
            f"PLANNER='{root / 'log/eipp.log.xz'}'", "PKG=''", "SRC=''",
        ]))
        with self.assertRaises(b.BackendError) as error:
            self.apt().audit_indexes([], root)
        self.assertEqual(error.exception.category, "permissions")


class AptSourceTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.sources = self.root / "custom.sources"
        self.parts = self.root / "sourceparts"
        self.trusted = self.root / "trustedparts"
        self.parts.mkdir()
        self.trusted.mkdir()
        self.sources.write_text("Types: deb\nURIs: https://example.invalid\nSuites: stable\nComponents: main\n")
        self.locations = dict(SOURCES=str(self.sources), SOURCEPARTS=str(self.parts), PARTS_ENABLED=str(self.parts),
                              TRUSTED=str(self.root / "optional-keyring.gpg"), TRUSTEDPARTS=str(self.trusted),
                              TRUSTEDPARTS_ENABLED=str(self.trusted))

    def audit(self):
        self.runner.run.return_value = completed(stdout="\n".join(
            key + "=" + b.shlex.quote(value) for key, value in self.locations.items()))
        self.apt().audit_sources([])

    def test_unreadable_source_directory_is_a_capability_error(self):
        with mock.patch.object(Path, "iterdir", side_effect=PermissionError("Directory cannot be read")), \
                self.assertRaises(b.BackendError) as error:
            self.audit()
        self.assertEqual(error.exception.category, "capability-error")

    def test_signed_by_key_permissions_are_checked_in_both_source_formats(self):
        key = self.root / "source-key.gpg"
        key.write_bytes(b"\x80\xffbinary-key")
        real_open = os.open
        def open_without_key(path, *args, **kwargs):
            if Path(path) == key:
                raise PermissionError("The desktop user cannot read this key")
            return real_open(path, *args, **kwargs)
        for suffix, source in [
            (".list", f"deb [signed-by={key}] https://example.invalid stable main\n"),
            (".sources", f"Types: deb\nURIs: https://example.invalid\nSuites: stable\nSigned-By: {key}\n"),
        ]:
            with self.subTest(suffix=suffix):
                self.sources = self.root / ("custom" + suffix)
                self.sources.write_text(source)
                self.locations["SOURCES"] = str(self.sources)
                with mock.patch.object(b.os, "open", side_effect=open_without_key), self.assertRaises(b.BackendError) as error:
                    self.audit()
                self.assertEqual(error.exception.category, "capability-error")
                self.assertNotIn("binary-key", str(error.exception))

    def test_binary_keys_are_valid_readability_inputs(self):
        key = self.root / "source-key.gpg"
        key.write_bytes(b"\x80\xffbinary-key")
        original = self.sources.read_text()
        self.sources.write_text(original + f"Signed-By: {key}\n")
        self.audit()
        self.sources.write_text(original)
        (self.trusted / "default.gpg").write_bytes(key.read_bytes())
        self.audit()

    def test_embedded_and_disabled_keys_need_no_external_key_file(self):
        self.sources.write_text(
            "# Comment before a Deb822 record\nTypes: deb\nURIs: https://example.invalid\nSuites: stable\n"
            "Signed-By:\n -----BEGIN PGP PUBLIC KEY BLOCK-----\n .\n embedded-key\n -----END PGP PUBLIC KEY BLOCK-----\n\n"
            "Types: deb\nURIs: https://disabled.invalid\nSuites: stable\nEnabled: no\nSigned-By: /missing/disabled-key.gpg\n")
        self.audit()

    def test_optional_missing_sources_disabled_parts_and_backups_remain_valid(self):
        (self.parts / "backup.list.save").write_text("Invalid source backup\n")
        self.audit()
        self.sources.unlink()
        self.locations.update(PARTS_ENABLED="", SOURCEPARTS="/")
        with mock.patch.object(Path, "iterdir", side_effect=AssertionError("Disabled directory must not be scanned")):
            self.audit()
            self.locations.update(PARTS_ENABLED="/dev/null", SOURCEPARTS="/dev/null/")
            self.audit()

    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_source_access_lost_during_refresh_keeps_the_snapshot(self, installed):
        previous = dict(schemaVersion=1, backend="apt", items=[INSTALLED["example:amd64"]], synchronizedAt=123)
        target = self.paths.cache / "apt-result.json"
        b.atomic_json(target, previous)
        with mock.patch.object(b.AptBackend, "indexes", return_value=contextlib.nullcontext([])), \
                mock.patch.object(b.AptBackend, "audit_sources", side_effect=[None, b.BackendError("Access lost", "capability-error")]):
            result = b.check_backend("apt", self.paths, self.runner)
        self.assertFalse(result["metadataCurrent"])
        self.assertEqual(result["items"], previous["items"])
        self.assertEqual(result["synchronizedAt"], 123)
        self.assertEqual(b.read_json(target), previous)
        self.assertEqual(self.runner.run.call_args.args[0][-2:], ["--error-on=any", "update"])
        self.assertEqual(self.runner.run.call_count, 1)


class PersistenceAndLifecycleTests(TemporaryCase):
    def test_failed_atomic_replace_keeps_the_previous_file(self):
        path = self.paths.cache / "updates.json"
        b.atomic_json(path, [{"old": True}])
        with mock.patch.object(b.os, "replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            b.atomic_json(path, [{"new": True}])
        self.assertEqual(b.read_json(path), [{"old": True}])

    def test_symlink_write_target_is_rejected(self):
        b.private_dir(self.paths.cache)
        target = self.root / "unrelated"
        target.write_text("unchanged")
        (self.paths.cache / "updates.json").symlink_to(target)
        with self.assertRaises(b.BackendError):
            b.atomic_json(self.paths.cache / "updates.json", [])
        self.assertEqual(target.read_text(), "unchanged")

    def test_chunked_json_with_quotes_unicode_and_large_data(self):
        value = [{"name": "' $() \\ \n", "description": "x" * 100000}]
        text = json.dumps(value)
        chunks = [text[index:index + 16000] for index in range(0, len(text), 16000)]
        for index, chunk in enumerate(chunks):
            b.cache_chunk(self.paths, "example-token", index, len(chunks), chunk)
        self.assertEqual(b.read_json(self.paths.cache / "updates.json"), value)
        self.assertFalse((self.paths.cache / "updates-example-token.part").exists())

    def test_partial_and_canceled_transactions_are_not_success(self):
        for failure, expected in ((100, "partial"), (130, "canceled")):
            with self.subTest(failure=failure):
                b.lifecycle(self.paths, "start", "example-token", pid=os.getpid())
                b.lifecycle(self.paths, "stage", "example-token", "apt", 0)
                b.lifecycle(self.paths, "stage", "example-token", "snap", failure)
                result = b.lifecycle(self.paths, "finish", "example-token")
                self.assertEqual(result["status"], expected)

    def test_unexpected_terminal_exit_is_unknown(self):
        b.lifecycle(self.paths, "start", "example-token", pid=99999999)
        self.assertEqual(b.lifecycle(self.paths, "state")["status"], "unknown")

    def test_a_reused_pid_is_not_a_running_transaction(self):
        b.lifecycle(self.paths, "start", "example-token", pid=os.getpid())
        with mock.patch.object(b, "process_identity", return_value="different-start-time"):
            self.assertEqual(b.lifecycle(self.paths, "state")["status"], "unknown")

    def test_nonzero_exit_without_stderr_is_a_failure(self):
        with self.assertRaises(b.BackendError) as error:
            b.Runner().run(["/bin/sh", "-c", "exit 17"])
        self.assertEqual(error.exception.code, 17)

    def test_checker_cancellation_stops_its_child(self):
        b.atomic_json(self.paths.cache / "cancel-example", {})
        with self.assertRaises(b.BackendError) as error:
            b.Runner(self.paths, "example").run(["/usr/bin/python3", "-I", "-B", "-c", "import time; time.sleep(30)"])
        self.assertEqual(error.exception.category, "canceled")

    def test_management_selection_rejects_indexes_outside_result_set(self):
        with mock.patch("builtins.input", side_effect=["0 999", "1 2"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(b.choose(["one", "two"]), ["one", "two"])


class SnapTests(TemporaryCase):
    def snap(self, candidates=None, installed=None, inhibited=None):
        backend = b.SnapBackend(self.paths, self.runner)
        responses = {"/v2/snaps": installed, "/v2/find?select=refresh": candidates,
                     "/v2/snaps?select=refresh-inhibited": inhibited or []}
        backend.api = mock.Mock(side_effect=lambda path: responses[path])
        return backend

    def test_equal_version_text_with_new_revision_is_an_update(self):
        installed = [dict(name="example", version="1", revision="10", **{"tracking-channel": "latest/stable"})]
        candidate = [dict(name="example", version="1", revision="9")]
        result = self.snap(candidate, installed).check()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["candidateRevision"], "9")
        self.assertEqual(result[0]["installedRevision"], "10")
        self.assertEqual(result[0]["uid"], "snap:example")

    def test_individual_hold_is_visible(self):
        installed = [dict(name="example", version="1", revision="10", hold="forever")]
        candidate = [dict(name="example", version="2", revision="11")]
        self.assertEqual(self.snap(candidate, installed).check()[0]["state"], "held")

    def test_running_application_restriction_is_a_blocked_update(self):
        installed = [dict(name="example", version="1", revision="10")]
        candidate = [dict(name="example", version="2", revision="11")]
        result = self.snap(candidate, installed, [dict(name="example")]).check()
        self.assertEqual(result[0]["state"], "blocked")

    def test_unknown_candidate_instance_does_not_match_by_display_name(self):
        with self.assertRaises(b.BackendError):
            self.snap([dict(name="example", revision="11")],
                      [dict(name="example_other", revision="10")]).check()

    def test_daemon_error_is_not_an_empty_list(self):
        backend = b.SnapBackend(self.paths)
        backend.api = mock.Mock(return_value={"message": "error"})
        with self.assertRaises(b.BackendError):
            backend.installed()

    @mock.patch.object(b, "confirm", side_effect=b.BackendError("No", "canceled", 130))
    @mock.patch.object(b, "snap_global_hold", return_value=True)
    @mock.patch.object(b.SnapBackend, "installed", return_value=[])
    @mock.patch.object(b.SnapBackend, "check", return_value=[
        b.package_record("snap", "example", "example", "1", "2")])
    def test_global_hold_override_defaults_to_no(self, check, installed, global_hold, confirm):
        with self.assertRaises(b.BackendError):
            b.snap_foreground(self.paths, "refresh", [], self.runner)
        self.runner.run.assert_not_called()

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b, "snap_global_hold")
    @mock.patch.object(b.SnapBackend, "installed", return_value=[])
    @mock.patch.object(b.SnapBackend, "check", return_value=[])
    def test_no_snap_updates_is_a_successful_noop(self, check, installed, global_hold, confirm):
        with contextlib.redirect_stdout(io.StringIO()):
            b.snap_foreground(self.paths, "refresh", [], self.runner)
        self.runner.run.assert_not_called()
        global_hold.assert_not_called()
        confirm.assert_not_called()

    @mock.patch.object(b, "confirm", side_effect=b.BackendError("No", "canceled", 130))
    @mock.patch.object(b, "snap_global_hold", return_value=False)
    @mock.patch.object(b.SnapBackend, "installed", return_value=[dict(name="example", hold="forever")])
    def test_targeted_hold_override_needs_separate_consent(self, installed, global_hold, confirm):
        with self.assertRaises(b.BackendError) as error:
            b.snap_foreground(self.paths, "refresh", ["example"], self.runner)
        self.assertEqual(error.exception.category, "canceled")
        self.runner.run.assert_not_called()

    @mock.patch.object(b, "confirm", side_effect=b.BackendError("No", "canceled", 130))
    @mock.patch.object(b.SnapBackend, "api", return_value=[dict(name="example", confinement="classic")])
    def test_classic_installation_cannot_proceed_without_consent(self, api, confirm):
        with self.assertRaises(b.BackendError):
            b.snap_foreground(self.paths, "install", ["example"], self.runner)
        self.runner.run.assert_not_called()

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b.SnapBackend, "api", return_value=dict(ready=True, status="Done"))
    def test_snapshot_removal_flag_requires_the_separate_purge_action(self, api, confirm):
        for action in ("remove", "purge"):
            self.runner.run.reset_mock()
            self.runner.run.side_effect = [completed(stdout="42\n"), completed()]
            with self.subTest(action=action), contextlib.redirect_stdout(io.StringIO()):
                b.snap_foreground(self.paths, action, ["example"], self.runner)
            request = self.runner.run.call_args_list[0].args[0]
            self.assertEqual("--purge" in request, action == "purge")

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b, "snap_global_hold", return_value=False)
    @mock.patch.object(b.SnapBackend, "installed", return_value=[dict(name="allowed"), dict(name="excluded")])
    @mock.patch.object(b.SnapBackend, "api", return_value={"ready": True, "status": "Done"})
    @mock.patch.object(b.SnapBackend, "check", return_value=[
        b.package_record("snap", "allowed", "allowed", "1", "2"),
        b.package_record("snap", "excluded", "excluded", "1", "2")])
    def test_snap_exclusions_are_local_and_do_not_create_holds(self, check, api, installed, global_hold, confirm):
        b.atomic_json(self.paths.config / "rules.json", [
            dict(backend="snap", type="name", value="excluded", ignore=True)])
        self.runner.run.side_effect = [completed(stdout="42\n"), completed()]
        with contextlib.redirect_stdout(io.StringIO()):
            b.snap_foreground(self.paths, "refresh", [], self.runner)
        calls = [call.args[0] for call in self.runner.run.call_args_list]
        self.assertIn("allowed", calls[0])
        self.assertNotIn("excluded", calls[0])
        self.assertFalse(any("hold" in str(argv) for argv in calls))

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b, "snap_global_hold", return_value=False)
    @mock.patch.object(b.SnapBackend, "installed", return_value=[dict(name="example")])
    @mock.patch.object(b.SnapBackend, "api", return_value={"ready": True, "status": "Done"})
    def test_snap_waits_for_change_completion(self, api, installed, global_hold, confirm):
        self.runner.run.side_effect = [completed(stdout="42\n"), completed()]
        with contextlib.redirect_stdout(io.StringIO()):
            b.snap_foreground(self.paths, "refresh", ["example"], self.runner)
        calls = [call.args[0] for call in self.runner.run.call_args_list]
        self.assertIn("--no-wait", calls[0])
        self.assertEqual(calls[1][-2:], ["watch", "42"])

    @mock.patch.object(b.SnapBackend, "installed", return_value=[dict(name="example", revision="10", status="active")])
    def test_cache_operation_cannot_remove_active_revision(self, installed):
        with self.assertRaises(b.BackendError):
            b.snap_foreground(self.paths, "remove-revision", ["example", "10"], self.runner)
        self.runner.run.assert_not_called()

    def test_expired_hold_is_not_active(self):
        self.assertFalse(b.held("2000-01-01T00:00:00Z"))
        self.assertTrue(b.held("9999-01-01T00:00:00Z"))
        with self.assertRaises(b.BackendError):
            b.held(True)

    def test_unix_socket_http_envelopes_and_no_interactive_authorization(self):
        observations = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observations.append((self.path, self.headers.get("X-Allow-Interaction")))
                code = 401 if self.path == "/denied" else 200
                body = dict(type="error" if code == 401 else "sync", **{"status-code": code},
                            result={"message": "authorization required"} if code == 401 else [])
                self.send_response(code)
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def log_message(self, *args):
                pass

        path = str(self.root / "snapd.socket")
        try:
            server = socketserver.UnixStreamServer(path, Handler)
        except PermissionError:
            self.skipTest("The sandbox prohibits Unix sockets.")
        with server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                backend = b.SnapBackend(self.paths, socket_path=path)
                self.assertEqual(backend.installed(), [])
                with self.assertRaises(b.BackendError) as error:
                    backend.api("/denied")
                self.assertEqual(error.exception.category, "auth-required")
                self.assertTrue(all(value == "false" for _, value in observations))
            finally:
                server.shutdown()
                thread.join()


@unittest.skipUnless(shutil.which("apt-get"), "APT is not installed.")
class NativeAptTests(TemporaryCase):
    """Real APT, local fixture indexes, no network, sudo, dpkg changes, or installation."""

    def setUp(self):
        super().setUp()
        self.repo = self.root / "repository"
        packages = self.repo / "dists/stable/main/binary-amd64"
        packages.mkdir(parents=True)
        (packages / "Packages").write_text(
            "Package: example\nVersion: 2.0-1\nArchitecture: amd64\n"
            "Maintainer: Test <test@example.invalid>\nConflicts: other\n"
            "Filename: example.deb\nSize: 1\nMD5sum: 00000000000000000000000000000000\nDescription: New example\n\n"
            "Package: other\nVersion: 1\nArchitecture: amd64\n"
            "Maintainer: Test <test@example.invalid>\nFilename: other.deb\nSize: 1\n"
            "MD5sum: 00000000000000000000000000000000\nDescription: Other package\n\n")
        status = self.root / "status"
        status.write_text(
            "Package: example\nStatus: install ok installed\nPriority: optional\n"
            "Architecture: amd64\nVersion: 1.0-1\nMaintainer: Test <test@example.invalid>\nDescription: Old example\n\n"
            "Package: other\nStatus: install ok installed\nPriority: optional\n"
            "Architecture: amd64\nVersion: 1\nMaintainer: Test <test@example.invalid>\nDescription: Other package\n\n")
        sources = self.root / "sources.list"
        # Trust applies only to this local test repository, never to product code.
        sources.write_text(f"deb [trusted=yes] file:{self.repo} stable main\n")
        for directory in ("lists/partial", "archives/partial", "empty"):
            (self.root / directory).mkdir(parents=True)
        self.config = self.root / "apt.conf"
        self.config.write_text("\n".join([
            f'Dir::Etc::sourcelist "{sources}";',
            f'Dir::Etc::sourceparts "{self.root / "empty"}";',
            f'Dir::State::status "{status}";',
            f'Dir::State::lists "{self.root / "lists"}";',
            f'Dir::State::extended_states "{self.root / "extended_states"}";',
            f'Dir::Cache::archives "{self.root / "archives"}";',
            'Dir::Cache::pkgcache "";', 'Dir::Cache::srcpkgcache "";',
            'APT::Architecture "amd64";', '#clear APT::Architectures;',
            'APT::Architectures { "amd64"; };',
            '#clear APT::Update::Pre-Invoke;', '#clear APT::Update::Post-Invoke;',
            '#clear APT::Update::Post-Invoke-Success;', '#clear APT::Update::Post-Invoke-Stats;',
            'Acquire::Retries "0";',
        ]) + "\n")
        self.native(["--error-on=any", "update"], check=True)

    def native(self, args, check=False):
        return subprocess.run(["apt-get", "-c", str(self.config), *args],
                              text=True, capture_output=True, timeout=30, check=check,
                              env=dict(os.environ, LC_ALL="C", LANGUAGE="C"))

    def test_multiarch_simulation_emits_multiple_annotations_that_remain_parseable(self):
        installed = {}
        for architecture in ("amd64", "i386"):
            metadata = (f"Package: multiarch-library\nArchitecture: {architecture}\nMulti-Arch: same\n"
                        "Maintainer: Test <test@example.invalid>\nDescription: Multiarch test library\n")
            with (self.root / "status").open("a") as stream:
                stream.write(metadata + "Status: install ok installed\nVersion: 1\n\n")
            indexes = self.repo / ("dists/stable/main/binary-" + architecture)
            indexes.mkdir(parents=True, exist_ok=True)
            with (indexes / "Packages").open("a") as stream:
                stream.write(metadata + "Version: 2\nFilename: library.deb\nSize: 1\n"
                             "MD5sum: 00000000000000000000000000000000\n\n")
            identifier = "multiarch-library:" + architecture
            installed[identifier] = b.package_record("apt", identifier, "multiarch-library", "1",
                                                      architecture=architecture)
        with self.config.open("a") as stream:
            stream.write('#clear APT::Architectures;\nAPT::Architectures { "amd64"; "i386"; };\n')
        self.native(["--error-on=any", "update"], check=True)
        result = self.native(["--simulate", "--no-remove", "install", "--only-upgrade", *installed], check=True)
        self.assertRegex(result.stdout, r"\)(?: \[[^\]]*\]){2,}\n")
        changes = b.parse_simulation(result.stdout, installed)
        self.assertEqual({item["nativeId"] for item in changes}, set(installed))
        self.assertTrue(all(item["candidateVersion"] == "2" for item in changes))
        self.assertTrue(all(item["action"] == "Inst" for item in changes))

    @unittest.skipIf(os.geteuid() == 0, "Root can read mode-000 source files.")
    def test_unreadable_sources_cannot_replace_the_last_complete_result(self):
        for source in (self.root / "sources.list", self.root / "empty/hidden.list", self.root / "empty/hidden.sources"):
            with self.subTest(source=source.name):
                if not source.exists():
                    source.write_text("# The file must be readable even when all entries are disabled.\n")
                previous = dict(schemaVersion=1, backend="apt", items=[INSTALLED["example:amd64"]], synchronizedAt=123)
                target = self.paths.cache / "apt-result.json"
                b.atomic_json(target, previous)
                source.chmod(0)
                try:
                    native_result = self.native(["--error-on=any", "update"])
                    self.assertEqual(native_result.returncode, 0, native_result.stderr)
                    with mock.patch.object(b.AptBackend, "indexes", return_value=contextlib.nullcontext(["-c", str(self.config)])), \
                            mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED):
                        result = b.check_backend("apt", self.paths)
                    self.assertEqual(result["status"], "partial")
                    self.assertFalse(result["metadataCurrent"])
                    self.assertEqual(result["synchronizedAt"], 123)
                    self.assertEqual(result["items"], previous["items"])
                    self.assertEqual(result["errors"][0]["category"], "capability-error")
                    self.assertEqual(b.read_json(target), previous)
                finally:
                    source.chmod(0o600)
                    if source.parent.name == "empty":
                        source.unlink()

    def test_only_upgrade_needs_no_remove_to_enforce_safe_mode(self):
        unguarded = self.native(["--simulate", "install", "--only-upgrade", "example:amd64"])
        self.assertEqual(unguarded.returncode, 0, unguarded.stderr)
        self.assertIn("Remv other", unguarded.stdout)
        guarded = self.native(["--simulate", "--no-remove", "install", "--only-upgrade", "example:amd64"])
        self.assertNotEqual(guarded.returncode, 0)
        self.assertIn("remove is disabled", guarded.stderr.lower())
        self.assertIn("Version: 1.0-1", (self.root / "status").read_text())

    def test_operation_pins_prevent_changes_without_persistent_holds(self):
        apt = self.apt(mode="full")
        with apt.constraints(INSTALLED, ["example"]) as (options, excluded):
            result = self.native([*options, "--simulate", "dist-upgrade"])
            self.assertEqual(result.returncode, 0, result.stderr)
            changes = b.parse_simulation(result.stdout, INSTALLED)
            self.assertFalse(any(change["nativeId"] in excluded for change in changes))

    def test_operation_pins_do_not_downgrade_a_concurrently_updated_package(self):
        apt = self.apt(mode="full")
        with apt.constraints(INSTALLED, ["example"]) as (options, excluded):
            status = self.root / "status"
            status.write_text(status.read_text().replace("Version: 1.0-1", "Version: 3.0-1"))
            result = self.native([*options, "--simulate", "dist-upgrade"])
            self.assertEqual(result.returncode, 0, result.stderr)
            changes = b.parse_simulation(result.stdout, INSTALLED)
            self.assertFalse(any(change["nativeId"] in excluded for change in changes))

    def test_transient_partial_refresh_returns_failure_with_error_on_any(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_error(503, "Temporary failure")

            def log_message(self, *args):
                pass

        try:
            server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError:
            self.skipTest("The sandbox prohibits local HTTP sockets.")
        with server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with (self.root / "sources.list").open("a") as stream:
                    stream.write(f"deb http://127.0.0.1:{server.server_port} unstable main\n")
                ordinary = self.native(["update"])
                guarded = self.native(["--error-on=any", "update"])
                self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
                self.assertNotEqual(guarded.returncode, 0)
                self.assertIn("503", guarded.stderr)
                self.assertIn("Version: 1.0-1", (self.root / "status").read_text())
            finally:
                server.shutdown()
                thread.join()


class ShellLifecycleTests(TemporaryCase):
    def native_terminal(self, operation, values=(), *, settings=None, codes=None,
                        translated=False, python_available=True, no_updates=False):
        """Exercise the real shell, replacing only native operations and tools."""
        case = Path(tempfile.mkdtemp(prefix="terminal fixture ", dir=self.root))
        tools = case / "contents/tools"
        scripts = tools / "sh"
        scripts.mkdir(parents=True)
        original = Path(b.__file__).parent / "sh"
        for name in ("upgrade", "utils", "vars", "arguments", "messages"):
            shutil.copyfile(original / name, scripts / name)
        if not python_available:
            script = scripts / "upgrade"
            detection = "[[ -x /usr/bin/python3 ]] && hasPython=true"
            self.assertEqual(script.read_text().count(detection), 1)
            script.write_text(script.read_text().replace(detection, "hasPython=false"))
        helper = tools / "backends.py"
        helper.write_text('''import json, os, sys
args = sys.argv[1:]
with open(os.environ["APDATIFIER_TEST_EVENTS"], "a") as stream:
    stream.write(json.dumps(args) + "\\n")
if args[0] == "lifecycle":
    if args[1] == "start":
        print("FIXTURE lifecycle start", file=sys.stderr, flush=True)
    os.execv("/usr/bin/python3", ["/usr/bin/python3", "-I", "-B",
             os.environ["APDATIFIER_TEST_REAL_HELPER"], *args])
assert args[0] == "foreground", args
print("FIXTURE foreground " + args[1], flush=True)
print("FIXTURE administrator prompt", flush=True)
if os.environ["APDATIFIER_TEST_EMPTY"] == "true":
    print("There are no selected Snap updates.", flush=True)
code = json.loads(os.environ["APDATIFIER_TEST_CODES"]).get(args[1], 0)
if code:
    print("FIXTURE operation failed", file=sys.stderr, flush=True)
raise SystemExit(code)
''')
        flatpak = scripts / "flatpak"
        flatpak.write_text("#!/bin/sh\nprintf '%s\\n' 'FIXTURE flatpak'\n")
        flatpak.chmod(0o700)
        if translated:
            gettext = scripts / "gettext"
            gettext.write_text('''#!/bin/sh
case "$1" in
    'APT Upgrade') printf '%s\\n' 'Translated APT' ;;
    'Snap Upgrade') printf '%s\\n' 'Translated Snap' ;;
    'Upgrade') printf '%s\\n' 'Translated Upgrade' ;;
    *) printf '%s\\n' "$1" ;;
esac
''')
            gettext.chmod(0o700)
        paths = b.Paths(case / "config", case / "cache")
        paths.config.mkdir()
        config = dict.fromkeys(("arch", "aur", "apt", "snap", "flatpak", "widgets", "fwupd", "termFont"), "false")
        config.update(settings or {})
        paths.config.joinpath("config.conf").write_text("".join(
            key + "=" + b.shlex.quote(value) + "\n" for key, value in config.items()))
        events = case / "events.jsonl"
        result = subprocess.run(
            ["bash", str(scripts / "upgrade"), operation, "--transaction", "header-test", *values],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=15, env=dict(
                os.environ, APDATIFIER_CONFIG_DIR=str(paths.config), APDATIFIER_CACHE_DIR=str(paths.cache),
                TERM="dumb", LC_ALL="C", LANGUAGE="C", PATH=str(scripts) + os.pathsep + os.environ["PATH"],
                APDATIFIER_TEST_REAL_HELPER=str(Path(b.__file__).resolve()), APDATIFIER_TEST_EVENTS=str(events),
                APDATIFIER_TEST_CODES=json.dumps(codes or {}), APDATIFIER_TEST_EMPTY=str(no_updates).lower(),
            ),
        )
        result.stdout = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout)
        calls = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        return result, calls, b.read_json(paths.cache / "upgrade-state.json", {})

    def test_native_source_and_package_headers_precede_foreground_output(self):
        cases = [
            ("apt", [], "apt", "upgrade", "APT Upgrade"),
            ("snap", [], "snap", "refresh", "Snap Upgrade"),
            ("apt-pkg", ["example:i386"], "apt", "upgrade-package", "Upgrade: example:i386 (APT)"),
            ("snap-pkg", ["example_test"], "snap", "refresh", "Upgrade: example_test (Snap)"),
        ]
        for operation, values, source, action, title in cases:
            with self.subTest(operation=operation):
                result, calls, state = self.native_terminal(operation, values)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(result.stdout.count(title), 1, result.stdout)
                self.assertIn(":" * 48, result.stdout)
                self.assertLess(result.stdout.index("FIXTURE lifecycle start"), result.stdout.index(title))
                self.assertLess(result.stdout.index(title), result.stdout.index("FIXTURE foreground"))
                self.assertLess(result.stdout.index(title), result.stdout.index("FIXTURE administrator prompt"))
                self.assertEqual([call for call in calls if call[0] == "foreground"], [
                    ["foreground", source, action, *values, "--transaction", "header-test"]])
                self.assertEqual(state["status"], "ok")
                self.assertIn(source + " Exit code: 0", result.stdout)
                self.assertIn("Total execution time:", result.stdout)

    def test_full_native_headers_keep_stage_order_and_the_flatpak_header(self):
        result, calls, state = self.native_terminal("full", settings=dict(apt="true", snap="true", flatpak="true"))
        self.assertEqual(result.returncode, 0, result.stdout)
        previous = -1
        for text in ("FIXTURE lifecycle start", "APT Upgrade", "FIXTURE foreground apt",
                     "Snap Upgrade", "FIXTURE foreground snap", "Flatpak Upgrade", "FIXTURE flatpak"):
            self.assertEqual(result.stdout.count(text), 1, result.stdout)
            position = result.stdout.index(text)
            self.assertGreater(position, previous)
            previous = position
        self.assertEqual([call[1] for call in calls if call[0] == "foreground"], ["apt", "snap"])
        self.assertEqual([stage["backend"] for stage in state["stages"]], ["apt", "snap", "flatpak"])

    def test_native_headers_remain_after_failure_cancellation_or_no_updates(self):
        for source, code, empty, expected in (("apt", 100, False, "error"), ("snap", 1, False, "error"),
                                              ("snap", 130, False, "canceled"), ("snap", 0, True, "ok")):
            with self.subTest(source=source, code=code, empty=empty):
                result, _, state = self.native_terminal(source, codes={source: code}, no_updates=empty)
                self.assertEqual(result.returncode, 130 if code == 130 else 1 if code else 0, result.stdout)
                title = "APT Upgrade" if source == "apt" else "Snap Upgrade"
                self.assertEqual(result.stdout.count(title), 1, result.stdout)
                self.assertLess(result.stdout.index(title), result.stdout.index("FIXTURE foreground"))
                self.assertEqual(state["status"], expected)
                self.assertEqual(state["stages"][0]["code"], code)
                if empty:
                    self.assertIn("There are no selected Snap updates.", result.stdout)

    def test_native_failure_continues_but_cancellation_skips_later_headers(self):
        for code in (100, 130):
            with self.subTest(code=code):
                result, calls, state = self.native_terminal(
                    "full", settings=dict(apt="true", snap="true", flatpak="true"), codes={"apt": code})
                self.assertEqual(result.returncode, 130 if code == 130 else 1, result.stdout)
                self.assertEqual(result.stdout.count("APT Upgrade"), 1)
                if code == 130:
                    self.assertNotIn("Snap Upgrade", result.stdout)
                    self.assertNotIn("Flatpak Upgrade", result.stdout)
                    self.assertEqual([call[1] for call in calls if call[0] == "foreground"], ["apt"])
                    self.assertEqual(state["status"], "canceled")
                else:
                    self.assertEqual(result.stdout.count("Snap Upgrade"), 1)
                    self.assertEqual(result.stdout.count("Flatpak Upgrade"), 1)
                    self.assertEqual(state["status"], "partial")

    def test_native_header_translations_keep_package_arguments_as_data(self):
        sentinel = self.root / "must-not-exist"
        name = f"example_$(touch {sentinel})'literal"
        cases = [("apt", [], "Translated APT"), ("snap", [], "Translated Snap"),
                 ("apt-pkg", ["example:i386"], "Translated Upgrade: example:i386 (APT)"),
                 ("snap-pkg", [name], "Translated Upgrade: " + name + " (Snap)")]
        for operation, values, title in cases:
            with self.subTest(operation=operation):
                result, calls, _ = self.native_terminal(operation, values, translated=True)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(result.stdout.count(title), 1, result.stdout)
                foreground = next(call for call in calls if call[0] == "foreground")
                self.assertEqual(foreground[3:-2], values)
                self.assertFalse(sentinel.exists())

    def test_native_header_precedes_the_missing_python_error(self):
        for source, title in (("apt", "APT Upgrade"), ("snap", "Snap Upgrade")):
            with self.subTest(source=source):
                result, calls, _ = self.native_terminal(source, python_available=False)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stdout.count(title), 1, result.stdout)
                self.assertLess(result.stdout.index(title), result.stdout.index("System Python 3 is unavailable"))
                self.assertIn(source + " Exit code: 127", result.stdout)
                self.assertEqual(calls, [])

    def test_argument_quotes_escapes_empty_values_and_literal_metacharacters(self):
        script = Path(__file__).resolve().parents[1] / "package/contents/tools/sh/arguments"
        examples = [
            '', '--cachedir "/tmp/pacman cache"', "one'two three'four '' \"\"",
            r'--path /tmp/escaped\ space', r'"a\"b" "c\\d" "e\q"',
            "word\\\ncontinued", '"$(touch sentinel)" "$HOME" "`touch sentinel`" ";" "*"',
        ]
        for text in examples:
            with self.subTest(arguments=text):
                result = subprocess.run(["bash", "-c", 'source "$1"; splitArguments "$2" || exit $?; '
                                         'if ((${#parsedArguments[@]})); then printf "%s\\0" "${parsedArguments[@]}"; fi',
                                         "test", str(script), text], capture_output=True, timeout=5, check=True,
                                        cwd=self.root)
                expected = b.shlex.split(text.replace("\\\n", ""))
                self.assertEqual(result.stdout.decode().split("\0")[:-1], expected)
                self.assertFalse((self.root / "sentinel").exists())

    def test_invalid_quoted_arguments_stop_before_a_native_command(self):
        marker = self.root / "unexpected-command"
        binary = self.root / "flatpak"
        binary.write_text('#!/bin/sh\ntouch "$APDATIFIER_TEST_ARGUMENTS"\n')
        binary.chmod(0o700)
        script = Path(__file__).resolve().parents[1] / "package/contents/tools/sh/upgrade"
        for flags in ('--sideload-repo "unterminated', "--sideload-repo 'unterminated", "trailing\\"):
            with self.subTest(flags=flags):
                escaped = flags.replace('\\', '\\\\').replace('"', '\\"')
                (self.paths.config / "config.conf").write_text('termFont="false"\nflatpakFlags="' + escaped + '"\n')
                result = subprocess.run(["bash", str(script), "flatpak", "--transaction", "invalid-arguments"],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15,
                                        env=dict(os.environ, APDATIFIER_CONFIG_DIR=str(self.paths.config),
                                                 APDATIFIER_CACHE_DIR=str(self.paths.cache), TERM="dumb",
                                                 PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                                                 APDATIFIER_TEST_ARGUMENTS=str(marker)))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(marker.exists())
                state = b.read_json(self.paths.cache / "upgrade-state.json")
                self.assertEqual(state["status"], "error")
                self.assertEqual(state["stages"][0]["code"], 2)

    def test_quoted_upgrade_arguments_reach_only_the_substitute_commands(self):
        marker = self.root / "arguments.jsonl"
        binary = self.root / "administrator helper"
        binary.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                          'with open(os.environ["APDATIFIER_TEST_ARGUMENTS"], "a") as stream:\n'
                          '    stream.write(json.dumps(sys.argv[1:]) + "\\n")\n')
        binary.chmod(0o700)
        (self.root / "flatpak").symlink_to(binary)
        script = Path(__file__).resolve().parents[1] / "package/contents/tools/sh/upgrade"
        sentinel = self.root / "must-not-exist"
        def config_value(value):
            return value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        cases = [
            ("system", [], {"sudoBin": f'"{binary}" --label "admin label"',
                             "archFlags": f'--cachedir "/tmp/pacman cache" "$(touch {sentinel})"'},
             [["--label", "admin label", "pacman", "-Syu", "--cachedir", "/tmp/pacman cache", f"$(touch {sentinel})"]]),
            ("system", [], {"aur": "true", "wrapper": f'"{binary}" --label "wrapper label"',
                             "archFlags": "--cachedir '/tmp/aur cache'"},
             [["--label", "wrapper label", "-Syu", "--cachedir", "/tmp/aur cache"]]),
            ("flatpak", [], {"flatpakFlags": '--sideload-repo "/tmp/flatpak cache"', "flatpakRemoveUnused": "true"},
             [["update", "--sideload-repo", "/tmp/flatpak cache"],
              ["uninstall", "--unused", "--sideload-repo", "/tmp/flatpak cache"]]),
            ("flatpak-pkg", ["app/org.example.App/x86_64/stable", "Example", "user"],
             {"flatpakFlags": '--sideload-repo "/tmp/flatpak cache"'},
             [["update", "--sideload-repo", "/tmp/flatpak cache", "--user", "app/org.example.App/x86_64/stable"]]),
        ]
        for index, (operation, values, settings, expected) in enumerate(cases):
            with self.subTest(operation=operation, settings=settings):
                marker.unlink(missing_ok=True)
                config = {"termFont": "false", "mirrors": "false", **settings}
                (self.paths.config / "config.conf").write_text(''.join(
                    key + '="' + config_value(value) + '"\n' for key, value in config.items()))
                result = subprocess.run(["bash", str(script), operation, "--transaction", f"quoted-{index}", *values],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15,
                                        env=dict(os.environ, APDATIFIER_CONFIG_DIR=str(self.paths.config),
                                                 APDATIFIER_CACHE_DIR=str(self.paths.cache), TERM="dumb",
                                                 PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                                                 APDATIFIER_TEST_ARGUMENTS=str(marker)))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([json.loads(line) for line in marker.read_text().splitlines()], expected)
                self.assertFalse(sentinel.exists())

    def test_single_flatpak_update_preserves_its_native_reference_and_scope(self):
        binary = self.root / "flatpak"
        marker = self.root / "flatpak-arguments"
        binary.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$APDATIFIER_TEST_ARGUMENTS\"\n")
        binary.chmod(0o700)
        (self.paths.config / "config.conf").write_text('termFont="false"\n')
        script = Path(__file__).resolve().parents[1] / "package/contents/tools/sh/upgrade"
        reference = "app/org.example.App/x86_64/stable"
        result = subprocess.run(["bash", str(script), "flatpak-pkg", "--transaction", "flatpak-test",
                                 reference, "Example", "user"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=15,
                                env=dict(os.environ, APDATIFIER_CONFIG_DIR=str(self.paths.config),
                                         APDATIFIER_CACHE_DIR=str(self.paths.cache), TERM="dumb",
                                         PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                                         APDATIFIER_TEST_ARGUMENTS=str(marker)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(marker.read_text().splitlines(), ["update", "--user", reference])
        self.assertIn("Upgrade: Example", re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout))

    def test_apt_only_sequence_runs_user_hooks_once_without_native_changes(self):
        marker = self.root / "hooks"
        for name in ("pre", "post"):
            hook = self.root / (name + ".sh")
            hook.write_text("#!/bin/sh\nprintf '%s\\n' " + name + " >> " + str(marker) + "\n")
            hook.chmod(0o700)
        administrator = self.root / "fake-administrator"
        administrator.write_text("#!/bin/sh\nexit 100\n")
        administrator.chmod(0o700)
        (self.paths.config / "config.conf").write_text(
            'arch="false"\naur="false"\napt="true"\nsnap="false"\n'
            'flatpak="false"\nwidgets="false"\nfwupd="false"\ntermFont="false"\n'
            f'sudoBin="{administrator}"\n'
            f'preExec="{self.root / "pre.sh"}"\npostExec="{self.root / "post.sh"}"\n')
        script = Path(__file__).resolve().parents[1] / "package/contents/tools/sh/upgrade"
        result = subprocess.run(["bash", str(script), "full", "--transaction", "hooks-test"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15,
                                env=dict(os.environ, APDATIFIER_CONFIG_DIR=str(self.paths.config),
                                         APDATIFIER_CACHE_DIR=str(self.paths.cache), TERM="dumb"))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(marker.read_text().splitlines(), ["pre", "post"])
        state = b.read_json(self.paths.cache / "upgrade-state.json")
        self.assertEqual([stage["backend"] for stage in state["stages"]], ["pre-script", "apt", "post-script"])
        self.assertEqual(state["status"], "partial")
        self.assertEqual(state["stages"][1]["code"], 100)


if __name__ == "__main__":
    unittest.main()
