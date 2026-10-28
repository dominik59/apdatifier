#!/usr/bin/python3
"""APT and snapd integration. Only the Python standard library is required.

This program always runs as the desktop user. Only explicit foreground native
commands receive the configured administrator prefix.
"""

import argparse
import contextlib
import datetime
import fcntl
import gettext
import gzip
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid


SCHEMA = 1
SCRIPT_DIR = Path(__file__).resolve().parent
_ = gettext.translation(
    "plasma_applet_com.github.exequtic.apdatifier",
    localedir=str(SCRIPT_DIR.parent / "locale"), fallback=True,
).gettext
PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]+")
ARCH = re.compile(r"[a-z0-9][a-z0-9-]*")
VERSION = re.compile(r"(?:[0-9]+:)?[0-9][A-Za-z0-9.+:~\-]*")
SNAP_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:_[a-z0-9]{1,10})?")
TOKEN = re.compile(r"[A-Za-z0-9-]{1,100}")
NETWORK_FAILURE = re.compile(
    r"could not (?:connect|resolve)|network (?:is )?unreachable|network is down|"
    r"no route to host|temporary failure (?:in |resolving)|connection timed out|"
    r"connection refused|failed to connect", re.I,
)
TERMINALS = ("alacritty", "foot", "ghostty", "gnome-terminal", "kitty", "konsole",
             "lxterminal", "ptyxis", "terminator", "tilix", "wezterm", "xterm", "yakuake")


class BackendError(Exception):
    def __init__(self, message, category="command-error", code=1):
        super().__init__(message)
        self.category, self.code = category, code


