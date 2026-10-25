const assert = require("node:assert/strict");
const { test } = require("node:test");
const { context, model, plain } = require("./helpers/qml_context.js");

function atNoon() {
    const c = context();
    const now = new Date(2026, 0, 6, 12, 0, 0).getTime();
    c.Date = class extends Date { constructor(...args) { super(...(args.length ? args : [now])); } static now() { return now; } };
    return { c, now };
}

test("interval scheduling uses the last check and triggers only due work", () => {
    const { c, now } = atNoon();
    c.cfg.checkMode = "interval";
    c.cfg.intervalMinutes = 5;
    c.sts.lastCheck = now - 240000;
    assert.equal(c.searchScheduler({ simulate: true }), now + 60000);
    let calls = 0;
    c.checkUpdates = () => { calls++; };
    c.searchScheduler();
    assert.equal(calls, 0);
    c.sts.lastCheck = now - 295000;
    c.searchScheduler();
    assert.equal(calls, 1);
});

test("daily and weekly schedules advance to the next local occurrence", () => {
    const { c } = atNoon();
    Object.assign(c.cfg, { checkMode: "daily", dailyHour: 11, dailyMinute: 30 });
    assert.equal(c.searchScheduler({ simulate: true }), new Date(2026, 0, 7, 11, 30).getTime());
    Object.assign(c.cfg, { checkMode: "weekly", weeklyDay: 2, weeklyHour: 11, weeklyMinute: 30 });
    assert.equal(c.searchScheduler({ simulate: true }), new Date(2026, 0, 13, 11, 30).getTime());
    c.cfg.weeklyDay = 4;
    assert.equal(c.searchScheduler({ simulate: true }), new Date(2026, 0, 8, 11, 30).getTime());
});

test("offline, metered, manual, and busy states prevent inappropriate scheduling", () => {
    const { c } = atNoon();
    c.cfg.checkMode = "interval";
    c.isOnline = false;
    assert.equal(c.searchScheduler({ simulate: true }), undefined);
    c.isOnline = true;
    c.isMetered = true;
    assert.equal(c.searchScheduler({ simulate: true }), undefined);
    c.isMetered = false;
    c.cfg.checkMode = "manual";
    c.scheduler.start();
    c.searchScheduler();
    assert.equal(c.scheduler.running, false);
    c.switchScheduler();
    assert.equal(c.scheduler.running, false);
    c.cfg.checkMode = "interval";
    c.sts.busy = true;
    c.switchScheduler();
    assert.equal(c.scheduler.running, false);
    c.sts.busy = false;
    c.switchScheduler();
    assert.equal(c.scheduler.running, true);
});

test("check-time text reports previous and future checks without negative durations", () => {
    const { c, now } = atNoon();
    c.sts.lastCheck = now - 90000;
    Object.assign(c.cfg, { checkMode: "interval", intervalMinutes: 5 });
    assert.match(c.getCheckTime(), /Last check:.*1 minute/);
    c.scheduler.start();
    assert.match(c.getCheckTime(), /Next check in:/);
    c.sts.lastCheck = now + 1000;
    assert.ok(!c.getCheckTime().includes("Last check:"));
});

test("feed serialization rejects invalid protocols and deduplicates valid feeds", () => {
    const c = context();
    assert.deepEqual(plain(c.parseCustomFeeds("https://one.invalid/feed|file:///etc/passwd\nhttp://two.invalid/feed")),
                     ["https://one.invalid/feed", "http://two.invalid/feed"]);
    assert.equal(c.serializeCustomFeeds([" https://one.invalid/feed ", "https://one.invalid/feed", "javascript:bad"]),
                 "https://one.invalid/feed");
    assert.equal(c.serializeCustomFeeds("https://one.invalid/feed\nhttps://two.invalid/feed"),
                 "https://one.invalid/feed|https://two.invalid/feed");
});

test("removed news items remain separate from active items in timestamp order", () => {
    const c = context();
    c.newsModel = model([{ link: "a", timestamp: 10 }, { link: "b", timestamp: 5 },
                         { link: "c", timestamp: 8, removed: true }]);
    c.addNewsItem({ link: "new", timestamp: 12 });
    assert.equal(c.newsModel.get(0).link, "new");
    c.removeNewsItem(0);
    assert.equal(c.newsModel.get(2).link, "new");
    assert.equal(c.newsModel.get(2).removed, true);
    const before = JSON.stringify(c.newsModel.toArray());
    c.removeNewsItem(2);
    assert.equal(JSON.stringify(c.newsModel.toArray()), before);
});

test("invalid rules and malformed JSON do not execute package text", () => {
    const c = context();
    c.cfg.rules = JSON.stringify([{ type: "regex", value: "[", excluded: true }]);
    const items = c.keys([{ NM: "example", LN: "javascript:bad" }]);
    assert.equal(c.applyRules(items).length, 1);
    assert.equal(items[0].LN, "");
    assert.equal(c.validJSON("not-json", "cache.json"), false);
    assert.equal(c.sts.errors.length, 1);
    assert.equal(c.validJSON("17"), false);
    assert.deepEqual(plain(c.validJSON('[{"uid":"example"}]')), [{ uid: "example" }]);
});
