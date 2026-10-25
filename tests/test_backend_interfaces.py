"""User-facing backend interfaces, with every native mutation substituted."""

import contextlib
import gzip
import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from test_backends import TemporaryCase, INSTALLED, UPGRADE, b, completed


class ManagementTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.backend = mock.Mock(spec=b.AptBackend)
        self.backend.installed.return_value = INSTALLED
        self.backend.marked.side_effect = b.AptBackend.marked
        self.backend.marks.return_value = {"example"}
        self.backend.metadata.return_value = [{"Package": "example", "Architecture": "amd64", "Description": "Editor"}]
        self.snap = mock.Mock(spec=b.SnapBackend)
        self.snap.installed.return_value = [dict(name="example", version="1", revision="10", description="Example snap")]
        self.snap.api.return_value = [dict(name="example", summary="Example snap")]
        self.runner.run.return_value = completed(stdout="example - Editor\n")

    def session(self, source, answers, transaction=""):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(b, "capabilities", return_value={"tools": {source: True}}), \
                mock.patch.object(b, "Runner", return_value=self.runner), \
                mock.patch.object(b, "AptBackend", return_value=self.backend), \
                mock.patch.object(b, "SnapBackend", return_value=self.snap), \
                mock.patch.object(b, "apt_foreground") as apt, \
                mock.patch.object(b, "snap_foreground") as snap, \
                mock.patch.object(b, "lifecycle") as state, \
                mock.patch("builtins.input", side_effect=answers), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            b.management(self.paths, transaction)
        return apt, snap, state, output.getvalue(), errors.getvalue()

    def test_apt_search_installs_the_selected_native_identity(self):
        apt, _, _, output, _ = self.session("apt", ["1", "1", "editor", "1", "q"])
        apt.assert_called_once_with(self.paths, "install", ["example:amd64"], self.runner)
        self.assertIn("Editor", output)
        self.runner.run.assert_any_call(["/usr/bin/apt-cache", "search", "--", "editor"])

    def test_empty_search_and_menu_cancellation_do_not_start_an_operation(self):
        for answers in (["1", "1", "", "q"], ["1", "q", "q"], ["q"]):
            with self.subTest(answers=answers):
                apt, snap, *_ = self.session("apt", answers)
                apt.assert_not_called()
                snap.assert_not_called()

    def test_installed_manual_and_automatic_filters_preserve_architecture(self):
        for action in ("2", "3", "4"):
            with self.subTest(menu=action):
                apt, *_ = self.session("apt", ["1", action, "example", "1", "1", "q"])
                apt.assert_called_once_with(self.paths, "remove", ["example:amd64"], self.runner)

    def test_earlier_version_selection_keeps_the_exact_version(self):
        apt, *_ = self.session("apt", ["1", "7", "example", "1", "1:0.9~rc1-1", "q"])
        apt.assert_called_once_with(self.paths, "install-version", ["example:amd64", "1:0.9~rc1-1"], self.runner)

    def test_explicit_apt_maintenance_choices_route_to_distinct_actions(self):
        for choice, action in (("5", "autoremove"), ("9", "clean"), ("10", "autoclean"), ("12", "upgrade")):
            with self.subTest(action=action):
                apt, *_ = self.session("apt", ["1", choice, "q"])
                apt.assert_called_once_with(self.paths, action, [], self.runner)

    def test_local_deb_path_keeps_spaces_and_metacharacters_as_data(self):
        filename = str(self.root / "local package $(literal).deb")
        apt, *_ = self.session("apt", ["1", "6", filename, "q"])
        apt.assert_called_once_with(self.paths, "local-install", [filename], self.runner)

    def test_cached_archive_selection_and_cancellation(self):
        archive = self.root / "cached package.deb"
        archive.touch()
        with mock.patch.object(Path, "glob", return_value=[archive]):
            apt, *_ = self.session("apt", ["1", "8", "1", "q"])
        apt.assert_called_once_with(self.paths, "local-install", [str(archive)], self.runner)
        with mock.patch.object(Path, "glob", return_value=[archive]):
            apt, *_ = self.session("apt", ["1", "8", "q", "q"])
        apt.assert_not_called()

    def test_history_reads_plain_and_compressed_logs_without_native_changes(self):
        plain = self.root / "history.log"
        plain.write_text("Plain operation\n")
        compressed = self.root / "history.log.1.gz"
        with gzip.open(compressed, "wt") as stream:
            stream.write("Compressed operation\n")
        with mock.patch.object(Path, "glob", return_value=[plain, compressed]):
            apt, _, _, output, _ = self.session("apt", ["1", "11", "q"])
        apt.assert_not_called()
        self.assertIn("Plain operation", output)
        self.assertIn("Compressed operation", output)

    def test_snap_search_encodes_the_query_and_preserves_native_names(self):
        _, snap, *_ = self.session("snap", ["1", "1", "control panel", "1", "q"])
        self.snap.api.assert_called_once_with("/v2/find?q=control%20panel")
        snap.assert_called_once_with(self.paths, "install", ["example"], self.runner, transaction="")

    def test_snap_remove_purge_and_refresh_remain_separate_choices(self):
        for selection, action in (("1", "refresh"), ("2", "remove"), ("3", "purge")):
            with self.subTest(action=action):
                _, snap, _, output, _ = self.session("snap", ["1", "2", "", "1", selection, "q"])
                snap.assert_called_once_with(self.paths, action, ["example"], self.runner, transaction="")
                self.assertIn("Remove without a data snapshot", output)

    def test_snap_revert_and_bulk_refresh_route_explicitly(self):
        _, snap, *_ = self.session("snap", ["1", "3", "", "1", "q"])
        snap.assert_called_once_with(self.paths, "revert", ["example"], self.runner, transaction="")
        _, snap, *_ = self.session("snap", ["1", "6", "q"])
        snap.assert_called_once_with(self.paths, "refresh", [], self.runner, transaction="")

    def test_inactive_revision_menu_excludes_the_active_revision(self):
        self.snap.installed.return_value = [dict(name="example", revision="9", status="installed"),
                                            dict(name="example", revision="10", status="active")]
        _, snap, state, output, _ = self.session("snap", ["1", "4", "1", "q"], "revision-session")
        snap.assert_called_once_with(self.paths, "remove-revision", ["example", "9"], self.runner, transaction="revision-session")
        state.assert_called_once_with(self.paths, "stage", "revision-session", "snap", 0)
        self.assertNotIn("example 10", output)

    def test_snap_history_queries_the_selected_change(self):
        _, snap, *_ = self.session("snap", ["1", "5", "7", "q"])
        snap.assert_not_called()
        self.runner.run.assert_any_call(["/usr/bin/snap", "tasks", "7"], foreground=True, capture=False, timeout=None)

    def test_legacy_management_uses_only_the_selected_source(self):
        for source in ("pacman", "flatpak"):
            with self.subTest(source=source):
                apt, snap, *_ = self.session(source, ["1", "q"])
                apt.assert_not_called()
                snap.assert_not_called()
                self.runner.run.assert_any_call([str(b.SCRIPT_DIR / "sh/management"), "--legacy", source],
                                               foreground=True, capture=False, timeout=None)

    def test_failed_operation_records_failure_and_leaves_the_menu_usable(self):
        with mock.patch.object(b, "capabilities", return_value={"tools": {"apt": True}}), \
                mock.patch.object(b, "Runner", return_value=self.runner), \
                mock.patch.object(b, "AptBackend", return_value=self.backend), \
                mock.patch.object(b, "apt_foreground", side_effect=[b.BackendError("Failed", code=100), None]), \
                mock.patch.object(b, "lifecycle") as state, \
                mock.patch("builtins.input", side_effect=["1", "12", "1", "12", "q"]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            b.management(self.paths, "session")
        self.assertEqual([call.args[-1] for call in state.call_args_list], [100, 0])


class CliTests(TemporaryCase):
    def invoke(self, args, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(b, "Paths", return_value=self.paths), \
                mock.patch.object(b.signal, "signal"), mock.patch.object(b.sys, "stdin", io.StringIO(stdin)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = b.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_capabilities_and_installed_commands_return_structured_data(self):
        for command, function, result in (("capabilities", "capabilities", {"tools": {}, "terminals": []}),
                                           ("installed", "installed_records", {"items": [], "errors": []})):
            with self.subTest(command=command), mock.patch.object(b, function, return_value=result):
                code, out, _ = self.invoke([command])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out), result)

    def test_cache_writer_accepts_only_a_json_list(self):
        for payload, expected in (([{"uid": "apt:example:amd64"}], 0), ({"unexpected": True}, 1)):
            with self.subTest(payload=payload):
                code, out, _ = self.invoke(["write-cache"], json.dumps(payload))
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(out)["status"], "ok" if expected == 0 else "error")
        self.assertEqual(b.read_json(self.paths.cache / "updates.json"), [{"uid": "apt:example:amd64"}])

    def test_cache_chunks_and_cancel_markers_use_the_requested_identity(self):
        code, _, _ = self.invoke(["cache-chunk", "chunk", "0", "1", "--", '[{"uid":"snap:example"}]'])
        self.assertEqual(code, 0)
        self.assertEqual(b.read_json(self.paths.cache / "updates.json"), [{"uid": "snap:example"}])
        code, _, _ = self.invoke(["cancel", "request-1"])
        self.assertEqual(code, 0)
        self.assertTrue(self.paths.canceled("request-1"))
        self.assertFalse(self.paths.canceled("request-2"))

    def test_check_exit_status_matches_backend_result(self):
        for status, expected in (("ok", 0), ("partial", 1), ("unavailable", 1)):
            result = dict(schemaVersion=1, status=status, items=[])
            with self.subTest(status=status), mock.patch.object(b, "check_backend", return_value=result) as check:
                code, out, _ = self.invoke(["check", "apt", "--mode", "full", "--request-id", "check-1"])
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(out), result)
                self.assertEqual(check.call_args.args[-1], "full")

    def test_invalid_request_identifiers_cannot_reach_the_backend(self):
        with mock.patch.object(b, "check_backend") as check:
            code, out, _ = self.invoke(["check", "snap", "--request-id", "../other"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["errors"][0]["category"], "invalid-input")
        check.assert_not_called()

    def test_foreground_commands_route_arguments_without_machine_json(self):
        for source, action, values in (("apt", "upgrade-package", ["example:amd64"]), ("snap", "refresh", ["example"])):
            with self.subTest(source=source), mock.patch.object(b, source + "_foreground") as foreground:
                code, out, _ = self.invoke(["foreground", source, action, *values, "--transaction", "cli-session"])
                self.assertEqual(code, 0)
                self.assertEqual(out, "")
                self.assertEqual(foreground.call_args.args, (self.paths, action, values))

    def test_terminal_errors_preserve_native_exit_codes_and_redact_credentials(self):
        with mock.patch.object(b, "apt_foreground", side_effect=b.BackendError("https://user:secret@example.invalid/file token=hidden", code=100)):
            code, out, err = self.invoke(["foreground", "apt", "upgrade"])
        self.assertEqual(code, 100)
        self.assertEqual(out, "")
        self.assertNotIn("secret", err)
        self.assertNotIn("hidden", err)

    def test_management_completion_cancellation_and_failure_record_real_lifecycle_states(self):
        for error, expected_code, expected_state in ((None, 0, "ok"), (KeyboardInterrupt(), 130, "canceled"),
                                                     (ValueError("Invalid selection"), 1, "error")):
            with self.subTest(state=expected_state), mock.patch.object(b, "management", side_effect=error):
                code, _, _ = self.invoke(["management", "--transaction", "cli-management"])
                self.assertEqual(code, expected_code)
                self.assertEqual(b.read_json(self.paths.cache / "upgrade-state.json")["status"], expected_state)

    def test_lifecycle_cli_preserves_a_native_stage_failure(self):
        code, _, _ = self.invoke(["lifecycle", "start", "--id", "cli-lifecycle", "--pid", str(os.getpid())])
        self.assertEqual(code, 0)
        self.invoke(["lifecycle", "stage", "--id", "cli-lifecycle", "--stage", "apt", "--code", "100"])
        code, out, _ = self.invoke(["lifecycle", "finish", "--id", "cli-lifecycle"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "error")


class InventoryTests(TemporaryCase):
    def test_installed_inventory_separates_all_native_identities(self):
        self.paths.config.joinpath("config.conf").write_text(''.join(
            source + '="true"\n' for source in ("apt", "snap", "arch", "flatpak", "widgets", "fwupd")))
        def run(argv, **kwargs):
            if argv[0] == "pacman":
                return completed(stdout="example 1\n")
            if argv[0] == "flatpak":
                return completed(stdout="org.example.App\tstable\tx86_64\tuser\t1\tcommit\n")
            if argv[0].endswith("sh/widgets"):
                return completed(stdout='{"NM":"example","nativeId":"org.example.widget","VO":"1"},')
            if argv[0] == "fwupdmgr":
                return completed(stdout=json.dumps({"Devices": [{"DeviceId": "device-1", "Name": "example", "Version": "1"}]}))
            self.fail("Unexpected native command: " + repr(argv))
        self.runner.run.side_effect = run
        with mock.patch.object(b, "Runner", return_value=self.runner), \
                mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED), \
                mock.patch.object(b.SnapBackend, "installed", return_value=[dict(name="example", revision="10", version="1")]):
            result = b.installed_records(self.paths)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len({item["uid"] for item in result["items"]}), 7)
        self.assertIn("flatpak:user:org.example.App/x86_64/stable", {item["uid"] for item in result["items"]})

    def test_one_inventory_failure_keeps_independent_sources(self):
        self.paths.config.joinpath("config.conf").write_text('apt="true"\nsnap="true"\n')
        with mock.patch.object(b.AptBackend, "installed", side_effect=b.BackendError("APT unavailable")), \
                mock.patch.object(b.SnapBackend, "installed", return_value=[dict(name="example", revision="10")]):
            result = b.installed_records(self.paths)
        self.assertEqual([item["backend"] for item in result["items"]], ["snap"])
        self.assertEqual(result["errors"][0]["backend"], "apt")

    def test_successful_apt_check_counts_installed_upgrades_without_new_dependencies(self):
        preview = UPGRADE + "Inst new-dependency (1 Debian:stable [all])\n"
        self.runner.run.return_value = completed(stdout=preview)
        with mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED), \
                mock.patch.object(b.AptBackend, "indexes", return_value=contextlib.nullcontext([])), \
                mock.patch.object(b.AptBackend, "audit_sources"), \
                mock.patch.object(b.AptBackend, "metadata", return_value=[dict(Package="example", Architecture="amd64", Version="2.0-1", Description="Editor", Homepage="https://example.invalid")]), \
                mock.patch.object(b.AptBackend, "marks", return_value={"example"}):
            result = b.check_backend("apt", self.paths, self.runner)
        self.assertTrue(result["metadataCurrent"])
        self.assertEqual([item["uid"] for item in result["items"]], ["apt:example:amd64"])
        self.assertEqual(result["items"][0]["summary"], "Editor")
        self.assertEqual(result["items"][0]["installReason"], "explicit")