def redact(text, limit=6000):
    text = re.sub(r"(https?://)[^/\s@]+@", r"\1[redacted]@", str(text))
    text = re.sub(r"(?im)(authorization|password|token)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return text[-limit:] if limit else text


def now():
    return int(time.time() * 1000)


def os_release(path="/etc/os-release"):
    result = {}
    for line in Path(path).read_text().splitlines():
        if re.match(r"^[A-Z_]+=", line):
            key, value = line.split("=", 1)
            values = shlex.split(value)
            result[key] = values[0] if values else ""
    return result


def load_config(path):
    """Read values, without executing the user's shell configuration."""
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            match = re.fullmatch(r'(\w+)="(.*)"', line)
            if match:
                values[match[1]] = re.sub(r'\\([\\"$`])', r'\1', match[2])
    return values


def private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise BackendError(_("The private directory has an unsafe owner or type."), "permissions")
    path.chmod(0o700)
    return path


def read_json(path, default=None):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return default
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise BackendError(_("The data file has an unsafe owner or type."), "permissions")
        try:
            return json.load(stream)
        except (ValueError, UnicodeError) as error:
            raise BackendError(_("The data file is not valid JSON."), "invalid-output") from error


def atomic_json(path, value):
    path = Path(path)
    parent = private_dir(path.parent)
    if path.is_symlink():
        raise BackendError(_("A data file must not be a symbolic link."), "permissions")
    fd, name = tempfile.mkstemp(prefix=".apdatifier-", dir=parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def cache_chunk(paths, token, index, total, data):
    validate(token, TOKEN, "cache identifier")
    if not 0 <= index < total <= 10000:
        raise BackendError(_("Invalid cache chunk."), "invalid-input")
    root = private_dir(paths.cache)
    part = root / ("updates-" + token + ".part")
    flags = os.O_WRONLY | os.O_NOFOLLOW
    flags |= os.O_CREAT | os.O_EXCL if index == 0 else os.O_APPEND
    fd = os.open(part, flags, 0o600)
    with os.fdopen(fd, "w") as stream:
        if os.fstat(stream.fileno()).st_uid != os.getuid():
            raise BackendError(_("The cache chunk has an unsafe owner."), "permissions")
        stream.write(data)
    if index + 1 == total:
        try:
            result = read_json(part)
            if not isinstance(result, list):
                raise BackendError(_("The cache must contain a list."), "invalid-input")
            atomic_json(root / "updates.json", result)
        finally:
            part.unlink()
    return dict(status="ok")


@contextlib.contextmanager
def file_lock(path):
    private_dir(Path(path).parent)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise BackendError(_("The lock has an unsafe owner."), "permissions")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BackendError(_("Another operation is in progress."), "busy") from error
        yield
    finally:
        os.close(fd)


class Paths:
    def __init__(self, config=None, cache=None):
        self.config = Path(config or os.environ.get("APDATIFIER_CONFIG_DIR") or
                           Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "apdatifier")
        self.cache = Path(cache or os.environ.get("APDATIFIER_CACHE_DIR") or
                          Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "apdatifier")

    def settings(self):
        return load_config(self.config / "config.conf")

    def exclusions(self, backend):
        rules = read_json(self.config / "rules.json", []) or []
        if not isinstance(rules, list):
            raise BackendError(_("The rules file must contain a list."), "invalid-output")
        return [rule["value"] for rule in rules if isinstance(rule, dict)
                and rule.get("backend") == backend and rule.get("type") == "name"
                and rule.get("ignore") is True and isinstance(rule.get("value"), str)]

    def canceled(self, token):
        if not token:
            return False
        validate(token, TOKEN, "request identifier")
        return (self.cache / ("cancel-" + token)).exists()


class Runner:
    def __init__(self, paths=None, token=""):
        self.paths, self.token = paths, token

    def run(self, argv, *, timeout=300, foreground=False, capture=True, check=True, capture_stderr=False):
        env = dict(os.environ)
        if not foreground or capture:
            env.update(LC_ALL="C", LANGUAGE="C")
        process = subprocess.Popen(
            [str(part) for part in argv], env=env, text=True, errors="replace",
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture and (capture_stderr or not foreground) else None,
            start_new_session=not foreground,
        )
        deadline = time.monotonic() + timeout if timeout is not None else None
        try:
            while True:
                if not foreground and self.paths and self.paths.canceled(self.token):
                    raise BackendError(_("The check was canceled."), "canceled", 130)
                if deadline is not None and time.monotonic() > deadline:
                    raise BackendError(_("The command timed out."), "network-error")
                try:
                    out, err = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if not foreground and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
            raise
        result = subprocess.CompletedProcess(argv, process.returncode, out or "", err or "")
        if check and result.returncode:
            message = redact(result.stderr or result.stdout) or _("The native command failed.")
            category = "command-error"
            output = result.stdout + "\n" + result.stderr
            if NETWORK_FAILURE.search(output):
                category = "network-error"
                evidence = [line for line in output.splitlines() if NETWORK_FAILURE.search(line)]
                message = (_("The update server could not be reached. Check the network connection.") +
                           "\n" + redact("\n".join(evidence[:3])) + "\n" + message)
            raise BackendError(message, category, result.returncode)
        return result


def validate(value, pattern, label):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise BackendError(_("Invalid value: ") + label, "invalid-input")
    return value


def apt_selector(name, arch, version=None):
    """Validate fields separately, then produce exactly one native argument."""
    validate(name, PACKAGE, "package name")
    validate(arch, ARCH, "architecture")
    selector = name + ":" + arch
    if version is not None:
        selector += "=" + validate(version, VERSION, "version")
    return selector


def split_apt_id(identifier):
    parts = identifier.split(":")
    if len(parts) != 2:
        raise BackendError(_("An APT package needs a name and architecture."), "invalid-input")
    apt_selector(*parts)
    return parts


def control_records(text):
    records, record, key = [], {}, None
    for line in text.splitlines() + [""]:
        if not line:
            if record:
                records.append(record)
            record, key = {}, None
        elif line.startswith((" ", "\t")) and key:
            record[key] += "\n" + line[1:]
        elif ":" in line:
            key, value = line.split(":", 1)
            record[key] = value.strip()
        else:
            raise BackendError(_("The package metadata has an unknown format."), "invalid-output")
    return records


def package_description(record):
    return record.get("Description") or record.get("Description-en") or next(
        (value for key, value in record.items() if key.startswith("Description-") and key != "Description-md5"), "")


def parse_simulation(text, installed, *, configure=False, package_data=None):
    """Keep native operations distinct from candidate versions printed by Conf."""
    changes, configurations = {}, {}
    operations, configuration_records = [], []
    configure_states = ("installed", "unpacked", "half-configured", "triggers-awaited", "triggers-pending")
    package_data = installed if package_data is None else package_data
    by_name = {}
    for pkg in package_data.values():
        by_name.setdefault(pkg["name"], []).append(pkg)
    for line in text.splitlines():
        if not re.match(r"^(Inst|Remv|Purg|Conf)\b", line):
            continue
        match = re.fullmatch(
            r"(Inst|Remv|Purg|Conf) ([a-z0-9][a-z0-9+.\-]*(?::[a-z0-9-]+)?)"
            r"(?: \[([^\]]+)\])?(?: \((.+)\))?(?: \[[^\]]*\])*", line,
        )
        if not match:
            raise BackendError(_("The APT transaction contains an unknown record.") + "\n" + redact(line)[:500],
                               "invalid-output")
        action, identifier, old, details = match.groups()
        if action == "Conf":
            if configure:
                configuration_records.append(match.groups())
            continue
        operations.append(match.groups())
    install_selectors = {}
    for action, identifier, old, details in operations + configuration_records:
        native_selector = identifier
        arch_match = re.search(r"\[([a-z0-9-]+)\]$", details or "")
        if action == "Conf" and native_selector in install_selectors:
            name, arch = split_apt_id(install_selectors[native_selector])
        elif ":" in identifier:
            name, arch = split_apt_id(identifier)
        else:
            name = identifier
            matches = by_name.get(name, [])
            if action == "Conf":
                matches = [pkg for pkg in matches if pkg.get("dpkgState") in configure_states]
                arch = matches[0]["architecture"] if len(matches) == 1 else ""
            else:
                arch = arch_match.group(1) if arch_match else (matches[0]["architecture"] if len(matches) == 1 else "")
            if not arch:
                raise BackendError(_("APT did not identify the package architecture."), "invalid-output")
        identifier = apt_selector(name, arch)
        candidate = details.split()[0] if details else ""
        if action == "Inst":
            validate(candidate, VERSION, "candidate version")
        previous = installed.get(identifier, {}) if action == "Inst" else installed.get(
            identifier, package_data.get(identifier, {}))
        entry = dict(action=action, nativeId=identifier, name=name, architecture=arch,
                     installedVersion=previous.get("installedVersion", old or ""),
                     candidateVersion=candidate, repository=(details or "").split(" ", 1)[-1])
        destination = configurations if action == "Conf" else changes
        if identifier in destination and destination[identifier] != entry:
            raise BackendError(_("The APT transaction contains an unknown record."), "invalid-output")
        destination[identifier] = entry
        if action == "Inst":
            if native_selector in install_selectors and install_selectors[native_selector] != identifier:
                raise BackendError(_("The APT transaction contains an unknown record."), "invalid-output")
            install_selectors[native_selector] = identifier
    for identifier, entry in configurations.items():
        if identifier in changes:
            if changes[identifier]["action"] != "Inst":
                raise BackendError(_("The APT transaction contains an unknown record."), "invalid-output")
            continue
        pkg = package_data.get(identifier, {})
        if pkg.get("dpkgState") not in configure_states:
            raise BackendError(_("The APT transaction contains an unknown record."), "invalid-output")
        current = validate(pkg.get("installedVersion", ""), VERSION, "configured version")
        entry.update(installedVersion=current, candidateVersion=current)
        changes[identifier] = entry
    return list(changes.values())


APT_PREVIEW_OPTIONS = [
    "-o", "quiet=0", "-o", "APT::Get::HideAutoRemove=false",
    "-o", "APT::Get::Show-Versions=false", "-o", "APT::Get::List-Columns=false",
    "-o", "APT::Color=false",
]
APT_INFORMATION = {
    "The following package was automatically installed and is no longer required:": "autoremove",
    "The following packages were automatically installed and are no longer required:": "autoremove",
    "The following upgrade has been deferred due to phasing:": "phased",
    "The following upgrades have been deferred due to phasing:": "phased",
    "The following packages have been kept back:": "deferred",
    "The following package has been kept back:": "deferred",
    "Not upgrading yet due to phasing:": "phased",
    "Not upgrading:": "deferred",
}
APT_PACKAGE_LISTS = {
    "The following additional packages will be installed:", "The following NEW packages will be installed:",
    "The following packages will be upgraded:", "The following packages will be DOWNGRADED:",
    "The following packages will be REMOVED:", "The following packages will be reinstalled:",
    "Installing:", "Installing dependencies:", "Upgrading:", "Downgrading:", "Removing:", "Reinstalling:",
}


def apt_information(text):
    """Read optional lists without treating suppressed or unfamiliar output as zero."""
    result = dict(autoremove=None, phased=[], deferred=[], diagnostics=[], summary=False, candidate_error=False,
                  operation_count=None, removal_count=None)
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        kind = APT_INFORMATION.get(line)
        if kind or line in APT_PACKAGE_LISTS:
            heading = line
            rows = []
            index += 1
            while index < len(lines) and lines[index].startswith("  "):
                rows.append(lines[index])
                index += 1
            names = " ".join(rows).split()
            valid = bool(names) and all(re.fullmatch(r"[a-z0-9][a-z0-9+.\-]+(?::[a-z0-9-]+)?", name.rstrip("*") if not kind else name) for name in names)
            if kind == "autoremove" and (index == len(lines) or not re.fullmatch(
                    r"Use '.+ autoremove' to remove (?:it|them)\.", lines[index])):
                valid = False
            if kind:
                if valid and (kind != "autoremove" or result[kind] is None):
                    result[kind] = list(dict.fromkeys([*(result[kind] or []), *names]))
                else:
                    if kind == "autoremove":
                        result["candidate_error"] = True
                    result["diagnostics"].extend([heading, *rows])
            elif not valid:
                result["diagnostics"].extend([heading, *rows])
            continue
        if re.fullmatch(r"\d+ upgraded, (?:\d+ (?:newly installed|reinstalled|downgraded|to remove)(?:, | and ))+\d+ not upgraded\.", line):
            result["summary"] = True
            counts = {label: int(count) for count, label in re.findall(
                r"(\d+) (upgraded|newly installed|reinstalled|downgraded|to remove|not upgraded)", line)}
            result["operation_count"] = sum(counts.get(label, 0) for label in ("upgraded", "newly installed", "reinstalled", "downgraded"))
            result["removal_count"] = counts["to remove"]
        elif re.match(r"^(?:Inst|Conf|Remv|Purg)\b", line):
            pass
        elif re.match(r"^(?:Reading package lists|Building dependency tree|Reading state information|Calculating upgrade)\.\.\.", line):
            pass
        elif re.fullmatch(r"Use '.+ autoremove' to remove (?:it|them)\.", line):
            pass
        elif line.strip():
            result["diagnostics"].append(line)
            if re.search(r"automatically installed.*no longer required|autoremove", line, re.I):
                result["candidate_error"] = True
        index += 1
    return result


def apt_candidate_rows(names, inventory):
    by_name = {}
    for pkg in inventory.values():
        by_name.setdefault(pkg["name"], []).append(pkg)
    rows = {}
    for name in names:
        matches = [inventory[name]] if name in inventory else by_name.get(name, [])
        if len(matches) != 1:
            return None
        pkg = matches[0]
        if not VERSION.fullmatch(pkg.get("installedVersion", "")):
            return None
        rows[pkg["nativeId"]] = pkg
    return sorted(rows.values(), key=lambda pkg: (pkg["name"], pkg["architecture"]))


def apt_version_order(candidate, current, runner):
    if candidate == current:
        return 0
    for operator, order in (("gt", 1), ("lt", -1)):
        result = runner.run(["/usr/bin/dpkg", "--compare-versions", candidate, operator, current], check=False)
        if result.returncode == 0:
            return order
        if result.returncode != 1:
            raise BackendError(_("Cannot compare the selected APT versions."), "invalid-output")
    return 0


def apt_operation_groups(changes, runner):
    groups = {name: [] for name in ("install", "upgrade", "downgrade", "reinstall", "remove", "configure")}
    comparisons = {}
    for change in changes:
        if change["action"] in ("Remv", "Purg"):
            group = "remove"
        elif change["action"] == "Conf":
            group = "configure"
        elif not change["installedVersion"]:
            group = "install"
        else:
            pair = change["candidateVersion"], change["installedVersion"]
            if pair not in comparisons:
                comparisons[pair] = apt_version_order(*pair, runner)
            order = comparisons[pair]
            group = "upgrade" if order > 0 else "downgrade" if order < 0 else "reinstall"
        groups[group].append(change)
    for rows in groups.values():
        rows.sort(key=lambda row: (row["name"], row["architecture"]))
    return groups


def apt_preview_policy(installed, pins, settings, runner):
    """Only verified APT 3.2.0 output can establish zero from an absent section."""
    versions = [pkg["installedVersion"] for pkg in installed.values() if pkg["name"] == "apt"]
    supported = len(versions) == 1 and bool(re.fullmatch(r"(?:\d+:)?3\.2\.0(?:[-+].*)?", versions[0]))
    if not supported:
        return False
    try:
        config_result = administrator([
            "/usr/bin/apt-config", *pins, *APT_PREVIEW_OPTIONS, "shell",
            "AUTO", "APT::Get::AutomaticRemove", "BINARY_AUTO", "Binary::apt-get::APT::Get::AutomaticRemove",
        ], settings, runner, capture=True, capture_stderr=True)
        if config_result.stderr:
            print(_("APT messages") + "\n" + redact(config_result.stderr, limit=None), file=sys.stderr)
        values = dict(token.split("=", 1) for token in shlex.split(config_result.stdout))
    except BackendError as error:
        if error.category == "canceled":
            raise
        return False
    except ValueError:
        return False
    value = values.get("BINARY_AUTO", values.get("AUTO", "false")).lower()
    return value in ("false", "no", "0", "off")


def print_apt_summary(groups, info, inventory, *, zero_verified=False, autoremove=False):
    labels = dict(install=_("Install"), upgrade=_("Upgrade"), downgrade=_("Downgrade"),
                  reinstall=_("Reinstall"), remove=_("Remove"), configure=_("Configure"))
    for group, rows in groups.items():
        print(f"{labels[group]} ({len(rows)})")
        for row in rows:
            identity, old, new = row["nativeId"], row["installedVersion"], row["candidateVersion"]
            version = old if group in ("remove", "configure") else (old + " -> " + new if old else "-> " + new)
            suffix = " (" + _("including configuration files") + ")" if row["action"] == "Purg" else ""
            print(f"  {identity} {version}{suffix}")
        if rows:
            print()
    phased = set(info["phased"])
    for label, names in ((_("Deferred because of phasing"), phased),
                         (_("Deferred updates"), set(info["deferred"]) - phased)):
        if names:
            print(f"\n{label} ({len(names)})")
            for name in sorted(names):
                print("  " + name)
    removed = {row["nativeId"] for row in groups["remove"]}
    candidates = None
    if info["autoremove"] is not None and not info["candidate_error"]:
        candidates = apt_candidate_rows(info["autoremove"], inventory)
    elif zero_verified and info["summary"] and not info["candidate_error"] and not autoremove:
        candidates = []
    if candidates is not None:
        candidates = [row for row in candidates if row["nativeId"] not in removed]
    status = (_("Not applicable") if autoremove and info["autoremove"] is None else
              _("Candidate list unavailable") if candidates is None else str(len(candidates)))
    print("\n" + _("Optional cleanup") + ": " + status)
    if candidates:
        print(_("These packages will not be removed during this operation."))
        print(_("You can remove them with a separate autoremove operation."))
    for row in candidates or []:
        print("  " + row["nativeId"] + " " + row["installedVersion"])
    total = len({row["nativeId"] for rows in groups.values() for row in rows})
    print("\n" + _("Transaction total") + ": " + str(total))
    print(", ".join(labels[group] + ": " + str(len(rows)) for group, rows in groups.items()))
    print(_("Deferred updates") + ": " + str(len(phased | set(info["deferred"]))))
    print(_("Optional cleanup") + ": " + status)
    if not total:
        print(_("No package operations are planned."))
    if info["diagnostics"]:
        print("\n" + _("APT messages"))
        print(redact("\n".join(info["diagnostics"]), limit=None))


def package_record(backend, identifier, name, installed="", candidate="", **fields):
    record = dict(
        uid=backend + ":" + identifier, backend=backend, nativeId=identifier, name=name,
        architecture="", installedVersion=installed, candidateVersion=candidate,
        installedRevision="", candidateRevision="", repository=backend, summary="",
        homepage="", icon="", installReason="unknown", state="available",
    )
    record.update(fields)
    return record


class AptBackend:
    def __init__(self, paths, runner=None, mode="auto", release=None):
        self.paths = paths
        self.runner = runner or Runner(paths)
        self.release = release if release is not None else os_release()
        if mode not in ("auto", "safe", "full"):
            raise BackendError(_("Unknown APT upgrade mode."), "invalid-input")
        neon = self.release.get("ID") == "neon"
        self.mode = ("full" if neon else "safe") if mode == "auto" else mode
        if neon and self.mode != "full":
            raise BackendError(_("KDE neon requires full upgrade mode."), "invalid-input")

    def package_states(self):
        text = self.runner.run([
            "/usr/bin/dpkg-query", "-W",
            "-f=${Package}\t${Architecture}\t${Version}\t${db:Status-Status}\n",
        ]).stdout
        result = {}
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) != 4:
                raise BackendError(_("dpkg returned an unknown record."), "invalid-output")
            name, arch, version, state = parts
            if state == "not-installed":
                continue
            identifier = apt_selector(name, arch)
            validate(version, VERSION, "installed version")
            result[identifier] = package_record("apt", identifier, name, version, architecture=arch, dpkgState=state)
        return result

    def installed(self):
        return {identifier: {key: value for key, value in pkg.items() if key != "dpkgState"}
                for identifier, pkg in self.package_states().items() if pkg["dpkgState"] == "installed"}

    def marks(self, action):
        return set(self.runner.run(["/usr/bin/apt-mark", action]).stdout.split())

    @staticmethod
    def marked(pkg, marks):
        return pkg["nativeId"] in marks or pkg["name"] in marks

    def audit_sources(self, options):
        """APT can skip unreadable source files and still return success."""
        result = self.runner.run([
            "/usr/bin/apt-config", *options, "shell",
            "SOURCES", "Dir::Etc::sourcelist/f", "SOURCEPARTS", "Dir::Etc::sourceparts/d",
            "PARTS_ENABLED", "Dir::Etc::sourceparts",
            "TRUSTED", "Dir::Etc::trusted/f", "TRUSTEDPARTS", "Dir::Etc::trustedparts/d",
            "TRUSTEDPARTS_ENABLED", "Dir::Etc::trustedparts",
        ])
        locations = dict(token.split("=", 1) for token in shlex.split(result.stdout))

        def read(path, optional=False, text=False):
            if not path or path.rstrip("/") == "/dev/null":
                return ""
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise OSError("Not a regular file")
                    data = stream.read()
                    return data.decode("utf-8") if text else data
            except FileNotFoundError as error:
                if optional and not Path(path).is_symlink():
                    return ""
                raise BackendError(_("Cannot read APT source configuration or key material: ") + str(path), "capability-error") from error
            except (OSError, UnicodeError) as error:
                raise BackendError(_("Cannot read APT source configuration or key material: ") + str(path), "capability-error") from error

        def fragments(path, suffixes):
            if not path or path.rstrip("/") == "/dev/null":
                return []
            try:
                entries = sorted(Path(path).iterdir())
                return [entry for entry in entries if re.fullmatch(r"[A-Za-z0-9_.-]+", entry.name)
                        and entry.suffix in suffixes]
            except FileNotFoundError as error:
                if not Path(path).is_symlink():
                    return []
                raise BackendError(_("Cannot read the APT configuration directory: ") + str(path), "capability-error") from error
            except OSError as error:
                raise BackendError(_("Cannot read the APT configuration directory: ") + str(path), "capability-error") from error

        sources = [(locations.get("SOURCES", ""), True)]
        if locations.get("PARTS_ENABLED"):
            sources.extend((str(path), False) for path in fragments(locations.get("SOURCEPARTS"), (".list", ".sources")))
        default_keys = False
        for path, optional in sources:
            text = read(path, optional, text=True)
            if path.endswith(".sources"):
                records = control_records("\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")))
                signed_by = []
                for record in records:
                    fields = {key.lower(): value for key, value in record.items()}
                    if fields.get("enabled", "yes").lower() == "no":
                        continue
                    signed_by.append(fields.get("signed-by", "").strip())
            else:
                signed_by = []
                for line in text.splitlines():
                    line = line.split("#", 1)[0].strip()
                    if not re.match(r"^deb(?:-src)?\s", line):
                        continue
                    match = re.match(r"^deb(?:-src)?\s+\[([^]]*)\]", line)
                    values = shlex.split(match[1]) if match else []
                    signed_by.append(next((value.split("=", 1)[1] for value in values
                                           if value.lower().startswith("signed-by=")), ""))
            for value in signed_by:
                if value.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"):
                    continue  # Embedded keys need no external key file.
                keys = [entry for entry in re.split(r"[,\s]+", value) if entry.startswith("/")]
                for key in keys:
                    read(key)
                if not keys:
                    default_keys = True  # A fingerprint can select a default trusted key.
        if default_keys:
            read(locations.get("TRUSTED"), optional=True)
            if locations.get("TRUSTEDPARTS_ENABLED"):
                for key in fragments(locations.get("TRUSTEDPARTS"), (".gpg", ".asc")):
                    read(str(key))

    def audit_indexes(self, options, root):
        result = self.runner.run([
            "/usr/bin/apt-config", *options, "shell", "ROOT", "RootDir",
            "STATUS", "Dir::State::status/f", "LISTS", "Dir::State::lists/d",
            "ARCHIVES", "Dir::Cache::archives/d", "LOG", "Dir::Log/d",
            "HISTORY", "Dir::Log::History/f", "TERMINAL", "Dir::Log::Terminal/f",
            "PLANNER", "Dir::Log::Planner/f",
            "PKG", "Dir::Cache::pkgcache", "SRC", "Dir::Cache::srcpkgcache",
        ])
        values = dict(token.split("=", 1) for token in shlex.split(result.stdout))
        if values.get("ROOT") or values.get("PKG") or values.get("SRC"):
            raise BackendError(_("APT overrides the private checker paths."), "permissions")
        if Path(values.get("STATUS", "")).resolve() != Path("/var/lib/dpkg/status").resolve():
            raise BackendError(_("APT does not use the system dpkg database."), "permissions")
        for key in ("LISTS", "ARCHIVES", "LOG", "HISTORY", "TERMINAL", "PLANNER"):
            value = values.get(key)
            if not value or not Path(value).resolve().is_relative_to(root.resolve()):
                raise BackendError(_("An APT write path is outside the private cache: ") + key, "permissions")

    @contextlib.contextmanager
    def indexes(self):
        root = private_dir(self.paths.cache / "apt")
        with file_lock(root / "refresh.lock"):
            private_dir(root / "lists")
            private_dir(root / "lists" / "partial")
            private_dir(root / "archives")
            private_dir(root / "log")
            with tempfile.TemporaryDirectory(prefix="check-", dir=root) as temporary:
                config = Path(temporary) / "apt.conf"
                for path in (root,):
                    if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
                        raise BackendError(_("The APT cache path cannot be represented safely."), "invalid-input")
                config.write_text("\n".join([
                    'Dir::State::lists "' + str(root / "lists") + '";',
                    'Dir::Cache::pkgcache "";', 'Dir::Cache::srcpkgcache "";',
                    'Dir::Cache::archives "' + str(root / "archives") + '";',
                    'Dir::Log "' + str(root / "log") + '";',
                    '#clear APT::Update;', '#clear APT::Update::Pre-Invoke;', '#clear APT::Update::Post-Invoke;',
                    '#clear APT::Update::Post-Invoke-Success;',
                    '#clear APT::Update::Post-Invoke-Stats;',
                    'Acquire::Retries "1";', 'Acquire::http::Timeout "30";',
                    'Acquire::https::Timeout "30";',
                ]) + "\n")
                options = ["-c", str(config)]
                self.audit_indexes(options, root)
                yield options

    @contextlib.contextmanager
    def constraints(self, installed, excluded):
        """Prepend exact per-operation pins, while retaining all system pins."""
        excluded_pkgs = [pkg for pkg in installed.values()
                         if pkg["name"] in excluded or pkg["nativeId"] in excluded
                         or pkg["uid"] in excluded]
        if not excluded_pkgs:
            yield [], set()
            return
        root = private_dir(self.paths.cache / "apt")
        with tempfile.TemporaryDirectory(prefix="pins-", dir=root) as temporary:
            path = Path(temporary)
            text = ""
            for pkg in excluded_pkgs:
                identifier = apt_selector(pkg["name"], pkg["architecture"])
                version = validate(pkg["installedVersion"], VERSION, "excluded version")
                # Priority 1000 keeps the captured version without permitting a
                # downgrade if another manager changes the package before execution.
                text += (f"Package: {identifier}\nPin: version {version}\nPin-Priority: 1000\n\n"
                         f"Package: {identifier}\nPin: version *\nPin-Priority: -1\n\n")
            config = self.runner.run([
                "/usr/bin/apt-config", "shell", "PREF", "Dir::Etc::preferences/f",
                "PARTS", "Dir::Etc::preferencesparts/d",
            ]).stdout
            locations = dict(token.split("=", 1) for token in shlex.split(config))
            original = Path(locations.get("PREF", "/etc/apt/preferences"))
            if original.exists():
                text += original.read_text() + "\n\n"
            parts = Path(locations.get("PARTS", "/etc/apt/preferences.d"))
            if parts.exists():
                for fragment in sorted(parts.iterdir()):
                    if re.fullmatch(r"[A-Za-z0-9_.-]+", fragment.name) and (
                            "." not in fragment.name or fragment.name.endswith(".pref")) and fragment.is_file():
                        text += fragment.read_text() + "\n\n"
            pins = path / "preferences"
            pins.write_text(text)
            (path / "empty").mkdir()
            yield ["-o", "Dir::Etc::preferences=" + str(pins),
                   "-o", "Dir::Etc::preferencesparts=" + str(path / "empty")], {
                       pkg["nativeId"] for pkg in excluded_pkgs}

    def command(self, action="upgrade", identifiers=()):
        flags = ["--no-remove"] if self.mode == "safe" and action in (
            "upgrade", "upgrade-package", "install", "install-version", "local-install") else []
        if action == "upgrade":
            return flags + (["--with-new-pkgs", "upgrade"] if self.mode == "safe" else ["dist-upgrade"])
        if action == "upgrade-package":
            return flags + ["install", "--only-upgrade"] + list(identifiers)
        if action in ("install", "install-version", "local-install"):
            return flags + ["install"] + list(identifiers)
        if action in ("remove", "purge"):
            return [action] + list(identifiers)
        if action in ("autoremove", "clean", "autoclean"):
            return [action]
        raise BackendError(_("Unknown APT operation."), "invalid-input")

    def plan(self, installed, options=(), action="upgrade", identifiers=(), excluded=()):
        result = self.runner.run(["/usr/bin/apt-get", *options, "--simulate",
                                  *self.command(action, identifiers)])
        changes = parse_simulation(result.stdout, installed)
        if any(change["nativeId"] in excluded for change in changes):
            raise BackendError(_("APT cannot keep an excluded package unchanged."), "blocked")
        if self.mode == "safe" and action in ("upgrade", "upgrade-package", "install", "install-version", "local-install"):
            if any(change["action"] in ("Remv", "Purg") for change in changes):
                raise BackendError(_("Safe mode does not permit package removals."), "blocked")
        return result.stdout, changes

    def metadata(self, identifiers, options=()):
        if not identifiers:
            return []
        result = self.runner.run(["/usr/bin/apt-cache", *options, "--no-all-versions", "show", *identifiers])
        return control_records(result.stdout)

    def check(self):
        installed = self.installed()
        with self.indexes() as options:
            self.audit_sources(options)
            self.runner.run(["/usr/bin/apt-get", *options, "--error-on=any", "update"], timeout=900)
            self.audit_sources(options)
            with self.constraints(installed, self.paths.exclusions("apt")) as (pins, excluded):
                _, changes = self.plan(installed, options + pins, excluded=excluded)
            upgrades = [change for change in changes if change["action"] == "Inst"
                        and change["nativeId"] in installed
                        and change["candidateVersion"] != change["installedVersion"]]
            metadata = self.metadata([change["nativeId"] for change in upgrades], options)
            manual = self.marks("showmanual")
            items = []
            for change in upgrades:
                record = dict(installed[change["nativeId"]])
                record.update({key: change[key] for key in ("candidateVersion", "repository")})
                record["installReason"] = "explicit" if self.marked(record, manual) else "dependency"
                about = next((entry for entry in metadata if entry.get("Package") == record["name"]
                              and entry.get("Version") == record["candidateVersion"]
                              and entry.get("Architecture") in (record["architecture"], "all")), {})
                record["summary"] = package_description(about).split("\n")[0]
                record["homepage"] = about.get("Homepage", "")
                items.append(record)
            return items


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path="/run/snapd.socket", timeout=15):
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(self.path)
        except BaseException:
            self.sock.close()
            raise


