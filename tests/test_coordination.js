const assert = require("node:assert/strict");
const { test } = require("node:test");
const vm = require("node:vm");
const { context, plain, model } = require("./helpers/qml_context.js");

const settle = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };
const result = (backend, name, extra = {}) => Object.assign({
    schemaVersion: 1, backend, status: "ok", metadataCurrent: true, synchronizedAt: 123,
    items: [{ backend, uid: backend + ":" + name, nativeId: name, name, installedVersion: "1",
              candidateVersion: "2", repository: backend, summary: "Package", state: "available" }], errors: [],
}, extra);

function nativeContext() {
    const c = context();
    c.cfg.packages = { python3: true, apt: true, snap: true };
    c.cfg.apt = c.cfg.snap = true;
    c.runLater = (ms, callback) => callback();
    c.saveCache = () => {};
    return c;
}

test("successful APT and Snap checks merge native identities and synchronization times", async () => {
    const c = nativeContext();
    c.execute = (command, callback) => {
        if (command.includes("'check'")) {
            const source = command.includes("'apt'") ? "apt" : "snap";
            callback(command, JSON.stringify(result(source, source === "apt" ? "example:amd64" : "example")), "", 0);
        }
    };
    c.checkUpdates();
    await settle();
    assert.equal(c.sts.busy, false);
    assert.equal(c.sts.errors.length, 0);
    assert.deepEqual(plain(c.cache.map(item => item.uid).sort()), ["apt:example:amd64", "snap:example"]);
    assert.ok(c.cache.every(item => item.synchronizedAt === 123 && !item.stale));
});

test("malformed or failed APT results preserve old APT data while Snap can succeed", async () => {
    for (const response of ["{broken", JSON.stringify({ schemaVersion: 9, items: [] }),
                            JSON.stringify(result("apt", "example:amd64", { status: "partial", metadataCurrent: false }))]) {
        const c = nativeContext();
        c.cache = c.keys([{ backend: "apt", uid: "apt:example:amd64", NM: "example", VO: "1", VN: "2" }]);
        c.execute = (command, callback) => {
            if (!command.includes("'check'")) return;
            const apt = command.includes("'apt'");
            callback(command, apt ? response : JSON.stringify(result("snap", "example")), "", apt ? 100 : 0);
        };
        c.checkUpdates();
        await settle();
        assert.equal(c.cache.length, 2);
        assert.equal(c.cache.find(item => item.backend === "apt").stale, true);
        assert.equal(c.cache.find(item => item.backend === "snap").stale, false);
        assert.equal(c.sts.errors[0].type, "apt");
    }
});

test("missing native capabilities keep the source enabled and continue independent checks", async () => {
    const c = nativeContext();
    c.cfg.packages.apt = false;
    const commands = [];
    c.execute = (command, callback) => {
        commands.push(command);
        if (command.includes("'check'")) callback(command, JSON.stringify(result("snap", "example")), "", 0);
    };
    c.checkUpdates();
    await settle();
    assert.equal(c.cfg.apt, true);
    assert.equal(c.sts.errors[0].type, "apt");
    assert.ok(!commands.some(command => command.includes("'check' 'apt'")));
    assert.equal(c.cache[0].backend, "snap");
});

test("canceling a native request rejects its late successful callback", async () => {
    const c = nativeContext();
    let pending;
    const commands = [];
    c.execute = (command, callback) => {
        commands.push(command);
        if (command.includes("'check'")) pending = callback;
    };
    c.checkUpdates();
    c.stopCheck();
    pending("late", JSON.stringify(result("apt", "example:amd64")), "", 0);
    await settle();
    assert.equal(c.sts.busy, false);
    assert.equal(c.cache.length, 0);
    assert.ok(commands.some(command => command.includes("'cancel'")));
});

