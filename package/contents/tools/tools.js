const scriptDir = decodeURIComponent(Qt.resolvedUrl("sh/").toString().replace("file://", ""));
const configDir = "${APDATIFIER_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/apdatifier}/"
const cacheDir = "${APDATIFIER_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/apdatifier}/"
const configFile = configDir + "config.conf"
const cacheFile = cacheDir + "updates.json"
const rulesFile = configDir + "rules.json"
const newsFile = cacheDir + "news.json"
const timestampFile = cacheDir + "lastCheck"

const procOpt = { stoppable: true }
const helperPath = decodeURIComponent(Qt.resolvedUrl("backends.py").toString().replace("file://", ""))
const shellQuote = value => "'" + String(value).replace(/'/g, "'\\''") + "'"
const helper = (...args) => ["/usr/bin/python3", "-I", "-B", helperPath, ...args].map(shellQuote).join(" ")
const escapeHTML = value => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")
let pendingCacheWrite = null
let cacheWriteActive = false

function execute(command, callback, opt) {
    const component = Qt.createComponent("../ui/components/Shell.qml")
    if (component.status === Component.Ready) {
        const componentObject = component.createObject(root)
        if (componentObject) {
            if (opt && opt.stoppable) sts.proc = componentObject
            componentObject.exec(command, callback)
        } else {
            Error(1, "Failed to create executable DataSource object")
        }
    } else {
        Error(1, "Executable DataSource component not ready")
    }
}

const readFile = (file) => `if [ -f "${file}" ]; then cat "${file}"; fi`
const writeFile = (data, redir, file) => `printf '%s\\n' ${shellQuote(data)} ${redir} "${file}"`
const saveTimestamp = () => execute(writeFile(Math.round(sts.lastCheck).toString(), '>', timestampFile))

const bash = (script, ...args) => ["bash", scriptDir + script, ...args].map(shellQuote).join(" ")
const runInTerminal = (script, ...args) => {
    if (script === "upgrade" || script === "management") {
        const transaction = String(Date.now()) + "-" + Math.random().toString(36).slice(2)
        sts.transactionId = transaction
        sts.completedStageCount = 0
        args.splice(script === "upgrade" ? 1 : 0, 0, "--transaction", transaction)
    }
    const cmd = bash('terminal', script, ...args)
    const failedLaunch = () => {
        sts.busy = sts.upgrading = false
        upgradeTimer.stop()
        resumeScheduler()
    }
    const launch = () => execute("kstart -- " + cmd, (command, out, err, code) => {
        if (code) {
            Error(code, err || i18n("Cannot start the terminal."))
            failedLaunch()
        }
    })
    saveTimer.stop()
    saveConfig(saved => saved ? launch() : failedLaunch(), true)
    if (script === "upgrade" || script === "management") {
        runLater(5000, () => upgradeTimer.start())
        scheduler.stop()
        sts.busy = sts.upgrading = true
        sts.statusMsg = (script === "management" ? i18n("Package management in progress") : i18n("Upgrade in progress")) + "..."
        sts.statusIco = cfg.ownIconsUI ? "toolbar_upgrade" : "akonadiconsole"
    }

}

function runLater(ms, fn) {
    // The applet survives startup reparenting; its visual parent may not.
    const timer = Qt.createQmlObject('import QtQuick 2.0; Timer { repeat: false }', root)
    timer.interval = ms
    timer.triggered.connect(() => {
        try { fn() } finally { timer.destroy() }
    })
    timer.start()
}

const debug = true
function log(message) {
    if (debug) console.log("[" + new Date().getTime().toString() + "] "+ "APDATIFIER: " + message)
}

function Error(code, err) {
    if (code || err) {
        err = err || i18n("The command failed without an error message.")
        sts.errors = sts.errors.concat([{code: code, message: err.trim(), type: ""}])
        cfg.notifyErrors && notify.send("error", i18n("Exit code: ") + code, err.trim())
        setStatusBar()
        return true
    }
    return false
}

function handleError(code, err, type, onError, category) {
    if (code) {
        err = err || i18n("The command failed without an error message.")
        if (type === "aur") err = err.replace(/(https?:\/\/[^\s)?]+)\?[^\s)]+/g, '$1?…')
        sts.errors = sts.errors.concat([{code: code, message: err.trim(), type: type, category: category || ""}])
        onError()
        return true
    }
    return false
}