class NetworkDiagnosticTests(TemporaryCase):
    def run_failure(self, stdout, stderr, code=100):
        process = mock.Mock()
        process.communicate.return_value = (stdout, stderr)
        process.returncode = code
        with mock.patch.object(b.subprocess, "Popen", return_value=process):
            return b.Runner(self.paths).run(["/usr/bin/apt-get", "--error-on=any", "update"])

    def test_network_failure_in_stdout_explains_secondary_release_errors(self):
        with self.assertRaises(b.BackendError) as error:
            self.run_failure("Err:1 https://example.invalid stable Release\n  Network is unreachable\n",
                             "E: The repository 'https://example.invalid stable Release' no longer has a Release file.")
        self.assertEqual(error.exception.category, "network-error")
        self.assertEqual(error.exception.code, 100)
        self.assertIn("network", str(error.exception).lower())
        self.assertIn("Release file", str(error.exception))

    def test_genuine_missing_release_and_signature_errors_remain_native_failures(self):
        for message in ("E: The repository no longer has a Release file.", "E: Signature verification failed: NO_PUBKEY ABCDEF"):
            with self.subTest(message=message), self.assertRaises(b.BackendError) as error:
                self.run_failure("Err: 404 Not Found", message)
            self.assertEqual(error.exception.category, "command-error")
            self.assertIn(message, str(error.exception))

    def test_successful_connection_fallback_is_not_reported_as_failure(self):
        result = self.run_failure("IPv6 network is unreachable; IPv4 succeeded\n", "", code=0)
        self.assertEqual(result.returncode, 0)

    def test_network_diagnostics_redact_credentials_from_both_output_streams(self):
        with self.assertRaises(b.BackendError) as error:
            self.run_failure("Could not connect to https://user:secret@example.invalid/file\n", "token=hidden")
        self.assertNotIn("secret", str(error.exception))
        self.assertNotIn("hidden", str(error.exception))