test("a failed source completes after the Snap result and resumes automatic checks", async () => {
    const c = nativeContext();
    c.cfg.flatpak = true;
    c.cfg.checkMode = "interval";
    c.cfg.intervalMinutes = 120;
    c.cache = c.keys([{ backend: "flatpak", NM: "old-flatpak", ID: "org.example.Old", VO: "1", VN: "2" }]);
    const delayed = [];
    c.runLater = (ms, callback) => delayed.push({ ms, callback });
    c.execute = (command, callback) => {
        if (command.startsWith("flatpak update")) callback(command, "", "network is unreachable", 1);
        else if (command.includes("'check'")) {
            const source = command.includes("'apt'") ? "apt" : "snap";
            callback(command, JSON.stringify(result(source, "example")), "", 0);
        }
    };
    c.checkUpdates();
    await settle();
    assert.equal(c.sts.busy, true);
    assert.equal(c.sts.statusMsg, "Checking Snap updates...");
    assert.equal(delayed.length, 1);
    assert.equal(delayed[0].ms, 3000);
    delayed[0].callback();
    assert.equal(c.sts.busy, false);
    assert.equal(c.scheduler.running, true);
    assert.ok(c.sts.lastCheck > 0);
    assert.equal(c.sts.retryAttempts, 1);
    assert.ok(c.sts.retryAt > c.sts.lastCheck);
    assert.equal(c.cache.length, 3);
    assert.equal(c.cache.find(item => item.backend === "flatpak").stale, true);
    assert.equal(c.cache.find(item => item.backend === "snap").stale, false);
});

test("a canceled delayed completion cannot finish a newer check", async () => {
    const c = nativeContext();
    const delayed = [];
    c.runLater = (ms, callback) => delayed.push(callback);
    c.execute = (command, callback) => {
        if (!command.includes("'check'")) return;
        const source = command.includes("'apt'") ? "apt" : "snap";
        callback(command, JSON.stringify(result(source, "example")), "native failure", source === "apt" ? 1 : 0);
    };
    c.checkUpdates();
    await settle();
    assert.equal(delayed.length, 1);
    c.stopCheck();
    c.execute = () => {};
    c.checkUpdates();
    const token = c.sts.checkId;
    const lastCheck = c.sts.lastCheck;
    delayed[0]();
    assert.equal(c.sts.busy, true);
    assert.equal(c.sts.checkId, token);
    assert.equal(c.sts.lastCheck, lastCheck);
    assert.equal(c.cache.length, 0);
});

test("delayed callbacks belong to the applet and release their timer even on failure", () => {
    for (const throws of [false, true]) {
        const c = context();
        let fire, destroyed = 0, calls = 0;
        const timer = { triggered: { connect(callback) { fire = callback; } },
                        start() {}, destroy() { destroyed++; } };
        c.Qt.createQmlObject = (source, owner) => {
            assert.equal(owner, c.root);
            return timer;
        };
        c.runLater(3000, () => {
            calls++;
            if (throws) throw new Error("callback failure");
        });
        assert.equal(timer.interval, 3000);
        if (throws) assert.throws(fire, /callback failure/);
        else fire();
        assert.equal(calls, 1);
        assert.equal(destroyed, 1);
    }
});

test("widget and firmware discovery share the model without mixing identities", async () => {
    const c = context();
    c.cfg.widgets = c.cfg.fwupd = true;
    c.saveCache = () => {};
    c.execute = (command, callback) => {
        if (command.includes("/widgets' 'check'")) callback(command, JSON.stringify([
            { backend: "widgets", uid: "widgets:org.example", NM: "example", CN: "123", VO: "1", VN: "2" },
        ]), "", 0);
        else if (command.startsWith("fwupdmgr refresh")) callback(command, "", "", 0);
        else if (command.startsWith("fwupdmgr get-updates")) callback(command, JSON.stringify({ Devices: [
            { DeviceId: "device-1", Vendor: "Vendor", Name: "example", Version: "1", Releases: [{ Version: "2", Summary: "Firmware" }] },
        ] }), "", 0);
    };
    c.checkUpdates();
    await settle();
    assert.deepEqual(plain(c.cache.map(item => item.uid).sort()), ["fwupd:device-1", "widgets:org.example"]);
});

test("firmware refresh and query failures keep the last firmware result", async () => {
    for (const failure of ["refresh", "get-updates"]) {
        const c = context();
        c.cfg.fwupd = true;
        c.cache = c.keys([{ backend: "fwupd", uid: "fwupd:device-1", NM: "device", VO: "1", VN: "2" }]);
        c.saveCache = () => {};
        c.runLater = (ms, callback) => callback();
        c.execute = (command, callback) => {
            if (command.startsWith("fwupdmgr")) callback(command, "", "failed", command.includes(failure) ? 1 : 0);
        };
        c.checkUpdates();
        await settle();
        assert.equal(c.cache[0].uid, "fwupd:device-1");
        assert.equal(c.cache[0].stale, true);
        assert.equal(c.sts.errors[0].type, "fwupd");
    }
});

