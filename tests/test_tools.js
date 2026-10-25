// Development tests use the Node.js already available on GitHub Actions.
// Node.js is not an application dependency.
const assert = require("node:assert/strict");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");
const { test } = require("node:test");
const { context, plain } = require("./helpers/qml_context.js");

test("shell quoting preserves data, including substitutions and quotes", () => {
    const c = context();
    const values = ["normal", "a b", "a'b", "$(printf injected)", "; printf injected", "line\nbreak"];
    for (const value of values) {
        c.value = value;
        const command = vm.runInContext("shellQuote(value)", c);
        const result = execFileSync("/bin/bash", ["-c", "printf '%s' " + command], { encoding: "utf8" });
        assert.equal(result, value);
    }
});

test("saved configuration preserves command text without early expansion", () => {
    const c = context();
    const value = 'printf "%s" "$PATH" $(printf injected) \\backslash `printf more`';
    c.cfg = { preExecDefault: "", preExec: value };
    let command;
    c.execute = text => { command = text; };
    c.saveConfig();
    const payloadCommand = command.replace(/ > "[^"]*"$/, "");
    const config = execFileSync("/bin/bash", [
        "-c", "set -- " + payloadCommand + "; printf '%s' \"$3\"",
    ], { encoding: "utf8" });
    const decoded = execFileSync("/bin/bash", [
        "-c", config + "\nprintf '%s' \"$preExec\"",
    ], { encoding: "utf8" });
    assert.equal(decoded, value);
});

test("a terminal starts only after current settings reach the configuration file", () => {
    const c = context();
    c.runLater = () => {};
    const calls = [];
    c.execute = (command, callback) => calls.push({ command, callback });
    vm.runInContext('runInTerminal("upgrade", "apt")', c);
    assert.equal(calls.length, 1);
    assert.ok(calls[0].command.includes("config.conf"));
    calls[0].callback(calls[0].command, "", "", 0);
    assert.equal(calls.length, 2);
    assert.ok(calls[1].command.startsWith("kstart -- "));
    assert.ok(calls[1].command.includes("--transaction"));
});

test("failed configuration persistence prevents a terminal operation", () => {
    const c = context();
    c.runLater = () => {};
    const calls = [];
    c.execute = (command, callback) => calls.push({ command, callback });
    vm.runInContext('runInTerminal("upgrade", "apt")', c);
    calls[0].callback(calls[0].command, "", "permission denied", 13);
    assert.equal(calls.length, 1);
    assert.equal(c.sts.upgrading, false);
});

test("cache normalization keeps same-name packages in distinct backends", () => {
    const c = context();
    const records = c.keys([
        { NM: "example", RE: "Ubuntu", backend: "apt", nativeId: "example:amd64" },
        { NM: "example", RE: "Snap", backend: "snap", nativeId: "example" },
        { NM: "example", RE: "extra" },
        { NM: "example", RE: "flathub", ID: "org.example.App", uid: "flatpak:user:org.example.App/x86_64/stable" },
        { NM: "example", RE: "flathub", ID: "org.example.App", uid: "flatpak:system:org.example.App/x86_64/stable" },
    ]);
    assert.equal(new Set(records.map(item => item.uid)).size, 5);
    assert.equal(records[0].uid, "apt:example:amd64");
    assert.equal(records[1].uid, "snap:example");
    assert.equal(records[2].backend, "pacman");
    assert.equal(records[0].state, "available");
});

test("scoped display rules do not hide the same name from another backend", () => {
    const c = context();
    c.cfg.rules = JSON.stringify([{ backend: "apt", type: "name", value: "example:amd64", excluded: true }]);
    const items = c.keys([
        { NM: "example", backend: "apt", nativeId: "example:amd64" },
        { NM: "example", backend: "snap", nativeId: "example" },
    ]);
    const result = c.applyRules(items);
    assert.equal(result.length, 1);
    assert.equal(result[0].backend, "snap");
});