def held(value):
    if not value:
        return False
    if value == "forever":
        return True
    if not isinstance(value, str):
        raise BackendError(_("The Snap hold has an unknown format."), "invalid-output")
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")) > datetime.datetime.now(datetime.timezone.utc)
    except (ValueError, TypeError):
        raise BackendError(_("The Snap hold has an unknown format."), "invalid-output")


class SnapBackend:
    def __init__(self, paths, runner=None, socket_path="/run/snapd.socket"):
        self.paths, self.runner, self.socket_path = paths, runner or Runner(paths), socket_path

    def api(self, path):
        connection = UnixHTTP(self.socket_path)
        try:
            connection.request("GET", path, headers={"X-Allow-Interaction": "false"})
            response = connection.getresponse()
            body = response.read(16 * 1024 * 1024 + 1)
            if len(body) > 16 * 1024 * 1024:
                raise BackendError(_("The snapd response is too large."), "invalid-output")
            data = json.loads(body)
            if not isinstance(data, dict) or data.get("status-code") != response.status:
                raise BackendError(_("The snapd response has an unknown format."), "invalid-output")
            if response.status != 200 or data.get("type") != "sync":
                detail = data.get("result", {})
                message = detail.get("message", "") if isinstance(detail, dict) else ""
                category = "auth-required" if response.status in (401, 403) else "service-unavailable"
                raise BackendError(redact(message) or _("snapd rejected the request."), category, response.status)
            return data.get("result")
        except (OSError, http.client.HTTPException) as error:
            raise BackendError(_("Cannot connect to snapd: ") + redact(error), "service-unavailable") from error
        except (ValueError, UnicodeError) as error:
            raise BackendError(_("snapd did not return valid JSON."), "invalid-output") from error
        finally:
            connection.close()

    def installed(self, all_revisions=False):
        data = self.api("/v2/snaps" + ("?select=all" if all_revisions else ""))
        if not isinstance(data, list) or any(not isinstance(entry, dict) for entry in data):
            raise BackendError(_("snapd did not return a package list."), "invalid-output")
        for entry in data:
            validate(entry.get("name"), SNAP_NAME, "snap name")
        return data

    def check(self):
        installed = {entry["name"]: entry for entry in self.installed()}
        candidates = self.api("/v2/find?select=refresh")
        if not isinstance(candidates, list):
            raise BackendError(_("snapd did not return refresh candidates."), "invalid-output")
        inhibited = self.api("/v2/snaps?select=refresh-inhibited") if candidates else []
        if not isinstance(inhibited, list) or any(not isinstance(entry, dict) for entry in inhibited):
            raise BackendError(_("snapd did not return refresh restrictions."), "invalid-output")
        blocked = {validate(entry.get("name"), SNAP_NAME, "inhibited snap name") for entry in inhibited}
        items = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise BackendError(_("Invalid Snap candidate."), "invalid-output")
            name = validate(candidate.get("name"), SNAP_NAME, "snap candidate name")
            local = installed.get(name)
            if local is None:
                raise BackendError(_("A Snap candidate has no matching installed instance."), "invalid-output")
            revision, next_revision = str(local.get("revision", "")), str(candidate.get("revision", ""))
            if not revision or not next_revision:
                raise BackendError(_("A Snap revision is missing."), "invalid-output")
            if revision == next_revision:
                continue
            items.append(package_record(
                "snap", name, name, local.get("version", ""), candidate.get("version", ""),
                installedRevision=revision, candidateRevision=next_revision,
                repository="Snap " + local.get("tracking-channel", local.get("channel", "")),
                summary=candidate.get("summary", ""), homepage="https://snapcraft.io/" + name.split("_")[0],
                state=("held" if held(local.get("hold")) or held(local.get("gating-hold"))
                       else "blocked" if name in blocked else "available"),
            ))
        return items