test("Arch and AUR checks retain repository, dependency reason, and native versions", async () => {
    const c = context();
    c.cfg.arch = c.cfg.aur = true;
    c.cfg.packages.pacman = true;
    c.cfg.wrapper = "yay";
    c.cfg.dbPath = "/tmp/package database";
    c.saveCache = () => {};
    c.execute = (command, callback) => {
        if (!callback) return;
        let output = "";
        if (command.startsWith("pacman -Qu")) output = "repo-pkg 1 -> 2";
        else if (command.startsWith("yay -Qua")) output = "source-git 1 -> latest-commit";
        else if (command.includes("pacman -Sl")) output = "extra repo-pkg 2 [installed: 1]";
        else if (command.includes("pacman -Qi")) {
            const name = command.includes("source-git") ? "source-git" : "repo-pkg";
            output = "Name : " + name + "\nDescription : Package\nURL : https://example.invalid\n" +
                     "Install Reason : " + (name === "repo-pkg" ? "Explicitly installed" : "Installed as a dependency") +
                     "\nRequired By : helper\nGroups : None\n";
        } else if (command.includes("'getIcons'")) output = "repo-pkg package-icon\nsource-git source-icon";
        callback(command, output, "", 0);
    };
    c.checkUpdates();
    await settle();
    assert.equal(c.cache.length, 2);
    assert.equal(c.cache.find(item => item.NM === "repo-pkg").RN, "explicit");
    const aur = c.cache.find(item => item.NM === "source-git");
    assert.equal(aur.RE, "devel");
    assert.equal(aur.RN, "dependency");
    assert.equal(aur.VN, "latest commit");
});

test("invalid Arch update lines do not become package commands", async () => {
    const c = context();
    let calls = 0;
    c.execute = () => { calls++; };
    assert.deepEqual(plain(await c.makeArchList(["malformed", "$(touch marker) 1 -> 2"], "aur")), []);
    assert.equal(calls, 0);
});

test("Arch metadata errors retain the last repository result", async () => {
    const c = context();
    c.cfg.arch = true;
    c.cache = c.keys([{ backend: "pacman", NM: "example", RE: "extra", VO: "1", VN: "2" }]);
    c.runLater = (ms, callback) => callback();
    c.saveCache = () => {};
    c.execute = (command, callback) => {
        if (!callback) return;
        callback(command, command.startsWith("pacman -Qu") ? "example 1 -> 2" : "", "",
                 command.includes("pacman -Sl") ? 17 : 0);
    };
    c.checkUpdates();
    await settle();
    assert.equal(c.cache.length, 1);
    assert.equal(c.cache[0].stale, true);
    assert.equal(c.sts.errors[0].type, "repositories");
});

test("news synchronization removes missing articles and inserts new articles in time order", async () => {
    const c = context();
    c.cfg.feedsEnabled = c.cfg.notifyNews = true;
    c.cfg.packages.jq = true;
    c.cfg.feeds = "https://example.invalid/feed|not-a-url";
    c.newsModel = model([{ link: "https://old.invalid", title: "Old", timestamp: 1 }]);
    c.saveCache = () => {};
    c.execute = (command, callback) => {
        if (command.includes("'rss'")) callback(command, JSON.stringify([
            { link: "https://new.invalid", title: "New", article: "Article", timestamp: 10 },
        ]), "", 0);
    };
    c.checkUpdates();
    await settle();
    assert.equal(c.newsModel.count, 1);
    assert.equal(c.newsModel.get(0).link, "https://new.invalid");
    assert.ok(c.notify.messages.some(message => message[0] === "news"));
});

test("active lifecycle stages refresh installed state once and keep the scheduler stopped", () => {
    const c = context();
    c.cfg.packages.python3 = true;
    let reconciliations = 0;
    c.reconcileInstalled = () => { reconciliations++; };
    c.execute = (command, callback) => callback(command, JSON.stringify({ id: "active", status: "running", stages: [{}] }), "", 0);
    c.upgradingState();
    c.upgradingState();
    assert.equal(reconciliations, 1);
    assert.equal(c.sts.upgrading, true);
    assert.equal(c.upgradeTimer.running, true);
    assert.equal(c.scheduler.running, false);
});

test("completed lifecycle states distinguish success, cancellation, partial failure, and unknown results", () => {
    for (const status of ["ok", "canceled", "partial", "error", "unknown"]) {
        const c = context();
        c.cfg.packages.python3 = true;
        c.sts.transactionId = "completed";
        c.sts.upgrading = true;
        c.reconcileInstalled = () => {};
        c.execute = (command, callback) => callback(command, JSON.stringify({ id: "completed", status }), "", 0);
        c.upgradingState();
        assert.equal(c.sts.upgrading, false);
        assert.equal(c.sts.transactionId, "");
        assert.equal(c.sts.errors.length, status === "ok" ? 0 : 1);
    }
});