function init() {
    execute(bash('init'), (cmd, out, err, code) => {
        if (Error(code, err)) return
        loadConfig()
    })

    function loadConfig() {
        execute(readFile(configFile), (cmd, out, err, code) => {
            if (Error(code, err)) return
            if (out) {
                const config = out.trim().split("\n")
                const convert = value => {
                    if (!isNaN(parseFloat(value))) return parseFloat(value)
                    if (value === "true" || value === "false") return value === 'true'
                    return value
                }
                config.forEach(line => {
                    const match = line.match(/(\w+)="((?:\\.|[^"])*)"/)
                    if (match) {
                        if (typeof plasmoid.configuration[match[1]] === "object") return // skip font
                        plasmoid.configuration[match[1]] = convert(match[2].replace(/\\([\\"$`])/g, "$1"))
                    }
                })
            }

            execute(readFile(timestampFile), (cmd, out, err, code) => {
                if (out) sts.lastCheck = parseInt(out.trim()) || 0
                loadCache()
            })
        })
    }

    function loadCache() {
        execute(readFile(cacheFile), (cmd, out, err, code) => {
            if (Error(code, err)) return
            if (out && validJSON(out, cacheFile)) cache = keys(JSON.parse(out.trim()))
            loadRules()
        })
    }

    function loadRules() {
        execute(readFile(rulesFile), (cmd, out, err, code) => {
            if (Error(code, err)) return
            if (out && validJSON(out, rulesFile)) plasmoid.configuration.rules = out
            loadNews()
        })
    }

    function loadNews() {
        execute(readFile(newsFile), (cmd, out, err, code) => {
            if (Error(code, err)) return
            if (out && validJSON(out, newsFile)) {
                const news = JSON.parse(out.trim())
                for (const article of news) addNewsItem(article)
            }

            onStartup()
        })
    }

    function onStartup() {
        sts.init = true
        checkDependencies(() => {
            refreshListModel()
            upgradingState()
        })
    }
}

function saveConfig(done, force) {
    if (saveTimer.running && !force) return
    let config = ""
    Object.keys(cfg).forEach(key => {
        if (key.endsWith("Default")) {
            let name = key.slice(0, -7)
            if (typeof cfg[name] === "object") return // skip font
            const value = String(cfg[name]).replace(/\\/g, "\\\\").replace(/(["$`])/g, "\\$1")
            config += `${name}="${value}"\n`
        }
    })
    execute(writeFile(config, ">", configFile), (cmd, out, err, code) => {
        const failed = Error(code, err)
        if (typeof done === "function") done(!failed)
    })
}

function checkDependencies(done) {
    const populate = (data) => data.map(item => ({
        "name": item.startsWith("flatpak://") ? `${item.split("/").pop()} (Flatpak)` : item.split("/").pop(),
        "value": item
    }))

    execute(bash('utils', 'checkPkgs'), (cmd, out, err, code) => {
        if (Error(code, err)) return

        let packages, terminalPaths
        if (out.trim().startsWith("{")) {
            if (!validJSON(out)) return
            const result = JSON.parse(out)
            if (!result.tools || !Array.isArray(result.terminals)) return
            packages = result.tools
            terminalPaths = result.terminals
        } else {
            // Keep existing backends usable when system Python is absent.
            const output = out.split("\n")
            const names = ["pacman", "flatpak", "fwupdmgr", "paru", "pikaur", "yay", "jq", "tmux"]
            packages = { python3: false, apt: false, snap: false }
            names.forEach((name, index) => packages[name] = Boolean(output[index]))
            terminalPaths = output.slice(8).filter(Boolean)
        }
        const { pacman, flatpak, fwupdmgr, paru, pikaur, yay, jq, tmux } = packages
        cfg.packages = packages
        if (!cfg.wrapper) cfg.wrapper = paru ? "paru" : yay ? "yay" : pikaur ? "pikaur" : ""

        const terminals = populate(terminalPaths)
        cfg.terminals = terminals.length > 0 ? terminals : null
        if (!cfg.terminal || !terminals.some(t => t.value === cfg.terminal))
            cfg.terminal = terminals.length > 0 ? terminals[0].value : ""

        if (!pacman) plasmoid.configuration.arch = false
        if (!pacman || (!yay && !paru && !pikaur)) plasmoid.configuration.aur = false
        if (!flatpak) plasmoid.configuration.flatpak = false
        if (!fwupdmgr) plasmoid.configuration.fwupd = false
        if (!tmux) plasmoid.configuration.tmuxSession = false
        if (!jq) {
            plasmoid.configuration.widgets = false
            plasmoid.configuration.feedsEnabled = false
        }
        if (typeof done === "function") done()
    })
}


function upgradePackage(pkg) {
    if (sts.upgrading) return
    if (pkg.backend === "apt" || pkg.backend === "snap") {
        runInTerminal("upgrade", pkg.backend + "-pkg", pkg.nativeId)
    } else if (pkg.ID) {
        const reference = pkg.architecture && pkg.BR ? "app/" + pkg.ID + "/" + pkg.architecture + "/" + pkg.BR : pkg.ID
        runInTerminal("upgrade", "flatpak-pkg", reference, pkg.NM, pkg.installation || "")
    } else if (pkg.CN) {
        runInTerminal("upgrade", "widget-pkg", pkg.CN, pkg.NM)
    }
}

function management() {
    runInTerminal("management")
}


function upgradingState() {
    if (cfg.packages?.python3) {
        execute(helper("lifecycle", "state"), (cmd, out, err, code) => {
            if (code || !out || !validJSON(out)) {
                handleError(code || 1, err, "transaction", () => {})
                return
            }
            const state = JSON.parse(out)
            const active = state.status === "running"
            if (active) {
                if (sts.transactionId !== state.id) sts.completedStageCount = 0
                sts.transactionId = state.id
                scheduler.stop()
                upgradeTimer.start()
                sts.busy = sts.upgrading = true
                sts.statusMsg = i18n("Upgrade in progress") + "..."
                if ((state.stages || []).length > sts.completedStageCount) {
                    sts.completedStageCount = state.stages.length
                    reconcileInstalled()
                }
            } else {
                const wasUpgrading = sts.upgrading
                sts.busy = sts.upgrading = false
                upgradeTimer.stop()
                if (state.id === sts.transactionId && ["error", "partial", "canceled", "unknown"].includes(state.status)) {
                    const message = state.message || i18n("Package operation result: %1", state.status)
                    sts.errors = sts.errors.concat([{ code: 1, type: "transaction", message }])
                }
                reconcileInstalled()
                setStatusBar()
                if (wasUpgrading) sts.transactionId = ""
                resumeScheduler()
            }
            updatePlasmoidStatus()
        })
        return
    }
    const checkProc = `pgrep -f "apdatifier.*upgrade*"`
    execute(checkProc, (cmd, out, err, code) => {
        if (!out) {
            sts.busy = sts.upgrading = false
            upgradeTimer.stop()
            execute(bash('utils', "currentVersions"), (cmd, out, err, code) => {
                if (Error(code, err)) return
                if (!out || !validJSON(out)) return
                const currentVersions = JSON.parse(out)
                const newList = cache.filter(cached => {
                    const current = currentVersions.find(pkg => pkg.NM.replace(/ /g, "-").toLowerCase() === cached.NM)
                    return current && current.VO === cached.VO + cached.AC
                })
                if (JSON.stringify(cache) !== JSON.stringify(newList)) {
                    cache = newList
                    refreshListModel()
                    saveCache(cache)
                }
                setStatusBar()
                resumeScheduler()
            })
        } else {
            scheduler.stop()
            upgradeTimer.start()
            sts.busy = sts.upgrading = true
            sts.statusMsg = i18n("Upgrade in progress") + "..."
            sts.statusIco = cfg.ownIconsUI ? "toolbar_upgrade" : "akonadiconsole"
        }
        updatePlasmoidStatus()
    })
}

function reconcileInstalled() {
    if (!cfg.packages?.python3) return
    execute(helper("installed"), (cmd, out, err, code) => {
        if (code || !out || !validJSON(out)) return
        const result = JSON.parse(out)
        if (!Array.isArray(result.items) || !Array.isArray(result.errors)) return
        const failed = new Set(result.errors.map(entry => entry.backend))
        const versions = new Map(result.items.map(item => [item.uid, item]))
        const previous = JSON.stringify(cache)
        const remaining = keys(cache).filter(item => {
            if (failed.has(item.backend)) return true
            let current = versions.get(item.uid)
            if (!current && item.legacyIdentity) {
                const normalized = name => name.replace(/ /g, "-").toLowerCase()
                const matches = result.items.filter(pkg => pkg.backend === item.backend &&
                    (item.backend === "flatpak" ? pkg.name === item.ID && (!item.BR || pkg.branch === item.BR)
                        : normalized(pkg.name) === normalized(item.NM)))
                if (matches.length !== 1) return true // Wait for a complete source check when migration is ambiguous.
                current = matches[0]
                item.uid = current.uid
                item.nativeId = current.nativeId
                item.legacyIdentity = false
            }
            if (!current) return false
            return item.backend === "snap"
                ? current.installedRevision === item.installedRevision
                : item.backend === "flatpak"
                ? current.installedRevision === item.AC && current.installedVersion === item.VO
                : current.installedVersion === item.VO
        })
        if (previous !== JSON.stringify(remaining)) {
            cache = remaining
            refreshListModel()
            saveCache(cache)
        }
    })
}

function upgradeSystem() {
    if (sts.upgrading && !cfg.tmuxSession) return
    runInTerminal("upgrade", "full", ...buildIgnoreArgs())
}

function upgradePart(source) {
    if (sts.upgrading && !cfg.tmuxSession) return
    if (source === "system") {
        runInTerminal("upgrade", "system", ...buildIgnoreArgs())
    } else {
        runInTerminal("upgrade", source)
    }
}

function stopCheck() {
    if (cfg.packages?.python3 && sts.checkId) execute(helper("cancel", sts.checkId))
    sts.checkId = ""
    sts.retryAt = 0
    sts.retryAttempts = 0
    sts.errors = []
    sts.busy = false
    sts.proc?.cleanup()
    setStatusBar()
    resumeScheduler()

    if (isOnline) {
        sts.lastCheck = Date.now()
        saveTimestamp()
    }
}


function loadIgnorePkgs() {
    return new Promise(resolve => {
        if (!cfg.packages || !cfg.packages.pacman) {
            resolve([])
            return
        }

        execute("pacman-conf IgnorePkg", (cmd, out, err, code) => {
            if (code || !out) {
                resolve([])
                return
            }

            const tokens = out.trim().split(/\s+/).filter(Boolean)
            const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

            const patterns = tokens.map(token => {
                let pat = token.split(/[<>=]/)[0].trim()
                if (!pat) return null
                let re = escapeRe(pat)
                re = re.replace(/\\\*/g, ".*").replace(/\\\?/g, ".")
                return new RegExp("^" + re + "$")
            }).filter(Boolean)

            resolve(patterns)
        })
    })
}

function buildIgnoreArgs() {
    const rules = !cfg.rules ? [] : JSON.parse(cfg.rules)
    if (!Array.isArray(rules)) return []

    const ignoreItems = rules.filter(rule =>
        rule && rule.ignore === true && (!rule.backend || rule.backend === "pacman")
    )

    if (ignoreItems.length === 0) return []

    const values = ignoreItems.map(rule => rule.value)
    return ["--ignore", values.join(',')]
}


function checkUpdates(options) {
    if (sts.upgrading) return
    if (!isOnline) return

    if (!options?.retry) sts.retryAttempts = 0
    sts.retryAt = 0
    sts.errors = []
    sts.checkId = String(Date.now()) + "-" + Math.random().toString(36).slice(2)
    const token = sts.checkId
    scheduler.stop()
    sts.busy = true

    let archRepos = [], archAur = [], flatpak = [], widgets = [], firmwares = [], nativePackages = []

    const feeds = cfg.feedsEnabled ? parseCustomFeeds(cfg.feeds) : []
    const news = feeds.length && cfg.packages?.jq

             news ? checkNews() :
         cfg.arch ? checkRepos() :
          cfg.aur ? checkAur() :
      cfg.flatpak ? checkFlatpak() :
      cfg.widgets ? checkWidgets() :
        cfg.fwupd ? checkFirmwares() :
                    merge()

    function checkNews() {
        const next = () => cfg.arch ? checkRepos() : cfg.aur ? checkAur() : cfg.flatpak ? checkFlatpak() :
                           cfg.widgets ? checkWidgets() : cfg.fwupd ? checkFirmwares() : merge()
        sts.statusIco = cfg.ownIconsUI ? "status_news" : "news-subscribe"
        sts.statusMsg = i18n("Checking latest news...")
        execute(bash('utils', 'rss', ...feeds), (cmd, out, err, code) => {
            if (handleError(code, err, "news", next)) return
            if (out) {
                const news = JSON.parse(out.trim())
                if (cfg.notifyNews) {
                    const currentLinks = new Set(Array.from(Array(newsModel.count), (_, i) => newsModel.get(i).link))
                    const newItems = news.filter(item => !currentLinks.has(item.link))
                    if (newItems.length > 0) {
                        const title = i18np("%1 new article", "%1 new articles", newItems.length)
                        const body = newItems.map(item => `<b>${item.title}</b>: ${item.article}`).join("\n")
                        notify.send("news", title, body, newItems[0].link)
                    }
                }

                if (newsModel.count === 0) {
                    news.forEach(item => addNewsItem(item))
                } else {
                    let newLinks = news.map(item => item.link)
                    let prevLinks = modelToArray(newsModel).map(item => item.link)

                    news.forEach(item => {
                        if (!prevLinks.includes(item.link)) addNewsItem(item)
                    })

                    for (let i = newsModel.count - 1; i >= 0; --i) {
                        let modelItem = newsModel.get(i)
                        if (!newLinks.includes(modelItem.link)) newsModel.remove(i)
                    }
                }

                saveNews()
            }

            next()
        }, procOpt)
    }

    function checkRepos() {
        const next = () => cfg.aur ? checkAur() : cfg.flatpak ? checkFlatpak() :
                           cfg.widgets ? checkWidgets() : cfg.fwupd ? checkFirmwares() : merge()
        sts.statusIco = cfg.ownIconsUI ? "status_package" : "apdatifier-package"
        sts.statusMsg = i18n("Synchronizing pacman databases...")
        execute(bash('utils', 'syncdb'), (cmd, out, err, code) => {
            if (handleError(code, err, "repositories", next)) return
            sts.statusIco = cfg.ownIconsUI ? "status_package" : "apdatifier-package"
            sts.statusMsg = i18n("Checking system updates...")
            execute(`pacman -Qu --dbpath "${cfg.dbPath}" 2>&1`, (cmd, out, err, code) => {
                if (handleError(code, err, "repositories", next)) return
                const updates = out ? out.trim().split("\n") : []
                makeArchList(updates, "repositories").then(result => {
                    archRepos = result
                    next()
                })
            }, procOpt)
        }, procOpt)
    }

    function checkAur() {
        const next = () => cfg.flatpak ? checkFlatpak() : cfg.widgets ? checkWidgets() : cfg.fwupd ? checkFirmwares() : merge()
        sts.statusIco = cfg.ownIconsUI ? "status_package" : "apdatifier-package"
        sts.statusMsg = i18n("Checking AUR updates...")
        const cmdArg = cfg.wrapper === "pikaur" ? " -Qua --noconfirm" : " -Qua"
        execute(cfg.wrapper + cmdArg, (cmd, out, err, code) => {
            if (handleError(code, err, "aur", next)) return
            const updates = out ? out.trim().split("\n") : []
            makeArchList(updates, "aur").then(result => {
                archAur = result
                next()
            })
        }, procOpt)
    }

    function checkFlatpak() {
        const next = () => cfg.widgets ? checkWidgets() : cfg.fwupd ? checkFirmwares() : merge()
        sts.statusIco = cfg.ownIconsUI ? "status_flatpak" : "apdatifier-flatpak"
        sts.statusMsg = i18n("Synchronizing flatpak appstream...")
        execute("flatpak update --appstream >/dev/null 2>&1", (cmd, out, err, code) => {
            if (handleError(code, err, "flatpak", next)) return
            sts.statusIco = cfg.ownIconsUI ? "status_flatpak" : "apdatifier-flatpak"
            sts.statusMsg = i18n("Checking flatpak updates...")
            makeFlatpakList().then(result => {
                flatpak = result
                next()
            })
        }, procOpt)
    }

    function checkWidgets() {
        const next = () => cfg.fwupd ? checkFirmwares() : merge()
        sts.statusIco = cfg.ownIconsUI ? "status_widgets" : "start-here-kde-plasma-symbolic"
        sts.statusMsg = i18n("Checking widgets updates...")
        execute(bash('widgets', 'check'), (cmd, out, err, code) => {
            if (handleError(code, err, "widgets", next)) return
            widgets = JSON.parse(out.trim())
            next()
        }, procOpt)
    }

    function checkFirmwares() {
        sts.statusIco = cfg.ownIconsUI ? "status_package" : "apdatifier-package"
        sts.statusMsg = i18n("Checking firmware updates...")
        execute("fwupdmgr refresh --force", (cmd, out, err, code) => {
            if (handleError(code, err, "fwupd", merge)) return
            execute("fwupdmgr get-updates --json", (cmd, out, err, code) => {
                if (handleError(code, err, "fwupd", merge)) return
                firmwares = JSON.parse(out).Devices.map(device => ({
                    backend: "fwupd",
                    uid: "fwupd:" + (device.DeviceId || device.Vendor + "-" + device.Name),
                    NM: `${device.Vendor}-${device.Name}`.replace(/ /g, "-").toLowerCase(),
                    RE: "fwupd",
                    DE: device.Releases?.[0]?.Summary || "",
                    LN: device.Releases?.[0]?.Homepage || "",
                    IN: device.Icons?.[0] || "",
                    VO: device.Version || "",
                    VN: device.Releases?.[0]?.Version || ""
                }))

                merge()
            }, procOpt)
        }, procOpt)
    }

    function merge() {
        const sources = ["apt", "snap"].filter(source => cfg[source])
        function checkNext(index) {
            if (token !== sts.checkId) return
            if (index === sources.length) {
                completeMerge()
                return
            }
            const source = sources[index]
            sts.statusMsg = source === "apt" ? i18n("Checking APT updates...") : i18n("Checking Snap updates...")
            sts.statusIco = cfg.ownIconsUI ? "status_package" : "apdatifier-package"
            const next = () => checkNext(index + 1)
            if (!cfg.packages?.python3 || !cfg.packages[source]) {
                handleError(1, i18n("The backend is unavailable: %1", source), source, next)
                return
            }
            execute(helper("check", source, "--mode", cfg.aptUpgradeMode || "auto", "--request-id", token),
                    (cmd, out, err, code) => {
                if (token !== sts.checkId) return
                let result
                try { result = JSON.parse(out) } catch (e) {}
                if (!result || result.schemaVersion !== 1 || !Array.isArray(result.items)) {
                    handleError(code || 1, err || i18n("The backend returned invalid data."), source, next)
                    return
                }
                nativePackages = nativePackages.concat(result.items.map(item => Object.assign({}, item, {
                    NM: item.name, VO: item.installedVersion, VN: item.candidateVersion,
                    RE: item.repository, DE: item.summary, LN: item.homepage, IN: item.icon,
                    RN: item.installReason === "unknown" ? "" : item.installReason,
                    stale: !result.metadataCurrent, synchronizedAt: result.synchronizedAt || 0
                })))
                if (code || result.status !== "ok") {
                    const message = (result.errors || []).map(error => error.message).join("\n")
                    const failure = (result.errors || [])[0] || {}
                    handleError(failure.code || code || 1, message, source, next, failure.category)
                } else next()
            }, procOpt)
        }
        checkNext(0)
    }

    function completeMerge() {
        const list = keys(archRepos.concat(archAur, flatpak, widgets, firmwares, nativePackages))

        const finish = (finalList) => {
            if (token !== sts.checkId) return
            sts.errors.length > 0
                ? runLater(3000, () => {
                    if (token === sts.checkId) isOnline ? finalize(finalList) : stopCheck()
                })
                : finalize(finalList)
        }

        loadIgnorePkgs().then(ignorePatterns => {
            if (!ignorePatterns || ignorePatterns.length === 0) {
                finish(list)
            } else {
                const filtered = list.filter(pkg => pkg.backend !== "pacman" || !ignorePatterns.some(re => re.test(pkg.NM)))
                finish(filtered)
            }
        })
    }
}

function makeArchList(updates, source) {
    return new Promise((resolve) => {
        if (updates.length === 0) {
            resolve([])
        } else {
            const updateRe = /^([A-Za-z0-9@._+-]+)\s+(\S+)\s+->\s+(\S+)/
            const parsed = updates.map(l => l.trim()).map(l => l.match(updateRe)).filter(Boolean)
            if (parsed.length === 0) {
                resolve([])
                return
            }

            const pkgs = parsed.map(m => m[1]).join(' ')
            execute(`LC_ALL=C.UTF-8 pacman -Sl --dbpath "${cfg.dbPath}" | awk 'index($0,"[installed:")>0'`, (cmd, out, err, code) => {
                if (code && handleError(code, err, source, () => resolve([]))) return
                const repositories = out.trim().split('\n')

                execute("LC_ALL=C.UTF-8 pacman -Qi " + pkgs, (cmd, out, err, code) => {
                    if (code && handleError(code, err, source, () => resolve([]))) return
                    const descriptions = out.trim().split('\n\n')

                    execute(bash('utils', 'getIcons', ...parsed.map(match => match[1])), (cmd, out, err, code) => {
                        if (code && handleError(code, err, source, () => resolve([]))) return
                        const icons = out.split('\n')

                        const iconsMap = new Map()
                        icons.map(l => l.split(' ', 2))
                             .filter(([name, icon]) => name && icon)
                             .forEach(([name, icon]) => iconsMap.set(name, icon))

                        const versionsMap = new Map()
                        parsed.forEach(m => versionsMap.set(m[1], { currentVer: m[2], newVer: m[3] }))

                        const repositoriesMap = new Map()
                        repositories.forEach(line => {
                            const [repo, name] = line.trim().split(/\s+/)
                            if (!repositoriesMap.has(name)) {
                                repositoriesMap.set(name, repo)
                            }
                        })

                        const keyMap = {
                            'Name':           'NM',
                            'Description':    'DE',
                            'URL':            'LN',
                            'Groups':         'GR',
                            'Provides':       'PR',
                            'Depends On':     'DP',
                            'Required By':    'RQ',
                            'Optional For':   'OF',
                            'Conflicts With': 'CF',
                            'Replaces':       'RP',
                            'Installed Size': 'IS',
                            'Install Date':   'DT',
                            'Install Reason': 'RN'
                        }

                        const packagesData = descriptions.map(description => {
                            const pkg = {}
                            const lines = description.split('\n')
                            for (const line of lines) {
                                const match = line.match(/^(\w+(?:\s+\w+)*)\s+:\s*(.*)/)
                                if (match) {
                                    const key = match[1].trim()
                                    const value = match[2].trim()
                                    if (value === "None") continue
                                    const mappedKey = keyMap[key]
                                    if (mappedKey) pkg[mappedKey] = value
                                }
                            }

                            if (iconsMap.has(pkg.NM)) pkg.IN = iconsMap.get(pkg.NM)

                            const versions = versionsMap.get(pkg.NM) || {}
                            pkg.VO = versions.currentVer || ""
                            pkg.VN = (versions.newVer === "latest-commit") ? i18n("latest commit") : (versions.newVer || "")
                            pkg.RE = repositoriesMap.get(pkg.NM) || (pkg.NM.endsWith("-git") || pkg.VN === i18n("latest commit") ? "devel" : "aur")

                            if (pkg.RN.includes("Explicitly")) {
                                pkg.RN = "explicit"
                            } else if (!pkg.RQ && !pkg.OF) {
                                pkg.RN = "orphan"
                            } else {
                                pkg.RN = "dependency"
                            }

                            delete pkg.OF

                            return pkg
                        })

                        resolve([...new Map(packagesData.map(item => [item.NM, item])).values()])
                    }, procOpt)
                }, procOpt)
            }, procOpt)
        }
    })
}


function makeFlatpakList() {
    return new Promise((resolve) => {
        execute("flatpak list --app --columns=application,version,active,branch,arch,installation,origin", (cmd, out, err, code) => {
            if (handleError(code, err, "flatpak", () => resolve([]))) return
            const installed = out.trim().split("\n").filter(Boolean).map(line => {
                const [ID, VO, AC, BR, architecture, installation, origin] = line.split("\t").map(entry => entry.trim())
                return { ID, VO, AC, BR, architecture, installation, origin }
            })
            const installations = Array.from(new Set(installed.map(pkg => pkg.installation)))
            const extendedList = []
            function readInstallation(index) {
                if (index === installations.length) { resolve(extendedList); return }
                const installation = installations[index]
                const scope = installation === "user" ? "--user" : installation === "system" || installation === "default"
                    ? "--system" : "--installation=" + installation
                const command = ["flatpak", "remote-ls", scope, "--app", "--updates", "--arch=*",
                    "--columns=name,description,application,version,branch,arch,origin,ref,commit,runtime,installed-size,download-size"]
                    .map(shellQuote).join(" ")
                execute(command, (cmd, out, err, code) => {
                    if (handleError(code, err, "flatpak", () => resolve([]))) return
                    out.split("\n").filter(Boolean).forEach(line => {
                        const [NM, DE, ID, VN, BR, architecture, RE, , CM, RT, IS, DS] = line.split("\t").map(entry => entry.trim())
                        installed.filter(pkg => pkg.installation === installation && pkg.ID === ID && pkg.BR === BR
                            && pkg.architecture === architecture && pkg.origin === RE).forEach(pkg => {
                            const nativeId = pkg.installation + ":" + ID + "/" + architecture + "/" + BR
                            extendedList.push({
                                backend: "flatpak", nativeId, uid: "flatpak:" + nativeId,
                                architecture, installation: pkg.installation,
                                NM: NM.replace(/ /g, "-").toLowerCase(),
                                DE, LN: "https://flathub.org/apps/" + ID,
                                ID, BR, RE, AC: pkg.AC, CM, RT, IS, DS, VO: pkg.VO,
                                VN: pkg.VO === VN ? i18n("latest commit") : VN
                            })
                        })
                    })
                    readInstallation(index + 1)
                }, procOpt)
            }
            readInstallation(0)
        }, procOpt)
    })
}


function sortList(list, byName) {
    if (!list) return

    return list.sort((a, b) => {
        const name = a.NM.localeCompare(b.NM)
        const repo = a.RE.localeCompare(b.RE)
        if (byName || !cfg.sorting) return name

        if (a.IM !== b.IM) return a.IM ? -1 : 1

        const develA = a.RE.includes("devel")
        const develB = b.RE.includes("devel")
        if (develA !== develB) return develA ? -1 : 1

        const aurA = a.RE.includes("aur")
        const aurB = b.RE.includes("aur")
        if (aurA !== aurB) return aurA ? -1 : 1

        return repo || name
    })
}


function refreshListModel(list) {
    list = sortList(applyRules(list || cache)) || []
    sts.count = list.filter(item => !item.state || item.state === "available").length
    setStatusBar()

    if (!list) return

    listModel.clear()
    list.forEach(item => listModel.append(item))
}


function finalize(list) {
    sts.busy = false
    resumeScheduler()

    sts.lastCheck = Date.now()
    saveTimestamp()
    sts.retryAt = 0
    if (!sts.errors.length) sts.retryAttempts = 0
    if (cfg.checkMode !== "manual" && sts.errors.some(isNetworkError) && (sts.retryAttempts || 0) < 3) {
        const attempt = sts.retryAttempts || 0
        sts.retryAttempts = attempt + 1
        sts.retryAt = sts.lastCheck + 30000 * Math.pow(2, attempt)
    }

    if (cfg.notifyErrors && sts.error) {
        const notifyMsg = sts.errors.map(err => `<b>${err.type}</b> => ${err.message} (Exit code ${err.code})`).join('\n\n')
        notify.send("error", i18np("%1 error occurred", "%1 errors occurred", sts.errors.length), notifyMsg)
    }

    if (!list) {
        listModel.clear()
        execute(writeFile("[]", '>', cacheFile))
        cache = []
        sts.count = 0
        setStatusBar()
        return
    }

    if (sts.error && cache.length > 0) {
        var errorTypes = {}
        for (var i = 0; i < sts.errors.length; i++) {
            const type = sts.errors[i].type
            errorTypes[type === "fwupdmgr" ? "fwupd" : type] = true
        }

        var currentNames = {}
        for (var j = 0; j < list.length; j++) currentNames[list[j].uid] = true
        
        var cachedPackages = []
        for (var k = 0; k < cache.length; k++) {
            var cached = cache[k]
            if (currentNames[cached.uid]) continue
            
            if (cached.backend === "pacman" && errorTypes.repositories && cached.RE !== "aur" && cached.RE !== "devel") {
                cachedPackages.push(cached)
            } else if (cached.backend === "pacman" && errorTypes.aur && (cached.RE === "aur" || cached.RE === "devel")) {
                cachedPackages.push(cached)
            } else if (errorTypes.flatpak && cached.backend === "flatpak") {
                cachedPackages.push(cached)
            } else if (errorTypes.widgets && cached.backend === "widgets") {
                cachedPackages.push(cached)
            } else if (errorTypes[cached.backend]) {
                cachedPackages.push(cached)
            }
        }

        cachedPackages.forEach(item => item.stale = true)

        list = list.concat(cachedPackages)
    }

    refreshListModel(list)

    if (cfg.notifyUpdates) {
        const cached = new Map(cache.map(el => [el.uid, updateFingerprint(el)]))
        const newList = applyRules(list).filter(el =>
            !el.stale && (!el.state || el.state === "available") &&
            (!cfg.notifyExplicitOnly || !el.RN || el.RN === "explicit") &&
            (!cached.has(el.uid) || (cfg.notifyEveryBump && cached.get(el.uid) !== updateFingerprint(el)))
        )
    
        if (newList.length > 0) {
            const title = i18np("+%1 new update", "+%1 new updates", newList.length)
            const body = newList.map(pkg => escapeHTML(pkg.NM) + " → " + escapeHTML(pkg.VN || pkg.candidateRevision)).join("\n")
            notify.send("updates", title, body)
        }
    }

    cache = list
    saveCache(cache)
}

function saveCache(list) {
    if (cfg.packages?.python3) {
        // ASCII chunks cannot split a UTF-16 surrogate pair at the process boundary.
        pendingCacheWrite = JSON.stringify(keys(JSON.parse(JSON.stringify(list)))).replace(
            /[\u007f-\uffff]/g, character => "\\u" + ("0000" + character.charCodeAt(0).toString(16)).slice(-4))
        flushCache()
        return
    }
    if (JSON.stringify(list).length > 130000) {
        let start = 0
        const chunkSize = 200
        const json = JSON.stringify(keys(sortList(JSON.parse(JSON.stringify(list)), true))).replace(/},/g, "},\n")
        const lines = json.split("\n")
        while (start < lines.length) {
            const chunk = lines.slice(start, start + chunkSize).join("\n")
            const redir = start === 0 ? ">" : ">>"
            execute(writeFile(chunk, redir, `${cacheFile}_${Math.ceil(start / chunkSize)}`))
            start += chunkSize
        }
        execute(bash('utils', 'combineFiles', cacheFile))
    } else {
        const json = toFileFormat(keys(sortList(JSON.parse(JSON.stringify(list)), true)))
        execute(writeFile(json, '>', cacheFile))
    }
}

function flushCache() {
    if (cacheWriteActive || pendingCacheWrite === null) return
    cacheWriteActive = true
    const data = pendingCacheWrite
    pendingCacheWrite = null
    const token = String(Date.now()) + "-" + Math.random().toString(36).slice(2)
    const size = 16000
    const total = Math.max(1, Math.ceil(data.length / size))
    function write(index) {
        execute(helper("cache-chunk", token, String(index), String(total), "--", data.slice(index * size, (index + 1) * size)),
                (cmd, out, err, code) => {
            if (code || index + 1 === total) {
                cacheWriteActive = false
                if (code) Error(code, err || i18n("Cannot save the package cache."))
                flushCache()
            } else write(index + 1)
        })
    }
    write(0)
}

function updateFingerprint(item) {
    if (item.backend === "snap") return item.candidateRevision
    if (item.backend === "flatpak") return item.CM || item.VN
    return item.VN
}


function setStatusBar() {
    if (sts.count > 0) {
        sts.statusIco = cfg.ownIconsUI ? "status_pending" : "accept_time_event"
        sts.statusMsg = sts.count + " " + i18np("update is pending", "updates are pending", sts.count)
    } else {
        sts.statusIco = cfg.ownIconsUI ? "status_blank" : ""
        sts.statusMsg = ""
    }
}

function resumeScheduler() {
    if (cfg.checkMode !== "manual") {
        scheduler.start()
    }
}

function isNetworkError(error) {
    if (error.type === "snap" && error.category === "service-unavailable") return false
    return error.category === "network-error" ||
        /could not (?:connect|resolve)|network (?:is )?unreachable|network is down|no route to host|temporary failure (?:in |resolving)|connection timed out|connection refused|failed to connect/i
            .test(error.message || "")
}

function searchScheduler(options) {
    if (!isOnline) return
    if (isMetered) return

    const mode = cfg.checkMode
    if (mode === "manual") {
        scheduler.stop()
        return
    }

    const currTime = new Date().getTime()
    const lastCheck = sts.lastCheck || 0
    let nextCheck = null

    if (sts.retryAt) {
        if (options?.simulate) return sts.retryAt
        if (sts.retryAt <= currTime) checkUpdates({ retry: true })
        return
    }

    if (mode === "interval") {
        const interval = parseFloat(cfg.intervalMinutes)
        const intervalMs = interval * 60 * 1000
        nextCheck = lastCheck ? (lastCheck + intervalMs) : (currTime + intervalMs)
    } else if (mode === "daily") {
        const scheduled = new Date(currTime)
        scheduled.setHours(cfg.dailyHour, cfg.dailyMinute, 0, 0)
        if (scheduled.getTime() <= currTime) scheduled.setDate(scheduled.getDate() + 1)
        nextCheck = scheduled.getTime()
    } else if (mode === "weekly") {
        const scheduled = new Date(currTime)
        const targetDay = Number(cfg.weeklyDay)
        const daysAhead = (targetDay - scheduled.getDay() + 7) % 7
        scheduled.setDate(scheduled.getDate() + daysAhead)
        scheduled.setHours(cfg.weeklyHour, cfg.weeklyMinute, 0, 0)
        if (scheduled.getTime() <= currTime) scheduled.setDate(scheduled.getDate() + 7)
        nextCheck = scheduled.getTime()
    }

    options = options || {}
    if (options.simulate) return nextCheck

    if (nextCheck && nextCheck <= (currTime + 10000) && nextCheck > lastCheck) {
        checkUpdates()
    }

    return
}


function getCheckTime() {
    const currTime = new Date().getTime()
    const lastCheck = sts.lastCheck || currTime

    const formatDelta = (ms1, ms2) => {
        const diff = Math.max(0, Math.floor((ms1 - ms2) / 1000))
        const days = Math.floor(diff / 86400)
        const hours = Math.floor((diff % 86400) / 3600)
        const minutes = Math.floor((diff % 3600) / 60)
        const seconds = diff % 60
        const parts = []
        if (days > 0) parts.push([days, i18np("%1 day", "%1 days", days)])
        if (hours > 0) parts.push([hours, i18np("%1 hour", "%1 hours", hours)])
        if (minutes > 0) parts.push([minutes, i18np("%1 minute", "%1 minutes", minutes)])
        if (parts.length === 0 && seconds > 0) return i18n("less than a minute")
        if (seconds > 0) parts.push([seconds, i18np("%1 second", "%1 seconds", seconds)])
        const take = parts.slice(0, 2).map(p => p[1])
        return take.join(' ')
    }

    const lastCheckStr = (currTime > lastCheck) ? `${i18n("Last check:")} ${formatDelta(currTime, lastCheck)} ${i18n("ago")}` : ""

    if (!scheduler.running) return lastCheckStr

    const nextCheck = searchScheduler({ simulate: true })
    if (!nextCheck) return lastCheckStr

    const nextCheckStr = (currTime < nextCheck) ? `${i18n("Next check in:")} ${formatDelta(nextCheck, currTime)}` : ""

    if (lastCheckStr && nextCheckStr) return `${lastCheckStr}\n${nextCheckStr}`
    if (lastCheckStr && !nextCheckStr) return lastCheckStr
    if (!lastCheckStr && nextCheckStr) return nextCheckStr
}


function setIndex(value, arr) {
    let index = 0
    for (let i = 0; i < arr.length; i++) {
        if (arr[i]["value"] == value) {
            index = i
            break
        }
    }
    return index
}

const defaultIcon = "apdatifier-plasmoid"
function setIcon(icon) {
    return icon === "" ? defaultIcon : icon
}


function applyRules(list) {
    const rules = !cfg.rules ? [] : JSON.parse(cfg.rules)

    list.forEach(el => {
        el.IC = el.IN ? el.IN : el.ID ? el.ID : "apdatifier-package"
        el.EX = false
        el.IM = false
    })

    function applyRule(el, rule) {
        if (rule.backend && rule.backend !== el.backend) return
        const types = {
            'name'  : () => el.NM === rule.value || el.nativeId === rule.value || el.uid === rule.value,
            'regex' : () => { try { return new RegExp(rule.value).test(el.NM) } catch(e) { return false } }
        }

        if (types[rule.type] && types[rule.type]()) {
            el.IC = rule.icon
            el.EX = rule.excluded
            el.IM = rule.important
        }
    }

    rules.forEach(rule => list.forEach(el => applyRule(el, rule)))
    return list.filter(el => !el.EX)
}


function keys(list) {
    const keysList = ["NM", "VO", "VN", "RE", "DE", "LN", "IN", "TP", "GR", "PR", "DP", "RQ", "CF", "RP", "IS", "DT", "RN", "ID", "BR", "AC", "CM", "RT", "DS", "CN", "AU",
                      "backend", "uid", "nativeId", "architecture", "installedRevision", "candidateRevision", "state", "installation"]

    list.forEach(el => {
        keysList.forEach(key => {
            if (!el.hasOwnProperty(key)) el[key] = ""
        })
        if (!el.backend) el.backend = el.CN ? "widgets" : el.ID ? "flatpak" : el.RE === "fwupd" ? "fwupd" : "pacman"
        if (!el.nativeId) el.nativeId = el.backend === "widgets" ? String(el.CN || el.NM) : el.ID || el.NM
        if (!el.uid) {
            el.uid = el.backend + ":" + el.nativeId
            el.legacyIdentity = true
        }
        el.legacyIdentity = Boolean(el.legacyIdentity)
        if (!el.state) el.state = "available"
        el.stale = Boolean(el.stale)
        el.synchronizedAt = Number(el.synchronizedAt || 0)
        if (!/^https?:\/\//.test(el.LN)) el.LN = ""

        if (el.hasOwnProperty("IC")) delete el["IC"]
        if (el.hasOwnProperty("EX")) delete el["EX"]
        if (el.hasOwnProperty("IM")) delete el["IM"]
    })

    return list
}


function switchScheduler() {
    if (cfg.checkMode === "manual" || sts.busy) return
    scheduler.running ? scheduler.stop() : scheduler.start()
}

function toFileFormat(obj) {
    return JSON.stringify(obj, null, 2)
}

function validJSON(string, file) {
    try {
        const json = JSON.parse(string)
        if (json && typeof json === "object") return json
    }
    catch (e) {
        file ? Error(1, `JSON data at ${file} is corrupted or broken and cannot be processed`)
             : Error(1, "JSON data is broken and cannot be processed")
    }

    return false
}

function isValidFeedUrl(value) {
  return /^https?:\/\/\S+$/i.test((value || "").trim())
}

function parseCustomFeeds(value) {
  return String(value || "")
    .split(/[\n|]/)
    .map(feed => feed.trim())
    .filter(isValidFeedUrl)
}

function serializeCustomFeeds(value) {
  return (Array.isArray(value) ? value : parseCustomFeeds(value))
    .map(feed => feed.trim())
    .filter((feed, index, feeds) => isValidFeedUrl(feed) && feeds.indexOf(feed) === index)
    .join("|")
}



function modelToArray(model) {
    const array = new Array(model.count)
    for (let i = 0; i < model.count; i++) {
        array[i] = model.get(i)
    }
    return array
}

function findInsertIndex(news) {
    const n = newsModel.count
    let firstRemoved = n

    for (let i = 0; i < n; i++) {
        if (newsModel.get(i).removed) {
            firstRemoved = i
            break
        }
    }

    const start = news.removed ? firstRemoved : 0
    const end = news.removed ? n : firstRemoved

    for (let i = start; i < end; i++) {
        if (newsModel.get(i).timestamp < news.timestamp)
            return i
    }

    return end
}

function saveNews() {
    execute(writeFile(toFileFormat(modelToArray(newsModel)), '>', newsFile))
}

function addNewsItem(news) {
    newsModel.insert(findInsertIndex(news), news)
}

function removeNewsItem(index) {
    const item = newsModel.get(index)
    if (!item || item.removed) return

    let to = findInsertIndex({ timestamp: item.timestamp, removed: true })
    if (to > index) to--

    newsModel.move(index, to, 1)
    newsModel.setProperty(to, "removed", true)

    saveNews()
}
