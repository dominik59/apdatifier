const assert = require("node:assert/strict");
const { test } = require("node:test");
const { context } = require("./helpers/qml_context.js");

function automatic() {
    const c = context();
    let now = 1000000;
    c.Date = class extends Date { constructor(...args) { super(...(args.length ? args : [now])); } static now() { return now; } };
    Object.assign(c.cfg, { checkMode: "interval", intervalMinutes: 120, checkConn: false });
    c.sts.retryAt = c.sts.retryAttempts = 0;
    c.saveCache = () => {};
    return { c, time: () => now, advance: milliseconds => { now += milliseconds; } };
}

test("network failures from native and legacy sources are distinguished from repository faults", () => {
    const { c } = automatic();
    for (const error of [
        { category: "network-error", message: "The command timed out." },
        { message: "While fetching: [7] Could not connect to server" },
        { message: "network is unreachable: Komputer jest niedostepny" },
        { message: "Temporary failure resolving archive.ubuntu.com" },
    ]) assert.equal(c.isNetworkError(error), true);
    for (const message of ["The repository no longer has a Release file.", "The signatures could not be verified: NO_PUBKEY",
                           "Too many API requests", "Cannot connect to snapd: Permission denied"]) {
        assert.equal(c.isNetworkError({ message }), false);
    }
    assert.equal(c.isNetworkError({ type: "snap", category: "service-unavailable",
                                   message: "Cannot connect to snapd: Connection refused" }), false);
});

test("a network failure schedules a short retry without changing connectivity preferences", () => {
    const { c, time } = automatic();
    c.sts.errors = [{ type: "flatpak", code: 1, message: "Could not connect to server" }];
    c.finalize([]);
    assert.equal(c.sts.retryAt, time() + 30000);
    assert.equal(c.sts.retryAttempts, 1);
    assert.equal(c.searchScheduler({ simulate: true }), time() + 30000);
    assert.equal(c.cfg.checkConn, false);
});

test("network retries use bounded backoff instead of retrying forever", () => {
    const { c, time, advance } = automatic();
    for (const delay of [30000, 60000, 120000]) {
        c.sts.errors = [{ type: "fwupd", code: 101, message: "network is unreachable" }];
        c.finalize([]);
        assert.equal(c.sts.retryAt, time() + delay);
        advance(delay);
    }
    c.finalize([]);
    assert.equal(c.sts.retryAt, 0);
    assert.equal(c.sts.retryAttempts, 3);
});

test("successful recovery clears retries and preserves the ordinary interval", () => {
    const { c, time } = automatic();
    c.sts.retryAt = time() + 30000;
    c.sts.retryAttempts = 2;
    c.sts.errors = [];
    c.finalize([]);
    assert.equal(c.sts.retryAt, 0);
    assert.equal(c.sts.retryAttempts, 0);
    assert.equal(c.searchScheduler({ simulate: true }), time() + 120 * 60000);
});

test("pending retries respect offline and metered connection restrictions", () => {
    const { c, time, advance } = automatic();
    c.sts.retryAt = time() + 30000;
    advance(30000);
    const calls = [];
    c.checkUpdates = options => calls.push(options);
    c.isOnline = false;
    c.searchScheduler();
    assert.equal(calls.length, 0);
    c.isOnline = true;
    c.isMetered = true;
    c.searchScheduler();
    assert.equal(calls.length, 0);
    c.isMetered = false;
    c.searchScheduler();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].retry, true);
});

test("manual mode and persistent repository errors do not start automatic retries", () => {
    const { c } = automatic();
    c.cfg.checkMode = "manual";
    c.sts.errors = [{ type: "apt", code: 100, category: "network-error", message: "Network unavailable" }];
    c.finalize([]);
    assert.equal(c.sts.retryAt, 0);
    c.cfg.checkMode = "interval";
    c.sts.errors = [{ type: "apt", code: 100, message: "The repository no longer has a Release file." }];
    c.finalize([]);
    assert.equal(c.sts.retryAt, 0);
});

test("canceling clears a pending retry and a new check resets its retry budget", () => {
    const { c, time } = automatic();
    c.sts.retryAt = time() + 30000;
    c.sts.retryAttempts = 2;
    c.stopCheck();
    assert.equal(c.sts.retryAt, 0);
    assert.equal(c.sts.retryAttempts, 0);
    c.cfg.apt = true;
    c.cfg.packages = { python3: true, apt: true };
    c.sts.retryAttempts = 2;
    c.checkUpdates({ retry: true });
    assert.equal(c.sts.retryAttempts, 2);
    c.stopCheck();
    c.sts.retryAttempts = 3;
    c.checkUpdates();
    assert.equal(c.sts.retryAttempts, 0);
});

test("structured native network failures keep the native exit code and retry category", async () => {
    const { c } = automatic();
    c.cfg.apt = true;
    c.cfg.packages = { python3: true, apt: true };
    c.runLater = (delay, callback) => callback();
    c.execute = (command, callback) => {
        if (command.includes("'check'")) callback(command, JSON.stringify({
            schemaVersion: 1, status: "partial", items: [], metadataCurrent: false,
            errors: [{ category: "network-error", code: 100, message: "Network unavailable" }],
        }), "", 1);
    };
    c.checkUpdates();
    for (let i = 0; i < 4; i++) await Promise.resolve();
    assert.equal(c.sts.errors[0].code, 100);
    assert.equal(c.sts.errors[0].category, "network-error");
    assert.equal(c.sts.retryAttempts, 1);
});