class NativeBoundaryTests(TemporaryCase):
    def test_dpkg_inventory_keeps_foreign_and_architecture_independent_packages(self):
        self.runner.run.return_value = completed(stdout=(
            "example\tamd64\t1:2.0~rc1-1\tinstalled\n"
            "example\ti386\t1:2.0~rc1-1\tinstalled\n"
            "independent\tall\t1\tinstalled\nremoved\tamd64\t1\tconfig-files\n"))
        records = self.apt().installed()
        self.assertEqual(set(records), {"example:amd64", "example:i386", "independent:all"})
        self.assertEqual(records["example:i386"]["installedVersion"], "1:2.0~rc1-1")

    def test_malformed_dpkg_inventory_is_an_error(self):
        self.runner.run.return_value = completed(stdout="example\t1\n")
        with self.assertRaises(b.BackendError):
            self.apt().installed()

    def test_capabilities_require_a_native_debian_system_and_all_apt_tools(self):
        names = {"apt-get", "apt-cache", "apt-mark", "apt-config", "dpkg", "dpkg-query", "dpkg-deb", "snap", "konsole"}
        def which(name):
            return "/usr/bin/" + name if name in names else None
        for release, database, apt in (("ubuntu", True, True), ("debian", True, True), ("arch", True, False), ("ubuntu", False, False)):
            with self.subTest(release=release, database=database), \
                    mock.patch.object(b, "os_release", return_value={"ID": release}), \
                    mock.patch.object(b.shutil, "which", side_effect=which), mock.patch.object(Path, "is_file", return_value=database):
                result = b.capabilities(self.paths)
                self.assertEqual(result["tools"]["apt"], apt)
                self.assertTrue(result["tools"]["snap"])
                self.assertEqual(result["terminals"], ["/usr/bin/konsole"])

    def test_flatpak_terminal_discovery_is_optional(self):
        names = {"flatpak", "konsole"}
        self.runner.run.side_effect = lambda argv, **kwargs: completed(stdout=(
            "org.example.Terminal\n" if argv[1] == "list" else "command=konsole\norg.freedesktop.Flatpak=talk\n"))
        with mock.patch.object(b.shutil, "which", side_effect=lambda name: "/usr/bin/" + name if name in names else None), \
                mock.patch.object(b, "Runner", return_value=self.runner):
            result = b.capabilities(self.paths)
            self.assertIn("flatpak://org.example.Terminal/konsole", result["terminals"])
            self.runner.run.side_effect = b.BackendError("Optional terminal inspection failed")
            result = b.capabilities(self.paths)
            self.assertEqual(result["terminals"], ["/usr/bin/konsole"])

    def test_confirmation_needs_an_explicit_yes_and_eof_means_cancel(self):
        for answer in ("", "no", "unexpected"):
            with self.subTest(answer=answer), mock.patch("builtins.input", return_value=answer), self.assertRaises(b.BackendError) as error:
                b.confirm("Continue?")
            self.assertEqual(error.exception.code, 130)
        with mock.patch("builtins.input", side_effect=EOFError), self.assertRaises(b.BackendError):
            b.confirm("Continue?")
        with mock.patch("builtins.input", return_value="YES"):
            b.confirm("Continue?")

    def test_administrator_prefix_preserves_quoted_arguments_and_foreground_semantics(self):
        settings = dict(sudoBin='"admin helper" --label "value with spaces"', idleInhibit="true")
        with mock.patch.object(b.shutil, "which", return_value="/usr/bin/systemd-inhibit"), contextlib.redirect_stdout(io.StringIO()):
            b.administrator(["/usr/bin/apt-get", "upgrade"], settings, self.runner)
        argv = self.runner.run.call_args.args[0]
        self.assertEqual(argv[-6:], ["--", "admin helper", "--label", "value with spaces", "/usr/bin/apt-get", "upgrade"])
        self.assertIn("systemd-inhibit", argv)
        self.assertEqual(self.runner.run.call_args.kwargs, dict(foreground=True, capture=False, timeout=None))

    def test_missing_administrator_command_stops_before_execution(self):
        with self.assertRaises(b.BackendError):
            b.administrator(["/usr/bin/apt-get", "upgrade"], {"sudoBin": ""}, self.runner)
        self.runner.run.assert_not_called()

    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_individual_upgrades_respect_holds_and_native_bulk_eligibility(self, installed):
        for holds in ({"example"}, set()):
            with self.subTest(holds=holds), mock.patch.object(b.AptBackend, "marks", return_value=holds), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(b.BackendError) as error:
                b.apt_foreground(self.paths, "upgrade-package", ["example:amd64"], self.runner)
            self.assertEqual(error.exception.category, "blocked")
        self.assertFalse(any("install" in call.args[0] for call in self.runner.run.call_args_list))

    @mock.patch.object(b, "confirm")
    @mock.patch.object(b.AptBackend, "installed", return_value=INSTALLED)
    def test_local_deb_uses_a_single_path_argument_and_native_dependency_resolution(self, installed, confirm):
        archive = self.root / "local package.deb"
        archive.touch()
        def run(argv, **kwargs):
            if "--field" in argv:
                return completed(stdout="Package: local\nArchitecture: all\nVersion: 1\n")
            return completed(stdout="Inst local (1 Test:stable [all])\n" if "--simulate" in argv else "")
        self.runner.run.side_effect = run
        with contextlib.redirect_stdout(io.StringIO()):
            b.apt_foreground(self.paths, "local-install", [str(archive)], self.runner)
        command = self.runner.run.call_args.args[0]
        self.assertEqual(command[-2:], ["install", str(archive)])
        self.assertIn("--no-remove", command)
        self.assertTrue(any("--field" in call.args[0] for call in self.runner.run.call_args_list))

    def test_snap_global_hold_falls_back_to_authorized_terminal_read_without_logging_config(self):
        backend = mock.Mock(spec=b.SnapBackend)
        backend.api.side_effect = b.BackendError("Authorization required", "auth-required", 403)
        self.runner.run.return_value = completed(stdout=json.dumps({"refresh": {"hold": "forever"}, "proxy": "secret"}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            held = b.snap_global_hold(backend, {"sudoBin": "sudo"}, self.runner)
        self.assertTrue(held)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(self.runner.run.call_args.args[0], ["sudo", "/usr/bin/snap", "get", "-d", "system"])

    def test_unknown_global_snap_hold_state_blocks_refresh(self):
        backend = mock.Mock(spec=b.SnapBackend)
        for payload in ([], {"refresh": []}):
            with self.subTest(payload=payload), self.assertRaises(b.BackendError):
                backend.api.return_value = payload
                b.snap_global_hold(backend, {"sudoBin": "sudo"}, self.runner)

    def test_snap_transport_errors_and_invalid_json_are_not_empty_results(self):
        for body, status, category in ((b"invalid JSON", 200, "invalid-output"),
                                       (b'{"status-code":403,"type":"error","result":{"message":"No access"}}', 403, "auth-required"),
                                       (b'{"status-code":500,"type":"error","result":{}}', 500, "service-unavailable")):
            with self.subTest(status=status), mock.patch.object(b, "UnixHTTP") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = status
                response.read.return_value = body
                with self.assertRaises(b.BackendError) as error:
                    b.SnapBackend(self.paths).api("/v2/snaps")
                self.assertEqual(error.exception.category, category)
                connection.return_value.close.assert_called_once()

    def test_busy_transaction_preserves_last_complete_result(self):
        previous = dict(schemaVersion=1, backend="apt", items=[INSTALLED["example:amd64"]], synchronizedAt=123)
        b.atomic_json(self.paths.cache / "apt-result.json", previous)
        with mock.patch.object(b, "lifecycle", return_value={"status": "running"}), mock.patch.object(b.AptBackend, "check") as check:
            result = b.check_backend("apt", self.paths)
        self.assertEqual(result["status"], "busy")
        self.assertEqual(result["synchronizedAt"], 123)
        check.assert_not_called()

    def test_private_lock_contention_does_not_remove_the_lock(self):
        path = self.paths.cache / "operation.lock"
        with b.file_lock(path):
            with self.assertRaises(b.BackendError) as error, b.file_lock(path):
                self.fail("The second lock must not succeed")
            self.assertEqual(error.exception.category, "busy")
            self.assertTrue(path.is_file())
        with b.file_lock(path):
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