test("completed upgrades refresh the status text and icon when installed packages leave the cache unchanged", () => {
    for (const pending of [false, true]) {
        const c = nativeContext();
        c.cfg.checkMode = "interval";
        c.cache = c.keys(pending ? [{ backend: "apt", uid: "apt:example:amd64", nativeId: "example:amd64",
                                    NM: "example", VO: "1", VN: "2" }] : []);
        c.refreshListModel();
        const previousCache = JSON.stringify(c.cache);
        c.sts.transactionId = "completed";
        c.sts.busy = c.sts.upgrading = true;
        c.sts.statusMsg = "Upgrade in progress...";
        c.sts.statusIco = "akonadiconsole";
        c.upgradeTimer.start();
        c.execute = (command, callback) => {
            if (command.includes("'lifecycle' 'state'")) {
                callback(command, JSON.stringify({ id: "completed", status: "ok" }), "", 0);
            } else if (command.includes("'installed'")) {
                callback(command, JSON.stringify({
                    items: c.cache.map(item => ({ uid: item.uid, installedVersion: item.VO })), errors: [],
                }), "", 0);
            } else assert.fail("Unexpected command: " + command);
        };
        c.upgradingState();
        assert.equal(JSON.stringify(c.cache), previousCache);
        assert.equal(c.sts.busy, false);
        assert.equal(c.sts.upgrading, false);
        assert.equal(c.upgradeTimer.running, false);
        assert.equal(c.scheduler.running, true);
        assert.equal(c.sts.statusMsg, pending ? "1 update is pending" : "");
        assert.equal(c.sts.statusIco, pending ? "accept_time_event" : "");
    }
});

test("legacy lifecycle fallback reconciles versions when system Python is unavailable", () => {
    const c = context();
    c.cache = c.keys([{ NM: "kept", VO: "1", VN: "2" }, { NM: "updated", VO: "1", VN: "2" }]);
    c.execute = (command, callback) => {
        if (callback) callback(command, command.startsWith("pgrep") ? "" :
            JSON.stringify([{ NM: "Kept", VO: "1" }, { NM: "Updated", VO: "2" }]), "", 0);
    };
    c.upgradingState();
    assert.equal(c.cache.length, 1);
    assert.equal(c.cache[0].NM, "kept");
    c.execute = (command, callback) => callback(command, "123", "", 0);
    c.upgradingState();
    assert.equal(c.sts.upgrading, true);
});

test("Qt execution bridge forwards command results and reports component creation failures", () => {
    const c = context({ keepExecute: true });
    const object = { exec(command, callback) { callback(command, "output", "", 0); } };
    c.Qt.createComponent = () => ({ status: 1, createObject: () => object });
    let output;
    c.execute("literal command", (command, out) => { output = out; }, { stoppable: true });
    assert.equal(output, "output");
    assert.equal(c.sts.proc, object);
    c.Qt.createComponent = () => ({ status: 1, createObject: () => null });
    c.execute("unavailable");
    c.Qt.createComponent = () => ({ status: 0 });
    c.execute("not ready");
    assert.equal(c.sts.errors.length, 2);
});

test("terminal launch errors stop busy state and restore automatic scheduling", () => {
    const c = context();
    c.cfg.checkMode = "interval";
    c.runLater = () => {};
    const calls = [];
    c.execute = (command, callback) => calls.push({ command, callback });
    vm.runInContext('runInTerminal("upgrade", "apt")', c);
    calls[0].callback(calls[0].command, "", "", 0);
    calls[1].callback(calls[1].command, "", "terminal failed", 1);
    assert.equal(c.sts.busy, false);
    assert.equal(c.sts.upgrading, false);
    assert.equal(c.scheduler.running, true);
});