test("legacy ignore rules remain pacman-only", () => {
    const c = context();
    c.cfg.rules = JSON.stringify([
        { type: "name", value: "old", ignore: true },
        { backend: "apt", type: "name", value: "example", ignore: true },
        { backend: "snap", type: "name", value: "another", ignore: true },
    ]);
    assert.deepEqual(plain(c.buildIgnoreArgs()), ["--ignore", "old"]);
});

test("a new Snap revision can notify even when version text does not change", () => {
    const c = context();
    c.cache = c.keys([{
        NM: "example", backend: "snap", nativeId: "example", VO: "1", VN: "1", candidateRevision: "10",
    }]);
    const next = c.keys([{
        NM: "example", backend: "snap", nativeId: "example", VO: "1", VN: "1", candidateRevision: "11",
    }]);
    c.finalize(next);
    assert.equal(c.notify.messages.length, 1);
    assert.equal(c.notify.messages[0][0], "updates");
});

test("Flatpak notifies for a new native commit with unchanged version text", () => {
    const c = context();
    const item = { NM: "example", backend: "flatpak", nativeId: "user:org.example.App/x86_64/stable",
                   VO: "1", VN: "latest commit", CM: "old-candidate" };
    c.cache = c.keys([Object.assign({}, item)]);
    c.finalize(c.keys([Object.assign({}, item, { CM: "new-candidate" })]));
    assert.equal(c.notify.messages.length, 1);
    c.finalize(c.keys([Object.assign({}, item, { CM: "new-candidate" })]));
    assert.equal(c.notify.messages.length, 1);
});

test("Flatpak commit changes respect notification settings and old-result state", () => {
    for (const settings of [{ notifyEveryBump: false }, { stale: true }]) {
        const c = context();
        const item = { NM: "example", backend: "flatpak", VO: "1", VN: "latest commit", CM: "old" };
        c.cache = c.keys([Object.assign({}, item)]);
        if (settings.notifyEveryBump === false) c.cfg.notifyEveryBump = false;
        c.finalize(c.keys([Object.assign({}, item, { CM: "new", stale: Boolean(settings.stale) })]));
        assert.equal(c.notify.messages.length, 0);
    }
});

test("Flatpak fingerprints use the native commit and retain the legacy version fallback", () => {
    const c = context();
    assert.equal(c.updateFingerprint({ backend: "flatpak", CM: "commit", VN: "latest commit" }),
                 c.updateFingerprint({ backend: "flatpak", CM: "commit", VN: "translated label" }));
    assert.notEqual(c.updateFingerprint({ backend: "flatpak", VN: "1" }),
                    c.updateFingerprint({ backend: "flatpak", VN: "2" }));
});

test("firmware failures keep only firmware's previous result and mark it old", () => {
    for (const type of ["fwupdmgr", "fwupd"]) {
        const c = context();
        c.cache = c.keys([
            { NM: "device", backend: "fwupd", uid: "fwupd:device-id", VO: "1", VN: "2", synchronizedAt: 123 },
            { NM: "example", backend: "snap", VO: "1", VN: "2" },
        ]);
        c.sts.errors = [{ type, code: 1, message: "refresh failed" }];
        c.finalize([]);
        assert.equal(c.cache.length, 1);
        assert.equal(c.cache[0].uid, "fwupd:device-id");
        assert.equal(c.cache[0].stale, true);
        assert.equal(c.cache[0].synchronizedAt, 123);
        assert.equal(c.notify.messages.length, 0);
    }
});

test("retained old data does not generate a new update notification", () => {
    const c = context();
    c.finalize(c.keys([{
        NM: "example", backend: "apt", nativeId: "example:amd64", VO: "1", VN: "2", stale: true,
    }]));
    assert.equal(c.notify.messages.length, 0);
});