def check_backend(name, paths, runner=None, mode="auto"):
    timestamp = now()
    state_path = paths.cache / (name + "-result.json")
    try:
        previous = read_json(state_path, {}) or {}
    except BackendError as error:
        if error.category != "invalid-output":
            raise
        previous = {}
    if not isinstance(previous, dict) or previous and (
            previous.get("schemaVersion") != SCHEMA or previous.get("backend") != name
            or not isinstance(previous.get("items"), list)):
        previous = {}
    result = dict(schemaVersion=SCHEMA, backend=name, status="ok", checkedAt=timestamp,
                  synchronizedAt=None, metadataCurrent=False, items=[], errors=[])
    try:
        if lifecycle(paths, "state").get("status") == "running":
            raise BackendError(_("Another package operation is in progress."), "busy")
        backend = AptBackend(paths, runner, mode) if name == "apt" else SnapBackend(paths, runner)
        result["items"] = backend.check()
        if runner and getattr(runner, "token", "") and paths.canceled(runner.token):
            raise BackendError(_("The check was canceled."), "canceled", 130)
        result.update(synchronizedAt=now(), metadataCurrent=True)
        atomic_json(state_path, result)
    except (BackendError, OSError, ValueError) as error:
        category = getattr(error, "category", "command-error")
        result["status"] = {"busy": "busy", "canceled": "canceled",
                            "service-unavailable": "unavailable"}.get(category, "partial" if previous else "error")
        result["items"] = previous.get("items", [])
        result["synchronizedAt"] = previous.get("synchronizedAt")
        result["errors"] = [dict(category=category, code=getattr(error, "code", 1), message=redact(error))]
    return result


