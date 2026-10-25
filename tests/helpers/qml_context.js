// Test doubles for Qt services. No QML component or executable process is started.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const sourcePath = path.resolve(__dirname, "../../package/contents/tools/tools.js");
const source = fs.readFileSync(sourcePath, "utf8");

function model(items = []) {
    const entries = [...items];
    return {
        get count() { return entries.length; },
        get(index) { return entries[index]; },
        append(item) { entries.push(item); },
        insert(index, item) { entries.splice(index, 0, item); },
        remove(index) { entries.splice(index, 1); },
        clear() { entries.length = 0; },
        move(from, to, count) { entries.splice(to, 0, ...entries.splice(from, count)); },
        setProperty(index, key, value) { entries[index][key] = value; },
        toArray() { return entries; },
    };
}

function timer() {
    return { running: false, start() { this.running = true; }, stop() { this.running = false; } };
}

function context(options = {}) {
    const c = {
        console, Date, Map, Set, Promise, isOnline: true, isMetered: false,
        Component: { Ready: 1 },
        Qt: { resolvedUrl: value => "file:///tmp/apdatifier path/" + value },
        cfg: { packages: {}, checkMode: "manual", rules: "", notifyUpdates: true,
               notifyEveryBump: true, sorting: true },
        sts: { errors: [], count: 0, busy: false, checkId: "", transactionId: "", completedStageCount: 0,
               retryAt: 0, retryAttempts: 0 },
        scheduler: timer(), upgradeTimer: timer(), saveTimer: timer(),
        cache: [], listModel: model(), newsModel: model(), activeNewsModel: model(),
        plasmoid: { configuration: {} }, root: {}, parent: {},
        notify: { messages: [], send(...args) { this.messages.push(args); } },
        i18n: (text, ...args) => args.reduce((s, value, i) => s.replace("%" + (i + 1), value), text),
        i18np: (one, many, number) => (number === 1 ? one : many).replace("%1", number),
        updatePlasmoidStatus() {},
    };
    Object.defineProperty(c.sts, "error", { get: () => !c.sts.busy && c.sts.errors.length > 0 });
    vm.createContext(c);
    vm.runInContext(source, c, { filename: pathToFileURL(sourcePath).href });
    if (!options.keepExecute) c.execute = () => {};
    return c;
}

function plain(value) {
    return JSON.parse(JSON.stringify(value));
}

module.exports = { context, model, plain };