test("a failed APT source cannot restore unrelated Snap data as repository data", () => {
    const c = context();
    c.cache = c.keys([
        { NM: "example", backend: "apt", nativeId: "example:amd64", VO: "1", VN: "2" },
        { NM: "example", backend: "snap", nativeId: "example", VO: "1", VN: "2" },
    ]);
    c.sts.errors = [{ type: "apt", code: 100, message: "refresh failed" }];
    c.finalize([]);
    assert.equal(c.cache.length, 1);
    assert.equal(c.cache[0].backend, "apt");
    assert.equal(c.cache[0].stale, true);
});

test("held entries stay in the list without increasing the actionable update count", () => {
    const c = context();
    c.refreshListModel(c.keys([
        { NM: "held", backend: "snap", state: "held" },
        { NM: "available", backend: "apt", state: "available" },
    ]));
    assert.equal(c.sts.count, 1);
});

test("Flatpak candidates match their installation, architecture, branch, and origin", async () => {
    const c = context();
    const commands = [];
    c.execute = (command, callback) => {
        commands.push(command);
        const installed = ["user", "system"].map(scope =>
            ["org.example.App", "1", "old-commit", "stable", "x86_64", scope, "flathub"].join("\t")).join("\n");
        const candidate = ["Example", "Description", "org.example.App", "2", "stable", "x86_64", "flathub",
                           "app/org.example.App/x86_64/stable", "next-commit", "", "1 MB", "1 MB"].join("\t");
        callback(command, command.includes("flatpak list") ? installed : command.includes("--user") ? candidate : "", "", 0);
    };
    const result = await c.makeFlatpakList();
    assert.equal(result.length, 1);
    assert.equal(result[0].uid, "flatpak:user:org.example.App/x86_64/stable");
    assert.equal(commands.length, 3);
    assert.ok(commands[2].includes("--system"));
});

test("single Flatpak updates pass the full native reference and installation", () => {
    const c = context();
    c.runLater = () => {};
    const calls = [];
    c.execute = (command, callback) => calls.push({ command, callback });
    c.upgradePackage({ backend: "flatpak", ID: "org.example.App", NM: "Example", BR: "stable",
                       architecture: "x86_64", installation: "user" });
    calls[0].callback(calls[0].command, "", "", 0);
    assert.ok(calls[1].command.includes("app/org.example.App/x86_64/stable"));
    assert.ok(calls[1].command.includes("user"));
});

test("failed legacy sources retain their data with an old-result marker", () => {
    const c = context();
    c.cache = c.keys([{ NM: "example", backend: "flatpak", ID: "org.example.App", VO: "1", VN: "2" }]);
    c.sts.errors = [{ type: "flatpak", code: 1, message: "offline" }];
    c.finalize([]);
    assert.equal(c.cache.length, 1);
    assert.equal(c.cache[0].stale, true);
    assert.equal(c.notify.messages.length, 0);
});

test("a canceled check cannot publish its delayed failure result", async () => {
    const c = context();
    c.cfg.apt = true;
    c.cfg.packages = { apt: true, python3: true };
    const delayed = [];
    c.runLater = (ms, fn) => delayed.push(fn);
    c.execute = (command, callback) => {
        if (command.includes("'check'")) callback(command, JSON.stringify({
            schemaVersion: 1, status: "error", metadataCurrent: false, items: [],
            errors: [{ message: "offline" }],
        }), "", 100);
    };
    let published = 0;
    c.finalize = () => { published++; };
    c.checkUpdates();
    await Promise.resolve();
    assert.equal(delayed.length, 1);
    c.stopCheck();
    delayed[0]();
    assert.equal(published, 0);
});

test("empty stderr does not hide nonzero exit codes", () => {
    const c = context();
    let continued = false;
    assert.equal(c.handleError(17, "", "apt", () => { continued = true; }), true);
    assert.equal(c.sts.errors[0].code, 17);
    assert.equal(continued, true);
});