test("startup loads configuration, cache, rules, and news before reconciliation", () => {
    const c = context();
    let ready = false;
    c.checkDependencies = callback => callback();
    c.upgradingState = () => { ready = true; };
    c.execute = (command, callback) => {
        if (!callback) return;
        let output = "";
        if (command.includes("config.conf")) output = 'apt="true"\nintervalMinutes="15"\nwrapper="yay"';
        else if (command.includes("lastCheck")) output = "123";
        else if (command.includes("updates.json")) output = '[{"backend":"apt","NM":"example","VO":"1","VN":"2"}]';
        else if (command.includes("rules.json")) output = "[]";
        else if (command.includes("news.json")) output = '[{"link":"https://example.invalid","timestamp":1}]';
        callback(command, output, "", 0);
    };
    c.init();
    assert.equal(ready, true);
    assert.equal(c.sts.init, true);
    assert.equal(c.plasmoid.configuration.apt, true);
    assert.equal(c.plasmoid.configuration.intervalMinutes, 15);
    assert.equal(c.sts.lastCheck, 123);
    assert.equal(c.newsModel.count, 1);
});

test("Flatpak discovery checks AppStream before reading scoped candidates", async () => {
    const c = context();
    c.cfg.flatpak = true;
    c.saveCache = () => {};
    const commands = [];
    c.execute = (command, callback) => {
        if (!callback) return;
        commands.push(command);
        let output = "";
        if (command.startsWith("flatpak list")) output = "org.example.App\t1\told\tstable\tx86_64\tuser\tflathub";
        else if (command.includes("'remote-ls'")) output = ["Example", "App", "org.example.App", "2", "stable",
            "x86_64", "flathub", "app/org.example.App/x86_64/stable", "new", "", "1 MB", "1 MB"].join("\t");
        callback(command, output, "", 0);
    };
    c.checkUpdates();
    await settle();
    assert.ok(commands[0].startsWith("flatpak update --appstream"));
    assert.equal(c.cache[0].uid, "flatpak:user:org.example.App/x86_64/stable");
});

test("native single-package and widget actions keep their backend-specific arguments", () => {
    for (const [item, action, identity] of [
        [{ backend: "apt", nativeId: "example:i386", ID: "unrelated" }, "apt-pkg", "example:i386"],
        [{ backend: "snap", nativeId: "example" }, "snap-pkg", "example"],
        [{ backend: "widgets", CN: "123", NM: "Widget" }, "widget-pkg", "123"],
    ]) {
        const c = context();
        c.runLater = () => {};
        const calls = [];
        c.execute = (command, callback) => calls.push({ command, callback });
        c.upgradePackage(item);
        calls[0].callback(calls[0].command, "", "", 0);
        assert.ok(calls[1].command.includes("'" + action + "'"));
        assert.ok(calls[1].command.includes("'" + identity + "'"));
    }
});

test("management launch includes a transaction without an upgrade operation argument", () => {
    const c = context();
    c.runLater = () => {};
    const calls = [];
    c.execute = (command, callback) => calls.push({ command, callback });
    c.management();
    calls[0].callback(calls[0].command, "", "", 0);
    assert.ok(calls[1].command.includes("'management' '--transaction'"));
    assert.match(c.sts.statusMsg, /Package management/);
});

test("native ignore globs preserve literal punctuation and wildcard semantics", async () => {
    const c = context();
    c.cfg.packages.pacman = true;
    c.execute = (command, callback) => callback(command, "library.* widget?", "", 0);
    const patterns = await c.loadIgnorePkgs();
    assert.equal(patterns[0].test("library.so"), true);
    assert.equal(patterns[0].test("libraryXso"), false);
    assert.equal(patterns[1].test("widget1"), true);
    assert.equal(patterns[1].test("widget12"), false);
});

test("pending cache writes are serialized and recover after a failed write", () => {
    const c = context();
    c.cfg.packages.python3 = true;
    const calls = [];
    c.execute = (command, callback) => calls.push({ command, callback });
    c.saveCache([{ NM: "old", backend: "apt" }]);
    c.saveCache([{ NM: "new", backend: "apt" }]);
    assert.equal(calls.length, 1);
    calls[0].callback(calls[0].command, "", "disk full", 1);
    assert.equal(calls.length, 2);
    assert.ok(calls[1].command.includes('"new"'));
    calls[1].callback(calls[1].command, "{}", "", 0);
    assert.equal(c.sts.errors.length, 1);
    c.saveCache([{ NM: "recovered", backend: "apt" }]);
    assert.equal(calls.length, 3);
});

test("offline and upgrading states prevent starting another discovery sequence", () => {
    const c = context();
    let calls = 0;
    c.execute = () => { calls++; };
    c.isOnline = false;
    c.checkUpdates();
    c.isOnline = true;
    c.sts.upgrading = true;
    c.checkUpdates();
    assert.equal(calls, 0);
    assert.equal(c.sts.checkId, "");
});