def capabilities(paths):
    names = ("pacman", "flatpak", "fwupdmgr", "paru", "pikaur", "yay", "jq", "tmux",
             "apt-get", "apt-cache", "apt-mark", "apt-config", "dpkg", "dpkg-query", "dpkg-deb", "snap")
    tools = {name: shutil.which(name) or "" for name in names}
    release = os_release()
    native_apt = release.get("ID") in ("ubuntu", "debian", "neon") or "debian" in release.get("ID_LIKE", "").split()
    apt = native_apt and Path("/var/lib/dpkg/status").is_file() and all(
        tools[name] for name in ("apt-get", "apt-cache", "apt-mark", "apt-config", "dpkg", "dpkg-query", "dpkg-deb"))
    tools.update(apt=bool(apt), snap=bool(tools["snap"]), python3="/usr/bin/python3", neon=release.get("ID") == "neon")
    terminals = [shutil.which(name) for name in TERMINALS if shutil.which(name)]
    if tools["flatpak"]:
        runner = Runner()
        try:
            result = runner.run(["flatpak", "list", "--app", "--columns=application"], check=False, timeout=10)
            deadline = time.monotonic() + 10
            for application in result.stdout.splitlines():
                if time.monotonic() > deadline:
                    break
                meta = runner.run(["flatpak", "info", "--show-metadata", application], check=False, timeout=5).stdout
                if "org.freedesktop.Flatpak=talk" in meta:
                    command = re.search(r"^command=(\S+)$", meta, re.M)
                    if command and command.group(1) in TERMINALS:
                        terminals.append("flatpak://" + application + "/" + command.group(1))
        except (BackendError, OSError):
            pass  # Optional terminal discovery cannot disable independent backends.
    return dict(tools=tools, terminals=terminals, release=release)