test("installed-state reconciliation uses identities, not display names", () => {
    const c = context();
    c.cfg.packages.python3 = true;
    c.cache = c.keys([
        { uid: "apt:example:amd64", backend: "apt", NM: "example", VO: "1", VN: "2" },
        { uid: "snap:example", backend: "snap", NM: "example", VO: "1", VN: "2", installedRevision: "10" },
    ]);
    c.saveCache = () => {};
    c.execute = (command, callback) => callback(command, JSON.stringify({
        items: [
            { uid: "apt:example:amd64", backend: "apt", installedVersion: "2" },
            { uid: "snap:example", backend: "snap", installedVersion: "1", installedRevision: "10" },
        ],
        errors: [],
    }), "", 0);
    c.reconcileInstalled();
    assert.equal(c.cache.length, 1);
    assert.equal(c.cache[0].uid, "snap:example");
});

test("named capabilities do not shift terminal detection", () => {
    const c = context();
    c.execute = (command, callback) => callback(command, JSON.stringify({
        tools: { apt: true, snap: true, python3: "/usr/bin/python3", jq: false, tmux: false },
        terminals: ["/usr/bin/konsole"],
    }), "", 0);
    c.checkDependencies();
    assert.equal(c.cfg.packages.apt, true);
    assert.equal(c.cfg.terminals[0].value, "/usr/bin/konsole");
});

test("missing system Python keeps legacy dependencies and terminals usable", () => {
    const c = context();
    c.execute = (command, callback) => callback(
        command, ["/usr/bin/pacman", "", "", "", "", "", "", "", "/usr/bin/konsole"].join("\n"), "", 0);
    c.checkDependencies();
    assert.equal(c.cfg.packages.python3, false);
    assert.equal(c.cfg.packages.apt, false);
    assert.equal(c.cfg.packages.pacman, true);
    assert.equal(c.cfg.terminals[0].value, "/usr/bin/konsole");
});

test("a native automatic Snap refresh clears only its completed revision", () => {
    const c = context();
    c.cfg.packages.python3 = true;
    c.cache = c.keys([{
        uid: "snap:example", backend: "snap", NM: "example", VO: "1", VN: "2", installedRevision: "10",
    }]);
    c.saveCache = () => {};
    c.execute = (command, callback) => callback(command, JSON.stringify({
        items: [{ uid: "snap:example", backend: "snap", installedVersion: "2", installedRevision: "11" }], errors: [],
    }), "", 0);
    c.reconcileInstalled();
    assert.equal(c.cache.length, 0);
});

test("legacy widget identities migrate and the migrated cache is saved", () => {
    const c = context();
    c.cfg.packages.python3 = true;
    c.cache = c.keys([{ NM: "my-widget", CN: "42", VO: "1", VN: "2" }]);
    let saved = false;
    c.saveCache = () => { saved = true; };
    c.execute = (command, callback) => callback(command, JSON.stringify({
        items: [{ uid: "widgets:org.example", nativeId: "org.example", backend: "widgets",
                  name: "My Widget", installedVersion: "1" }], errors: [],
    }), "", 0);
    c.reconcileInstalled();
    assert.equal(c.cache[0].uid, "widgets:org.example");
    assert.equal(c.cache[0].legacyIdentity, false);
    assert.equal(saved, true);
});

test("large cache writes keep complete JSON chunks and safe argument boundaries", () => {
    const c = context();
    c.cfg.packages.python3 = true;
    const records = [{ NM: "' $(printf injected)", DE: "line\n\u{1f600}".repeat(5000), backend: "apt" }];
    const chunks = [];
    c.execute = (command, callback) => {
        const args = execFileSync("/bin/bash", [
            "-c", "set -- " + command + "; printf '%s\\0' \"$@\"",
        ]).toString().split("\0");
        assert.equal(args[4], "cache-chunk");
        chunks.push(args[9]);
        callback(command, "{}", "", 0);
    };
    c.saveCache(records);
    const result = JSON.parse(chunks.join(""));
    assert.equal(result[0].NM, records[0].NM);
    assert.equal(result[0].DE, records[0].DE);
    assert.ok(chunks.length > 1);
});