def confirm(message):
    try:
        answer = input(message + " [y/N]: ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        raise BackendError(_("The operation was canceled."), "canceled", 130)


def administrator(argv, settings, runner, *, capture=False, capture_stderr=False):
    prefix = shlex.split(settings.get("sudoBin", "sudo"))
    if not prefix:
        raise BackendError(_("No administrator command is configured."), "dependency-missing")
    command = prefix + list(argv)
    if settings.get("idleInhibit") == "true" and shutil.which("systemd-inhibit"):
        command = ["systemd-inhibit", "--what=idle:sleep:shutdown", "--who=Apdatifier",
                   "--why=" + _("Package operation in progress"), "--"] + command
    # Do not print captured configuration (for example Snap proxy credentials).
    if not capture:
        print(shlex.join(command), flush=True)
    options = {"capture_stderr": True} if capture_stderr else {}
    return runner.run(command, foreground=True, capture=capture, timeout=None, **options)


def assert_plan(changes, excluded, safe):
    if any(change["nativeId"] in excluded for change in changes):
        raise BackendError(_("The transaction changes an excluded package."), "blocked")
    if safe and any(change["action"] in ("Remv", "Purg") for change in changes):
        raise BackendError(_("Safe mode does not permit package removals."), "blocked")


def apt_foreground(paths, action, values, runner=None):
    runner = runner or Runner(paths)
    settings = paths.settings()
    backend = AptBackend(paths, runner, settings.get("aptUpgradeMode", "auto"))
    values = list(values)
    if action in ("upgrade-package", "install", "remove", "purge"):
        if not values:
            raise BackendError(_("Select at least one package."), "invalid-input")
        values = [apt_selector(*split_apt_id(value)) for value in values]
    elif action == "install-version":
        if len(values) != 2:
            raise BackendError(_("Select a package and a version."), "invalid-input")
        name, arch = split_apt_id(values[0])
        version = validate(values[1], VERSION, "version")
        runner.run(["/usr/bin/dpkg", "--validate-version", version])
        values = [apt_selector(name, arch, version)]
        confirm(_("An earlier version can need different dependencies. Continue?"))
    elif action == "local-install":
        if len(values) != 1:
            raise BackendError(_("Select one DEB file."), "invalid-input")
        archive = Path(values[0]).expanduser().resolve(strict=True)
        if not archive.is_file() or archive.suffix != ".deb":
            raise BackendError(_("Select a regular DEB file."), "invalid-input")
        records = control_records(runner.run(["/usr/bin/dpkg-deb", "--field", str(archive)]).stdout)
        if len(records) != 1:
            raise BackendError(_("The DEB metadata is invalid."), "invalid-output")
        about = records[0]
        apt_selector(about.get("Package", ""), about.get("Architecture", ""), about.get("Version", ""))
        print(_("Local package: ") + about["Package"] + " " + about["Version"])
        confirm(_("The local file can install an earlier version. Continue?"))
        values = [str(archive)]
    elif action not in ("upgrade", "autoremove", "clean", "autoclean"):
        raise BackendError(_("Unknown APT operation."), "invalid-input")

    if action in ("upgrade", "upgrade-package", "install", "install-version", "local-install"):
        administrator(["/usr/bin/apt-get", "--error-on=any", "update"], settings, runner)
    installed = backend.installed()
    inventory = dict(installed)
    states_read = False

    def current_states():
        nonlocal states_read
        if not states_read:
            inventory.update(backend.package_states())
            states_read = True
        return inventory

    if action == "purge" and any(value not in installed for value in values):
        current_states()
    selected = inventory if action == "purge" else installed
    if action in ("remove", "purge", "upgrade-package") and any(value not in selected for value in values):
        raise BackendError(_("A selected package is no longer installed."), "invalid-input")
    if action in ("install", "install-version"):
        records = backend.metadata(values)
        for selector in values:
            identifier, separator, version = selector.partition("=")
            name, arch = split_apt_id(identifier)
            if not any(record.get("Package") == name and record.get("Architecture") in (arch, "all")
                       and (not separator or record.get("Version") == version) for record in records):
                raise BackendError(_("No exact package matches the selected name, architecture, and version."), "invalid-input")
    excluded_rules = paths.exclusions("apt") if action in ("upgrade", "upgrade-package") else []
    with backend.constraints(installed, excluded_rules) as (pins, excluded):
        if action == "upgrade-package":
            holds = backend.marks("showhold")
            if any(backend.marked(installed[value], holds) for value in values):
                raise BackendError(_("A selected package has a native hold."), "blocked")
            # Explicit install requests can bypass native phasing. Require native
            # bulk eligibility before performing an individual upgrade.
            eligibility = administrator(
                ["/usr/bin/apt-get", *pins, "--simulate", *backend.command()], settings, runner,
                capture=True, capture_stderr=True,
            )
            if eligibility.stderr:
                print(_("APT messages") + "\n" + redact(eligibility.stderr, limit=None), file=sys.stderr)
            eligible = {entry["nativeId"] for entry in parse_simulation(eligibility.stdout, installed)
                        if entry["action"] == "Inst"}
            if not set(values) <= eligible:
                raise BackendError(_("APT did not select this update under the current policy."), "blocked")
        args = backend.command(action, values)
        if action not in ("clean", "autoclean"):
            preview_result = administrator(
                ["/usr/bin/apt-get", *pins, *APT_PREVIEW_OPTIONS, "--simulate", *args], settings, runner,
                capture=True, capture_stderr=True,
            )
            preview = preview_result.stdout
            inst_names = set(re.findall(r"^Inst (\S+)", preview, re.M))
            if any(kind == "Purg" or name not in inst_names
                   for kind, name in re.findall(r"^(Purg|Conf) (\S+)", preview, re.M)):
                current_states()
            changes = parse_simulation(preview, installed, configure=True, package_data=inventory)
            assert_plan(changes, excluded, "--no-remove" in args)
            groups = apt_operation_groups(changes, runner)
            info = apt_information(preview)
            info["diagnostics"].extend(preview_result.stderr.splitlines())
            if info["summary"] and (info["operation_count"] != sum(len(groups[key]) for key in
                    ("install", "upgrade", "downgrade", "reinstall")) or info["removal_count"] != len(groups["remove"])):
                raise BackendError(_("The APT transaction contains an unknown record."), "invalid-output")
            if info["autoremove"] and apt_candidate_rows(info["autoremove"], inventory) is None:
                try:
                    current_states()
                except BackendError as error:
                    if error.category == "canceled":
                        raise
                    info["candidate_error"] = True
                    info["diagnostics"].append(str(error))
            zero_verified = (info["autoremove"] is None and not info["candidate_error"] and info["summary"]
                             and action != "autoremove" and apt_preview_policy(installed, pins, settings, runner))
            print_apt_summary(groups, info, inventory, zero_verified=zero_verified, autoremove=action == "autoremove")
            decreases = [change["nativeId"] for change in groups["downgrade"]]
            if decreases:
                print(_("Packages that will receive an earlier version: ") + ", ".join(decreases))
                confirm(_("The plan installs earlier package versions. Allow these version decreases?"))
        else:
            print(_("This operation removes downloaded package archives."))
        confirm(_("Run this APT operation?"))
        administrator(["/usr/bin/apt-get", *pins, *args], settings, runner)
    if settings.get("rebootSystem") == "true" and Path("/run/reboot-required").exists():
        print(_("The system requests a restart."))
        packages = Path("/run/reboot-required.pkgs")
        if packages.exists():
            print(packages.read_text())
        try:
            confirm(_("Restart the system now?"))
        except BackendError as error:
            if error.category != "canceled":
                raise
        else:
            runner.run(["qdbus6", "org.kde.Shutdown", "/Shutdown", "logoutAndReboot"],
                       foreground=True, capture=False, timeout=None)


def snap_global_hold(backend, settings, runner):
    try:
        config = backend.api("/v2/snaps/system/conf")
    except BackendError as error:
        if error.category != "auth-required":
            raise
        result = administrator(["/usr/bin/snap", "get", "-d", "system"], settings, runner, capture=True)
        try:
            config = json.loads(result.stdout)
        except ValueError as failure:
            raise BackendError(_("Cannot determine the global Snap hold."), "invalid-output") from failure
    if not isinstance(config, dict):
        raise BackendError(_("Cannot determine the global Snap hold."), "invalid-output")
    refresh = config.get("refresh", {})
    if not isinstance(refresh, dict):
        raise BackendError(_("The Snap refresh configuration is invalid."), "invalid-output")
    return held(config.get("refresh.hold", refresh.get("hold")))


def snap_foreground(paths, action, values, runner=None, transaction=""):
    runner = runner or Runner(paths)
    settings = paths.settings()
    backend = SnapBackend(paths, runner)
    values = [validate(value, SNAP_NAME, "snap name") for value in values] if action != "remove-revision" else list(values)
    if action in ("refresh", "install", "remove", "purge", "revert") and not values and action != "refresh":
        raise BackendError(_("Select at least one package."), "invalid-input")
    if action in ("install", "revert") and len(values) > 1:
        for name in values:
            snap_foreground(paths, action, [name], runner, transaction)
            if transaction:
                lifecycle(paths, "stage", transaction, "snap", 0)
        return
    args = []
    if action == "refresh":
        installed = {entry["name"]: entry for entry in backend.installed()}
        if any(name not in installed for name in values):
            raise BackendError(_("The selected Snap is no longer installed."), "invalid-input")
        if not values:
            candidates = backend.check()
            ready = [pkg for pkg in candidates if pkg["state"] == "available"]
            if not ready:
                print(_("There are no selected Snap updates."))
                return
        if snap_global_hold(backend, settings, runner):
            confirm(_("A manual refresh overrides the automatic-refresh hold. Override it now?"))
        if values:
            if any(held(installed[name].get("hold")) or held(installed[name].get("gating-hold"))
                   for name in values):
                confirm(_("A selected Snap has a native hold. Override it for this operation?"))
        else:
            excluded = set(paths.exclusions("snap"))
            if excluded:
                values = [pkg["nativeId"] for pkg in ready
                          if pkg["nativeId"] not in excluded and pkg["uid"] not in excluded]
                if not values:
                    print(_("There are no selected Snap updates."))
                    return
        if any(name in paths.exclusions("snap") or "snap:" + name in paths.exclusions("snap") for name in values):
            raise BackendError(_("A selected Snap is excluded by an operation rule."), "blocked")
        args = ["refresh", *values]
    elif action == "install":
        args = ["install", *values]
        classic = False
        for name in values:
            data = backend.api("/v2/find?name=" + urllib.parse.quote(name))
            if not isinstance(data, list) or len(data) != 1:
                raise BackendError(_("Cannot determine the Snap confinement mode."), "invalid-output")
            if data[0].get("confinement") == "classic":
                classic = True
        if classic:
            confirm(_("Classic confinement gives the application access outside the Snap sandbox. Allow it?"))
            args.append("--classic")
    elif action in ("remove", "purge"):
        args = ["remove", *values] + (["--purge"] if action == "purge" else [])
        if action == "purge":
            confirm(_("Remove these Snaps without a data snapshot?"))
    elif action == "revert":
        print(_("Revision return does not restore all shared application data."))
        args = ["revert", *values]
    elif action == "remove-revision":
        if len(values) != 2:
            raise BackendError(_("Select one inactive revision."), "invalid-input")
        name = validate(values[0], SNAP_NAME, "snap name")
        revision = validate(values[1], re.compile(r"(?:[1-9][0-9]*|x[1-9][0-9]*)"), "revision")
        match = [pkg for pkg in backend.installed(True)
                 if pkg["name"] == name and str(pkg.get("revision")) == revision]
        if len(match) != 1 or match[0].get("status") != "installed":
            raise BackendError(_("The selected revision is active or unavailable."), "blocked")
        confirm(_("This removes a revision that could be used for revision return. Continue?"))
        args = ["remove", name, "--revision=" + revision]
    else:
        raise BackendError(_("Unknown Snap operation."), "invalid-input")
    print(shlex.join(["snap", *args]))
    confirm(_("Run this Snap operation?"))
    result = administrator(["/usr/bin/snap", *args, "--no-wait"], settings, runner, capture=True)
    change_id = result.stdout.strip()
    if not re.fullmatch(r"[1-9][0-9]*", change_id):
        raise BackendError(_("The Snap transaction result is unknown. Inspect snap changes."), "unknown")
    if transaction:
        lifecycle(paths, "change", transaction, stage="snap", change=change_id)
    # snap watch waits for daemon completion, rather than just request acceptance.
    administrator(["/usr/bin/snap", "watch", change_id], settings, runner)
    try:
        change = backend.api("/v2/changes/" + change_id)
    except BackendError:
        change = None  # A successful native watch is completion evidence.
    if change and (not change.get("ready") or change.get("status") != "Done"):
        raise BackendError(_("The Snap transaction did not complete successfully."), "unknown")


def installed_records(paths):
    settings, runner = paths.settings(), Runner(paths)
    items, errors = [], []
    for source, enabled in (("apt", settings.get("apt") == "true"),
                            ("snap", settings.get("snap") == "true"),
                            ("pacman", settings.get("arch") == "true" or settings.get("aur") == "true"),
                            ("flatpak", settings.get("flatpak") == "true"),
                            ("widgets", settings.get("widgets") == "true"),
                            ("fwupd", settings.get("fwupd") == "true")):
        if not enabled:
            continue
        try:
            if source == "apt":
                items.extend(AptBackend(paths, runner).installed().values())
            elif source == "snap":
                for pkg in SnapBackend(paths, runner).installed():
                    items.append(package_record("snap", pkg["name"], pkg["name"], pkg.get("version", ""),
                                                installedRevision=str(pkg.get("revision", ""))))
            elif source == "pacman":
                for line in runner.run(["pacman", "-Q"]).stdout.splitlines():
                    name, version = line.split(" ", 1)
                    items.append(package_record("pacman", name, name, version))
            elif source == "flatpak":
                text = runner.run(["flatpak", "list", "--app",
                                   "--columns=application,branch,arch,installation,version,active"]).stdout
                for line in text.splitlines():
                    application, branch, arch, installation, version, active = line.split("\t")
                    identifier = installation + ":" + application + "/" + arch + "/" + branch
                    items.append(package_record("flatpak", identifier, application, version,
                                                installedRevision=active, branch=branch,
                                                architecture=arch, installation=installation))
            elif source == "widgets":
                text = runner.run([str(SCRIPT_DIR / "sh/widgets"), "list"]).stdout
                for pkg in json.loads("[" + text.strip().rstrip(",") + "]"):
                    identifier = str(pkg.get("nativeId") or pkg.get("CN") or pkg["NM"])
                    items.append(package_record("widgets", identifier, pkg["NM"], pkg.get("VO", "")))
            else:
                data = json.loads(runner.run(["fwupdmgr", "get-devices", "--json"]).stdout)
                for pkg in data.get("Devices", []):
                    identifier = pkg.get("DeviceId") or (pkg.get("Vendor", "") + "-" + pkg.get("Name", ""))
                    name = pkg.get("Vendor", "") + "-" + pkg.get("Name", "")
                    items.append(package_record("fwupd", identifier, name, pkg.get("Version", "")))
        except (BackendError, OSError, ValueError) as error:
            errors.append(dict(backend=source, message=redact(error)))
    return dict(items=items, errors=errors)


def process_identity(pid):
    if not isinstance(pid, int) or pid <= 0:
        return None
    try:
        process = Path("/proc") / str(pid)
        if process.stat().st_uid != os.getuid():
            return None
        return (process / "stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def lifecycle(paths, action, transaction="", stage="", code=0, pid=0, change=""):
    state_file = paths.cache / "upgrade-state.json"
    with file_lock(paths.cache / "upgrade-state.lock"):
        state = read_json(state_file, {}) or {}
        if not isinstance(state, dict):
            raise BackendError(_("The transaction state is invalid."), "invalid-output")
        if action == "state":
            if state.get("status") == "running":
                identity = process_identity(state.get("pid"))
                if not identity or identity != state.get("pidStart"):
                    state["status"] = "unknown"
                    state["message"] = _("The terminal process ended without a transaction result.")
                    atomic_json(state_file, state)
            return state
        validate(transaction, TOKEN, "transaction identifier")
        if action == "start":
            if state.get("status") == "running":
                identity = process_identity(state.get("pid"))
                if identity and identity == state.get("pidStart"):
                    raise BackendError(_("Another upgrade is in progress."), "busy")
            state = dict(id=transaction, pid=pid, pidStart=process_identity(pid),
                         status="running", startedAt=now(), stages=[])
        elif state.get("id") != transaction:
            raise BackendError(_("The transaction identifier does not match."), "invalid-input")
        elif action == "stage":
            state["stages"].append(dict(backend=stage, code=code,
                                        status="ok" if code == 0 else "canceled" if code == 130 else "error"))
        elif action == "change":
            state["snapChange"] = change
        elif action == "finish":
            codes = [entry["code"] for entry in state["stages"]]
            state["status"] = ("canceled" if 130 in codes else "partial" if any(codes) and 0 in codes
                               else "error" if any(codes) else "ok")
            state["finishedAt"] = now()
        atomic_json(state_file, state)
        return state


def choose(items, label=lambda item: str(item), page_size=20, multiple=True):
    """Numbered, paginated selection; indexes always refer to this exact list."""
    page = 0
    if not items:
        print(_("No matching packages."))
        return []
    while True:
        start = page * page_size
        for index, item in enumerate(items[start:start + page_size], start + 1):
            print(f"{index}. {label(item)}")
        try:
            answer = input(
                _("Numbers separated by spaces; n: next; p: previous; q: cancel: ") if multiple else
                _("Number; n: next; p: previous; q: cancel: ")).strip()
        except EOFError:
            return []
        if answer == "q" or not answer:
            return []
        if answer == "n":
            page = min(page + 1, (len(items) - 1) // page_size)
        elif answer == "p":
            page = max(page - 1, 0)
        else:
            try:
                indexes = list(dict.fromkeys(int(number) - 1 for number in answer.split()))
                if not indexes or (not multiple and len(indexes) != 1) or any(index < 0 or index >= len(items) for index in indexes):
                    raise ValueError
                return [items[index] for index in indexes]
            except ValueError:
                print(_("Select numbers from the displayed result set."))


def management(paths, transaction=""):
    runner = Runner(paths)
    available = capabilities(paths)["tools"]
    labels = {
        "search": _("Search available packages"), "installed": _("Manage installed packages"),
        "manual": _("Manually installed packages"), "automatic": _("Automatically installed packages"),
        "orphans": _("Unused dependencies"), "local-install": _("Install a local DEB file"),
        "earlier-version": _("Select an earlier package version"),
        "cached-versions": _("Install a cached package version"),
        "clean": _("Remove all downloaded archives"), "autoclean": _("Remove obsolete downloaded archives"),
        "history": _("Recent operations"), "upgrade": _("Upgrade packages"),
        "refresh": _("Refresh packages"), "revert": _("Return to an earlier revision"),
        "inactive-revisions": _("Manage inactive revisions"), "remove": _("Remove selected packages"),
        "purge": _("Remove selected packages and saved configuration"),
        "upgrade-package": _("Upgrade selected packages"),
    }
    source_labels = {"apt": "APT", "snap": "Snap", "pacman": _("Arch packages"), "flatpak": "Flatpak"}
    while True:
        sources = [source for source in ("apt", "snap", "pacman", "flatpak") if available.get(source)]
        selected = choose(sources, source_labels.__getitem__, multiple=False)
        if not selected:
            return
        source = selected[0]
        def action_label(action):
            if source == "snap" and action == "purge":
                return _("Remove without a data snapshot")
            return labels[action]
        if source in ("pacman", "flatpak"):
            runner.run([str(SCRIPT_DIR / "sh/management"), "--legacy", source],
                       foreground=True, capture=False, timeout=None)
            continue
        actions = (["search", "installed", "manual", "automatic", "orphans", "local-install", "earlier-version", "cached-versions",
                    "clean", "autoclean", "history", "upgrade"] if source == "apt" else
                   ["search", "installed", "revert", "inactive-revisions", "history", "refresh"])
        selected = choose(actions, action_label, multiple=False)
        if not selected:
            continue
        action, values = selected[0], []
        try:
            if source == "apt":
                backend = AptBackend(paths, runner, paths.settings().get("aptUpgradeMode", "auto"))
                if action == "search":
                    query = input(_("Search: ")).strip()
                    if not query:
                        continue
                    result = runner.run(["/usr/bin/apt-cache", "search", "--", query]).stdout
                    selected = choose(result.splitlines())
                    for line in selected:
                        name = validate(line.split(" ", 1)[0], PACKAGE, "package name")
                        records = backend.metadata([name])
                        if not records:
                            raise BackendError(_("Package metadata is unavailable."), "invalid-output")
                        about = records[0]
                        print(package_description(about))
                        values.append(apt_selector(name, about.get("Architecture", "")))
                    action = "install"
                elif action in ("installed", "manual", "automatic", "earlier-version"):
                    packages = list(backend.installed().values())
                    if action in ("manual", "automatic"):
                        marks = backend.marks("showmanual" if action == "manual" else "showauto")
                        packages = [pkg for pkg in packages if backend.marked(pkg, marks)]
                    query = input(_("Filter by name; empty for all: ")).strip().lower()
                    selected = choose([pkg for pkg in packages if query in pkg["name"]],
                                      lambda pkg: pkg["nativeId"] + " " + pkg["installedVersion"],
                                      multiple=action != "earlier-version")
                    values = [pkg["nativeId"] for pkg in selected]
                    for pkg in selected:
                        print(runner.run(["/usr/bin/apt-cache", "show", pkg["nativeId"]]).stdout)
                    if action == "earlier-version" and len(values) == 1:
                        print(runner.run(["/usr/bin/apt-cache", "policy", values[0]]).stdout)
                        values.append(input(_("Exact version: ")).strip())
                        action = "install-version"
                    else:
                        choice = choose(["remove", "purge", "upgrade-package"], action_label, multiple=False) if values else []
                        if not choice:
                            continue
                        action = choice[0]
                elif action == "orphans":
                    action = "autoremove"
                elif action == "local-install":
                    values = [input(_("Path to a DEB file: ")).strip()]
                elif action == "cached-versions":
                    archives = sorted(Path("/var/cache/apt/archives").glob("*.deb"))
                    selected = choose(archives, lambda path: path.name, multiple=False)
                    if not selected:
                        continue
                    values, action = [str(selected[0])], "local-install"
                elif action == "history":
                    for path in sorted(Path("/var/log/apt").glob("history.log*"), reverse=True):
                        opener = gzip.open if path.suffix == ".gz" else open
                        with opener(path, "rt", errors="replace") as stream:
                            print(stream.read()[-30000:])
                    continue
                if not values and action in ("install", "remove", "purge", "upgrade-package", "install-version"):
                    continue
                apt_foreground(paths, action, values, runner)
                if transaction:
                    lifecycle(paths, "stage", transaction, "apt", 0)
            else:
                backend = SnapBackend(paths, runner)
                if action == "search":
                    query = input(_("Search: ")).strip()
                    if not query:
                        continue
                    data = backend.api("/v2/find?q=" + urllib.parse.quote(query))
                    selected = choose(data, lambda pkg: pkg["name"] + " - " + pkg.get("summary", ""))
                    values, action = [pkg["name"] for pkg in selected], "install"
                elif action in ("installed", "revert"):
                    query = input(_("Filter by name; empty for all: ")).strip().lower()
                    packages = [pkg for pkg in backend.installed() if query in pkg["name"]]
                    selected = choose(packages, lambda pkg: pkg["name"] + " " + pkg.get("version", ""))
                    values = [pkg["name"] for pkg in selected]
                    for pkg in selected:
                        print(pkg.get("description", pkg.get("summary", "")))
                    if action == "installed":
                        choice = choose(["refresh", "remove", "purge"], action_label, multiple=False) if values else []
                        if not choice:
                            continue
                        action = choice[0]
                elif action == "inactive-revisions":
                    revisions = [pkg for pkg in backend.installed(True) if pkg.get("status") == "installed"]
                    selected = choose(revisions, lambda pkg: pkg["name"] + " " + str(pkg.get("revision", "")))
                    for pkg in selected:
                        snap_foreground(paths, "remove-revision", [pkg["name"], str(pkg["revision"])], runner,
                                        transaction=transaction)
                        if transaction:
                            lifecycle(paths, "stage", transaction, "snap", 0)
                    continue
                elif action == "history":
                    runner.run(["/usr/bin/snap", "changes"], foreground=True, capture=False, timeout=None)
                    change = input(_("Change ID for tasks; empty to return: ")).strip()
                    if change:
                        validate(change, re.compile(r"[1-9][0-9]*"), "change identifier")
                        runner.run(["/usr/bin/snap", "tasks", change], foreground=True, capture=False, timeout=None)
                    continue
                if not values and action != "refresh":
                    continue
                snap_foreground(paths, action, values, runner, transaction=transaction)
                if transaction:
                    lifecycle(paths, "stage", transaction, "snap", 0)
        except (BackendError, OSError, ValueError) as error:
            if transaction:
                lifecycle(paths, "stage", transaction, source, getattr(error, "code", 1))
            print(redact(error), file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("installed")
    manage = sub.add_parser("management")
    manage.add_argument("--transaction", default="")
    sub.add_parser("write-cache")
    chunk = sub.add_parser("cache-chunk")
    chunk.add_argument("token")
    chunk.add_argument("index", type=int)
    chunk.add_argument("total", type=int)
    chunk.add_argument("data")
    cancel = sub.add_parser("cancel")
    cancel.add_argument("token")
    check = sub.add_parser("check")
    check.add_argument("backend", choices=("apt", "snap"))
    check.add_argument("--mode", default="auto")
    check.add_argument("--request-id", default="")
    foreground = sub.add_parser("foreground")
    foreground.add_argument("backend", choices=("apt", "snap"))
    foreground.add_argument("action")
    foreground.add_argument("values", nargs="*")
    foreground.add_argument("--transaction", default="")
    state = sub.add_parser("lifecycle")
    state.add_argument("action", choices=("start", "stage", "change", "finish", "state"))
    state.add_argument("--id", default="")
    state.add_argument("--stage", default="")
    state.add_argument("--code", type=int, default=0)
    state.add_argument("--pid", type=int, default=0)
    args = parser.parse_args(argv)
    paths = Paths()
    if args.command == "check":
        def stop_check(signum, frame):
            raise BackendError(_("The check was canceled."), "canceled", 130)
        signal.signal(signal.SIGTERM, stop_check)
    try:
        if args.command == "capabilities":
            result = capabilities(paths)
        elif args.command == "installed":
            result = installed_records(paths)
        elif args.command == "write-cache":
            result = json.load(sys.stdin)
            if not isinstance(result, list):
                raise BackendError(_("The cache must contain a list."), "invalid-input")
            atomic_json(paths.cache / "updates.json", result)
            result = dict(status="ok")
        elif args.command == "cache-chunk":
            result = cache_chunk(paths, args.token, args.index, args.total, args.data)
        elif args.command == "cancel":
            validate(args.token, TOKEN, "request identifier")
            private_dir(paths.cache)
            atomic_json(paths.cache / ("cancel-" + args.token), dict(canceledAt=now()))
            result = dict(status="ok")
        elif args.command == "check":
            if args.request_id:
                validate(args.request_id, TOKEN, "request identifier")
            result = check_backend(args.backend, paths, Runner(paths, args.request_id), args.mode)
        elif args.command == "foreground":
            if args.backend == "apt":
                apt_foreground(paths, args.action, args.values)
            else:
                snap_foreground(paths, args.action, args.values, transaction=args.transaction)
            return 0
        elif args.command == "management":
            transaction = args.transaction or str(uuid.uuid4())
            lifecycle(paths, "start", transaction, pid=os.getpid())
            try:
                management(paths, transaction)
            except BaseException as error:
                lifecycle(paths, "stage", transaction, "management",
                          130 if isinstance(error, (KeyboardInterrupt, EOFError)) else getattr(error, "code", 1))
                raise
            finally:
                lifecycle(paths, "finish", transaction)
            return 0
        else:
            result = lifecycle(paths, args.action, args.id, args.stage, args.code, args.pid)
        print(json.dumps(result, ensure_ascii=True))
        return 1 if args.command == "check" and result.get("status") != "ok" else 0
    except (BackendError, OSError, ValueError) as error:
        if args.command in ("foreground", "management"):
            print(redact(error), file=sys.stderr)
        else:
            print(json.dumps(dict(schemaVersion=SCHEMA, status="error", errors=[dict(
                category=getattr(error, "category", "command-error"),
                code=getattr(error, "code", 1), message=redact(error))])))
        return getattr(error, "code", 1) if 0 < getattr(error, "code", 1) < 256 else 1
    except (KeyboardInterrupt, EOFError):
        print(_("Interrupted. Inspect the native transaction before retrying."), file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
