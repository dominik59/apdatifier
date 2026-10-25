# Change request: APT and Snap

| Field | Value |
| --- | --- |
| Request ID | CR-APT-SNAP-001 |
| Revision | 1.9 |
| Date | 2026-10-25 |
| Product | Apdatifier |
| Source version | 2.10.0 |
| Source commit | e971e7c3ff568e061b5ff8d066411135dc4c7219 |
| Status | Implemented; full platform acceptance remains open |
| Product source changes | Owner approved implementation on 2026-10-24 |
| Document language | English |
| Language reference | ASD-STE100, Issue 9, 2025-01-15 |
| Language review | Structure review complete; full dictionary review open |

## 1. Purpose and authority

This document gives the complete change request.
No previous conversation is necessary.
All repository paths in this document start at the repository root.

The owner approved creation of this document.
The owner then requested implementation on 2026-10-24.
That request permits product source changes and local development tests.
It does not permit host package changes or deployment.

AUTH-01. Use the source-change approval recorded above for this implementation.

AUTH-02. Keep unrelated local changes.

AUTH-03. Do not install tools to prepare or review this document.

Each requirement with an identifier is mandatory.
The command tables define the required native command arguments.
They do not give permission to run system changes.

## 2. Owner decisions

The owner selected the following scope:

| Item | Decision |
| --- | --- |
| Functions | Match the applicable functions of the current application |
| Desktop | Plasma 6 |
| Initial systems | Kubuntu 26.04; Ubuntu 26.04 with Plasma 6; Debian 13 with Plasma 6; KDE neon with Plasma 6 |
| Distribution method | KDE Widget Store |
| Background APT data | Current repository data, without a password prompt |
| System changes | The selected terminal and the current administrator authorization method |
| Snap settings | Keep the existing snapd settings |
| Additional dependencies | Do not require installation of additional tools |
| Python | System Python 3 and its standard library are acceptable |
| Snap availability | Use Snap only where snapd is already installed |

The current application uses a terminal for system changes.
Its default administrator command is sudo.
This change keeps that interaction.

## 3. Language and terms

ASD-STE100 Issue 9 is the language reference.
The standard contains writing rules and a controlled dictionary.
Short sentences alone do not prove full conformity. [S01]

LANG-01. Use a maximum of 20 words in each procedural sentence.

LANG-02. Use a maximum of 25 words in each descriptive sentence.

LANG-03. Give one instruction in each procedural sentence.

LANG-04. Use the imperative form for instructions.

LANG-05. Use the active voice.

LANG-06. Use one technical term for each concept.

LANG-07. Keep exact spelling for commands, paths, identifiers, and source titles.

LANG-08. Complete the independent dictionary review before a full ASD-STE100 conformity declaration.

The following technical nouns have the meanings given below.

| Technical noun | Meaning |
| --- | --- |
| Backend | The component that connects Apdatifier to one package system |
| Candidate | The package version that the native package system selects |
| Capability | An operation that a backend can perform |
| Check result | Data from one attempt to find package updates |
| Current result | A result from a complete, successful repository refresh and update calculation |
| Identity | The stable key for one installed package instance |
| Metadata | Package information that does not contain the installed package files |
| Native command | A command from APT, dpkg, or Snap |
| Old result | The last complete result after a later attempt fails |
| Operation exclusion | A rule that keeps a package unchanged during one manual operation |
| Package hold | A persistent restriction in the native package system |
| Private indexes | APT repository indexes in the user's Apdatifier cache |
| Revision | The Snap identifier for one package upload |
| Transaction | One native package operation and its result |
| Update fingerprint | The identity and the native candidate version or revision |

The technical verbs below refer to software processes.
Their technical meanings apply only to this document.

| Technical verb | Meaning |
| --- | --- |
| Configure | Set software configuration values |
| Download | Receive data from a remote system |
| Install | Add a software package through its native package system |
| Parse | Read structured data into fields |
| Refresh | Get current metadata through the native package system |
| Resolve | Find a valid set of package dependencies |
| Return | Give output data to the software caller |
| Run | Start a software process |
| Save | Write software data for later use |
| Upgrade | Install a candidate for an installed package |
| Validate | Determine whether data meets specified software rules |

## 4. Current source evidence

The source version has backends for pacman, AUR, Flatpak, Plasma widgets, and firmware.
README.md describes the current functions and optional dependencies.
package/metadata.json requires Plasma 6.

| Source location | Current behavior | Necessary change |
| --- | --- | --- |
| package/contents/tools/tools.js:161 | Reads dependency results by position | Add named capability data |
| package/contents/tools/tools.js:194 | Routes single updates through Flatpak or widget fields | Route through backend and identity |
| package/contents/tools/tools.js:209 | Compares installed packages by name | Compare native identities |
| package/contents/tools/tools.js:301 | Builds pacman ignore arguments | Add backend-specific operation exclusions |
| package/contents/tools/tools.js:316 | Runs the update search sequence | Add APT and Snap |
| package/contents/tools/tools.js:650 | Uses names and field tests for cache decisions | Use backend state and update fingerprints |
| package/contents/tools/sh/utils:315 | Refreshes a private pacman database | Add a separate private APT refresh |
| package/contents/tools/sh/utils:341 | Reads installed versions for current backends | Add APT and Snap identities |
| package/contents/tools/sh/utils:519 | Prints tools and terminals in a fixed order | Keep dependency consumers consistent |
| package/contents/tools/sh/upgrade | Runs upgrades and user scripts | Add APT, Snap, and explicit operation results |
| package/contents/tools/sh/management | Uses pacman operations and fzf | Add APT and Snap menus without fzf |
| package/contents/ui/main.qml | Requires pacman for the management action | Use management capabilities |
| package/contents/ui/representation/Expanded.qml | Builds source menus from current flags | Add the new backend actions |
| package/contents/ui/scrollview/Updates.qml | Shows single-update actions through ID or CN | Use backend capabilities |
| package/contents/config/main.xml | Defines current settings | Add settings and migration |
| .github/workflows/build.yml | Builds translations and the plasmoid | Add applicable automated tests |

Line numbers refer to the source commit above.
Function names remain the primary references after source changes.

## 5. Scope

SCOPE-01. Add update discovery, package details, notifications, and terminal upgrades for APT and Snap.

SCOPE-02. Add package search, installation, installed-package lists, and removal for both backends.

SCOPE-03. Add package history, cache operations, and operations that install an earlier version.

SCOPE-04. Keep the current pacman, AUR, Flatpak, widget, and firmware functions.

SCOPE-05. Keep the applet identifier com.github.exequtic.apdatifier.

SCOPE-06. Include all new application files inside the plasmoid.

SCOPE-07. Do not add a system service or a privileged helper.

SCOPE-08. Do not add Plasma 5 support.

SCOPE-09. Do not add distribution release upgrades.

SCOPE-10. Do not add repository editing or signing-key installation.

SCOPE-11. Do not add automatic package installation.

SCOPE-12. Do not change native update schedules.

SCOPE-13. Do not create artificial equivalents for Arch-only functions.

## 6. Runtime architecture and dependencies

The existing QML interface and JavaScript coordinator remain.
A bundled Python helper supplies structured data for the new backends.
The existing Bash terminal entry points start foreground operations.

Ubuntu 26.04 includes Python 3 through ubuntu-minimal.
The python3 package depends on the standard library. [S02, S03]

DEP-01. Use /usr/bin/python3 and its standard library for the new helper.

DEP-02. Use Python syntax available in Python 3.10 or later.

DEP-03. Use native commands from the existing apt and dpkg installations.

DEP-04. Use the existing snap command for foreground Snap operations.

DEP-05. Use Python socket and http.client for local snapd API requests.

DEP-06. Use Python json for JSON input and output.

DEP-07. Use Python fcntl for application locks.

DEP-08. Do not require jq, curl, wget, fzf, python3-apt, requests, or a Python virtual environment.

DEP-09. Do not require PackageKit, new KAuth components, or a compiler.

DEP-10. Do not install missing dependencies.

DEP-11. Show the reason when a dependency is absent.

DEP-12. Disable only the capabilities that need the absent dependency.

DEP-13. Keep existing dependency rules for unrelated functions.

DEP-14. Start the helper without Python user-site modules.

DEP-15. Do not create Python bytecode files in the installed plasmoid.

DEP-16. Find named capabilities without dependence on output line positions.

DEP-17. Keep terminal detection correct after dependency changes.

APT and dpkg supply apt-get, apt-cache, apt-config, apt-mark, dpkg, dpkg-query, and dpkg-deb.
These commands form the allowed native APT tool set.
The existing terminal and administrator command remain necessary for system changes.

ARCH-01. Keep machine output separate from terminal output.

ARCH-02. Return one JSON document for each helper request.

ARCH-03. Return diagnostic text through stderr.

ARCH-04. Use subprocess argument lists without shell interpretation inside the helper.

ARCH-05. Use shell quotation marks around the helper path at the existing QML-to-shell boundary.

ARCH-06. Use one tested argument encoder at that boundary.

ARCH-07. Do not pass package descriptions or display names as shell code.

ARCH-08. Do not run the plasmoid or the Python helper as root.

ARCH-09. Apply administrator authorization only to the native command that needs it.

ARCH-10. Keep the current configurable administrator command.

## 7. Capability detection and settings

CONF-01. Identify APT through the native system type and a readable dpkg database.

CONF-02. Do not activate APT solely because an apt-get executable exists.

CONF-03. Identify Snap independently of the native distribution backend.

CONF-04. Let Snap operate with either APT or pacman.

CONF-05. Show an absent snapd installation and an unavailable snapd service as different states.

CONF-06. Keep the user's enable setting when a service is temporarily unavailable.

CONF-07. Add the settings below.

| Setting | Type | Default | Meaning |
| --- | --- | --- | --- |
| apt | Boolean | false | Enable APT checks |
| snap | Boolean | false | Enable Snap checks |
| aptUpgradeMode | Enumeration | auto | Select auto, safe, or full |

CONF-08. Use full mode for KDE neon when aptUpgradeMode is auto.

CONF-09. Use safe mode for the other initial systems when aptUpgradeMode is auto.

CONF-10. Do not permit safe mode on KDE neon.

CONF-11. Give the reason when a mode is unavailable.

CONF-12. Save new settings through the existing configuration path.

CONF-13. Use APDATIFIER_CONFIG_DIR, APDATIFIER_CACHE_DIR, XDG_CONFIG_HOME, and XDG_CACHE_HOME to select the configured paths.

CONF-14. Do not change existing user settings during migration.

CONF-15. Keep the existing automatic-check schedule and connection settings effective.

CONF-16. Do not start background downloads on a metered connection when the user prohibits them.

The disabled defaults match the current optional-backend pattern.
The user enables the new sources in the application settings.

## 8. APT background checks

APT permits separate paths for repository indexes and the dpkg status file. [S04]
The private-index design needs a prototype before the full implementation.
The owner requires current data without background administrator authorization.

APT-01. Refresh APT metadata as the desktop user.

APT-02. Store private indexes below the resolved Apdatifier cache directory.

APT-03. Use the real system dpkg status database for update calculation.

APT-04. Keep system package holds and automatic-install data as read-only inputs.

APT-05. Read the system source files, including Deb822 .sources files.

APT-06. Keep system architecture, pinning, proxy, and authentication settings.

APT-07. Keep native repository signature and validity checks.

APT-08. Do not use fakeroot.

APT-09. Do not disable native authentication or signature checks.

APT-10. Do not change /etc/apt, /var/lib/apt, /var/cache/apt, or the dpkg database during background checks.

APT-11. Redirect all writable checker paths into the user's cache.

APT-12. Do not redirect the entire system root or the entire APT state tree.

APT-13. Load checker-specific configuration after the normal APT configuration.

APT-14. Clear update hooks that would write outside the private checker area.

APT-15. Keep those hook changes local to the checker process.

APT-16. Keep normal system hooks for foreground native operations.

APT-17. Use one application lock for private APT refreshes.

APT-18. Give a busy result when another instance holds that lock.

APT-19. Do not remove an active lock file.

APT-20. Use bounded network timeouts for background requests.

APT-21. Keep background checks cancelable.

APT-22. Stop only the process group for the canceled checker.

APT-23. Give an incomplete repository refresh a partial result status.

APT-24. Do not report an incomplete refresh as a current empty result.

APT-25. Keep the last complete result after a later refresh failure.

APT-26. Show the age and failure state of that old result.

APT-27. Write the successful refresh time only after the complete operation succeeds.

APT-28. Do not silently use system indexes when private refresh fails.

APT-29. Report unreadable source configuration or key material as a capability error.

The checker configuration can use Dir::State::lists and private cache paths.
The checker can disable generated binary caches.
The implementation must inspect the effective writable paths.

APT-30. Use apt-get simulation to calculate the selected upgrade plan.

APT-31. Use the same upgrade mode for discovery and execution.

APT-32. Set LC_ALL=C and LANGUAGE=C for machine-oriented command output.

APT-33. Do not parse apt list output.

APT-34. Parse documented simulation operations separately from explanatory messages.

APT-35. Count updates only for installed packages with a selected candidate change.

APT-36. Keep new dependencies and removals separate from the update count.

APT-37. Keep native holds, pinning, and phased-update decisions effective.

APT-38. Do not infer the full transaction from version differences alone.

APT-39. Use dpkg version comparison when an explicit version comparison is necessary.

APT-40. Keep the architecture in each APT identity.

APT-41. Get package metadata in batches.

APT-42. Keep package versions as exact native strings.

APT-43. Do not accept unknown simulation records that could change the transaction meaning.

APT-44. Do parser tests against each supported APT version.

APT-45. Use --error-on=any for every private APT index refresh.

APT-46. Keep the previous synchronization time after any refresh error, including a transient error.

APT-47. Do not calculate a new update plan from an incomplete index refresh.

APT recommends apt-get and apt-cache for scripts. [S05]
Simulation does not lock the system state. [S06]
The preview is therefore not a reservation of the later transaction.
The --error-on=any option includes transient errors. [S06]

## 9. APT foreground operations

| Operation | Native command or command family |
| --- | --- |
| Refresh system indexes | sudo apt-get --error-on=any update |
| Safe upgrade | sudo apt-get --no-remove --with-new-pkgs upgrade |
| Full upgrade | sudo apt-get dist-upgrade |
| Package installation | sudo apt-get install PACKAGE |
| Single installed-package upgrade, safe mode | sudo apt-get --no-remove install --only-upgrade PACKAGE |
| Single installed-package upgrade, full mode | sudo apt-get install --only-upgrade PACKAGE |
| Package removal | sudo apt-get remove PACKAGE |
| Configuration removal | sudo apt-get purge PACKAGE |
| Unused dependencies | sudo apt-get autoremove |
| Complete archive cache removal | sudo apt-get clean |
| Obsolete archive cache removal | sudo apt-get autoclean |
| Available-package search | apt-cache search QUERY |
| Installed-package list | dpkg-query with an explicit output format |
| Manual-install list | apt-mark showmanual |
| Automatic-install list | apt-mark showauto |
| Package holds | apt-mark showhold |
| Earlier version or local archive | apt-get install with a selected version or local DEB |

sudo in this table means the current administrator command.
Safe mode permits new dependencies.
Safe mode does not permit package removals.
The --only-upgrade option alone does not prohibit removal of other packages.
The --no-remove option stops APT if the transaction needs any package removal. [S06]
Full mode can permit package removals. [S06]
KDE neon requires the full-upgrade behavior. [S07]

EXEC-01. Start foreground operations in the selected terminal.

EXEC-02. Refresh system indexes before an APT install or upgrade.

EXEC-03. Stop the APT operation if the necessary system refresh fails.

EXEC-04. Calculate the final plan from current system state.

EXEC-05. Show upgrades, new dependencies, removals, and version decreases.

EXEC-06. Get user confirmation before the native change.

EXEC-07. Do not add automatic yes options.

EXEC-08. Keep native configuration-file questions available in the terminal.

EXEC-09. Keep package removal, purge, autoremove, and cache removal as separate user actions.

EXEC-10. Do not add those actions to a normal upgrade.

EXEC-11. Get explicit confirmation before a version decrease.

EXEC-12. Read local DEB metadata with dpkg-deb before a local-archive installation.

EXEC-13. Use APT dependency resolution for local DEB installation.

EXEC-14. Do not replace APT dependency resolution with dpkg -i.

EXEC-15. Wait for native package locks or report a busy state.

EXEC-16. Do not remove APT or dpkg lock files.

EXEC-17. Do not kill another package manager.

EXEC-18. Do not apply a hard process timeout during a foreground dpkg operation.

EXEC-19. Show native interruption and recovery information after an incomplete transaction.

EXEC-20. Do not run automatic repair commands.

EXEC-21. Use --error-on=any for every foreground APT index refresh.

EXEC-22. Use --no-remove for every safe-mode upgrade, including a single-package upgrade.

EXEC-23. Use --no-remove for the corresponding safe-mode simulations.

EXEC-24. Stop a safe-mode upgrade if the selected transaction needs any package removal.

Removing dpkg lock files is not a correct lock recovery method. [S08]

## 10. Snap discovery and operations

The local snapd API uses /run/snapd.socket.
Python standard-library HTTP and Unix sockets can access this API. [S09, S10]

SNAP-01. Read installed packages through GET /v2/snaps.

SNAP-02. Read refresh candidates through GET /v2/find?select=refresh.

SNAP-03. Use Unix sockets for API transport.

SNAP-04. Do not contact a hard-coded Snap Store endpoint directly.

SNAP-05. Set connection and response timeouts.

SNAP-06. Validate HTTP status and the snapd response envelope.

SNAP-07. Keep an API error distinct from an empty package list.

SNAP-08. Do not request interactive authorization during background checks.

SNAP-09. Do not request Snap Store login for ordinary public-package checks.

SNAP-10. Report private-package authorization limits without a background prompt.

SNAP-11. Match installed packages and candidates by native instance identity.

SNAP-12. Keep both installed and candidate revisions.

SNAP-13. Use the candidate that snapd selects for the current channel.

SNAP-14. Do not select a candidate through lexical version comparison.

SNAP-15. Do not select a candidate through numeric revision comparison.

SNAP-16. Keep the current channel, confinement mode, and native holds.

SNAP-17. Keep refresh.timer, refresh.hold, refresh.metered, and refresh.retain unchanged.

SNAP-18. Do not target an individually held package during an ordinary bulk upgrade.

SNAP-19. Get separate confirmation before a deliberate manual hold override.

SNAP-20. Use No as the default answer for a hold override.

SNAP-21. Find the global hold state before a manual refresh.

SNAP-22. If background access cannot supply hold state, read it in the authorized terminal operation.

SNAP-23. If hold state remains unknown, stop the affected operation.

SNAP-24. Explain that a manual refresh can override an automatic-refresh hold.

SNAP-25. Show running-application restrictions from snapd.

SNAP-26. Do not terminate running applications to permit a refresh.

SNAP-27. Refresh the displayed state after native automatic updates.

SNAP-28. Do not change desktop notification settings owned by snapd.

SNAP-29. Do not report a background transaction as complete merely because a client process exits.

SNAP-30. Read the transaction result when the API permits it.

SNAP-31. If the transaction result is unavailable, show an unknown result until a later state check.

SNAP-32. Keep Snap base packages and content packages identifiable in package lists.

The snapd refresh endpoint currently permits ordinary read access. [S11]
The implementation must test access on the installed snapd versions.
Revision numbers identify package uploads.
They do not define release order. [S12]

| Operation | Native command or command family |
| --- | --- |
| Search | snap find QUERY |
| Installed packages | GET /v2/snaps or snap list |
| Bulk refresh | sudo snap refresh |
| Selected refresh | sudo snap refresh PACKAGE |
| Install | sudo snap install PACKAGE |
| Remove | sudo snap remove PACKAGE |
| Return to an earlier revision | sudo snap revert PACKAGE |
| Remove a selected inactive revision | sudo snap remove PACKAGE --revision=REVISION |
| Recent changes | snap changes and snap tasks CHANGE_ID |

SNAP-33. Get confirmation before installation, removal, or a revision return.

SNAP-34. Keep default removal snapshots.

SNAP-35. Make removal without a snapshot a separate explicit action.

SNAP-36. Explain the data limits of snap revert before that action.

SNAP-37. Get explicit consent before an installation that needs classic confinement.

SNAP-38. Do not add --classic, --devmode, or --dangerous automatically.

SNAP-39. Do not remove the active revision during cache operations.

SNAP-40. Show the effect on revision return before an inactive-revision removal.

SNAP-41. Use native commands for revision removal.

SNAP-42. Do not delete files directly from snapd storage.

Individual and global Snap holds have different effects on manual refreshes. [S13]
Snap removal and revision return also have different data effects. [S14]
Classic confinement requires explicit user consent. [S15]

## 11. Package management interface

UI-01. Keep the current terminal-based management entry point.

UI-02. Enable management when an available backend has management capabilities.

UI-03. Do not require pacman for APT or Snap management.

UI-04. Add an explicit source selector.

UI-05. Show only operations that the selected backend can perform.

UI-06. Include search, pagination, selection, details, and cancellation without fzf.

UI-07. Let the user select packages through validated item numbers.

UI-08. Show the selected native identities before a change.

UI-09. Validate every selection against the current result set.

UI-10. Use a search query for Snap Store discovery.

UI-11. Do not require a complete Snap Store catalog download.

UI-12. Keep APT manual-install information distinct from automatic-install information.

UI-13. Do not label Snap packages as APT-style orphan dependencies.

UI-14. Keep AUR rebuild and Arch mirror functions limited to their existing backends.

UI-15. Read available history without a new database service.

UI-16. Use the Python gzip module when the available APT history needs it.

UI-17. Do not infer unavailable history entries.

UI-18. Add APT and Snap to applicable check and upgrade menus.

UI-19. Show the backend in package details.

UI-20. Show Snap revisions when version text alone does not explain a change.

UI-21. Keep existing generic icons available as fallbacks.

UI-22. Put new interface strings through the existing translation mechanism.

UI-23. Keep unrelated optional features available with their current dependency rules.

## 12. Data, cache, rules, and notifications

The helper result format has a schema version.
The JavaScript coordinator maps helper fields into existing QML roles.
New backend data does not reuse the Flatpak-specific meaning of ID.

DATA-01. Add backend and uid fields to the shared package model.

DATA-02. Use apt:NAME:ARCHITECTURE for APT identities.

DATA-03. Use snap:INSTANCE_NAME for Snap identities.

DATA-04. Give existing backends equivalent stable identities.

DATA-05. Include the necessary installation scope and native reference in Flatpak identities.

DATA-06. Use uid for cache merge, installed-state comparison, and action routing.

DATA-07. Use the update fingerprint for notification deduplication.

DATA-08. Include the candidate revision in Snap update fingerprints.

DATA-09. Do not deduplicate different backends through display names.

DATA-10. Keep successful backend results when another backend fails.

DATA-11. Keep the last complete result for a failed backend.

DATA-12. Give that retained result an old-result indication.

DATA-13. Do not generate new-update notifications solely from retained old data.

DATA-14. Write cache files through an atomic file replacement.

DATA-15. Keep the old cache if a new cache write fails.

DATA-16. Read the current cache format during migration.

DATA-17. Add identities without loss of existing package details.

DATA-18. Keep backward-compatible defaults for absent fields.

DATA-19. Use the same QML roles across all package records.

DATA-20. Keep an empty successful result distinct from every error state.

The following JSON structure defines the helper boundary.
The sample values illustrate a successful APT result.

~~~json
{
  "schemaVersion": 1,
  "backend": "apt",
  "status": "ok",
  "checkedAt": 1792800000000,
  "synchronizedAt": 1792800000000,
  "metadataCurrent": true,
  "items": [
    {
      "uid": "apt:example:amd64",
      "backend": "apt",
      "nativeId": "example:amd64",
      "name": "example",
      "architecture": "amd64",
      "installedVersion": "1.0-1",
      "candidateVersion": "1.1-1",
      "installedRevision": "",
      "candidateRevision": "",
      "repository": "example-source",
      "summary": "Example package",
      "homepage": "",
      "icon": "",
      "installReason": "explicit",
      "state": "available"
    }
  ],
  "errors": []
}
~~~

| Field | Required values or meaning |
| --- | --- |
| schemaVersion | Integer format version |
| backend | apt or snap |
| status | ok, partial, busy, unavailable, error, or canceled |
| checkedAt | Attempt time in Unix milliseconds |
| synchronizedAt | Last complete metadata synchronization time; null before first success |
| metadataCurrent | True only after a complete successful metadata refresh |
| items | Complete package records for this result |
| installReason | explicit, dependency, orphan, or unknown |
| state | available, held, blocked, or unknown |
| errors | Structured backend errors |

DATA-21. Keep native error codes in structured error records.

DATA-22. Include an error category and an understandable message.

DATA-23. Give a nonzero process exit a failure status even when stderr is empty.

DATA-24. Do not accept malformed JSON or unknown schema versions.

DATA-25. Do not describe unknown installation reasons as explicit installations.

RULE-01. Add an optional backend scope to package rules.

RULE-02. Keep existing visual rules applicable through their current name and regular-expression behavior.

RULE-03. Keep legacy ignore rules limited to their existing pacman upgrade meaning.

RULE-04. Use explicit backend scope for new APT and Snap operation exclusions.

RULE-05. Keep visual exclusion separate from operation exclusion.

RULE-06. Keep persistent native package holds unchanged when a widget rule changes.

RULE-07. Use transaction-specific APT solver constraints for an APT operation exclusion.

RULE-08. Prove that each excluded APT package remains unchanged before execution.

RULE-09. If the solver cannot honor an exclusion, stop the APT transaction.

RULE-10. Do not silently upgrade an excluded package to complete another update.

RULE-11. Keep Snap operation exclusions local to the manual action.

RULE-12. Keep native Snap holds effective during candidate selection.

RULE-13. Do not implement widget exclusions through persistent hold changes.

## 13. Foreground lifecycle

LIFE-01. Keep the selected terminal, optional tmux behavior, and idle-inhibition setting.

LIFE-02. Run the pre-upgrade user script once before the selected upgrade sequence.

LIFE-03. Do not require the Arch backend to run that script.

LIFE-04. Run the post-upgrade user script once after that sequence.

LIFE-05. Write each native operation result before the terminal wait-for-close step.

LIFE-06. Show success, failure, cancellation, and partial completion separately.

LIFE-07. Do not infer transaction success from process-name matching alone.

LIFE-08. Do not infer transaction success from terminal closure.

LIFE-09. Continue independent backend stages after one stage fails.

LIFE-10. Give the complete sequence a partial result status when any stage fails.

LIFE-11. Stop later stages when the user cancels the complete sequence.

LIFE-12. Refresh affected package states after each completed native operation.

LIFE-13. Keep background checks separate from active foreground transactions.

LIFE-14. Do not interrupt an active native transaction when a check is canceled.

LIFE-15. Use available native restart indications after APT operations.

LIFE-16. On Ubuntu, read /run/reboot-required and its package list when present.

LIFE-17. Do not infer that no restart is necessary from an absent marker.

LIFE-18. Do not reuse the Arch critical-package list as the APT restart policy.

LIFE-19. Keep restart suggestions separate from restart execution.

LIFE-20. Keep the user's existing restart preference.

## 14. Input, permissions, and diagnostics

SAFE-01. Validate native identifiers before an operation.

SAFE-02. Validate names, architectures, versions, revisions, and file paths separately.

SAFE-03. Do not accept arbitrary command options through a package selection.

SAFE-04. Do not evaluate repository data as code.

SAFE-05. Use only the Python standard library for new helper imports.

SAFE-06. Keep private directories owned by the desktop user.

SAFE-07. Do not use a shared fixed /tmp directory for new backend state.

SAFE-08. Use unique temporary paths for each operation.

SAFE-09. Do not accept unexpected symlinks at private write targets.

SAFE-10. Keep checker configuration out of privileged APT command execution.

SAFE-11. Pass only validated operation constraints to privileged native commands.

SAFE-12. Keep source credentials, authorization tokens, and passwords out of notifications and logs.

SAFE-13. Convert special package-text characters to the correct QML display form.

SAFE-14. Do not add sudoers or polkit policy changes.

SAFE-15. Do not store administrator passwords.

SAFE-16. Do not silently change a native hold, package pin, or repository trust setting.

SAFE-17. Report unsupported features without installation instructions that run automatically.

SAFE-18. Build each native selector from validated fields in the syntax of its native command.

SAFE-19. For a versioned APT package selector, use NAME:ARCH=VERSION as one subprocess argument.

SAFE-20. Pass each completed selector or file path as one subprocess argument without shell interpretation.

SAFE-21. Do not let a selector introduce command options, package patterns, or extra arguments.

APT combines a package name, architecture, and selected version in one selector argument. [S06]
Separate field validation does not require separate subprocess arguments.

### 14.1 Background network recovery

NET-01. Retry failed automatic checks after detected network failures.

NET-02. Use retry delays of 30, 60, and 120 seconds after each failed check.

NET-03. Stop this retry sequence after three additional attempts.

NET-04. Use the normal schedule after the retry sequence ends.

NET-05. Do not start automatic retries in manual mode.

NET-06. Keep the user's connectivity and metered connection settings effective during retries.

NET-07. Clear the retry sequence after success, explicit cancellation, or a new independent check.

NET-08. Keep native error codes and useful network evidence from stdout and stderr.

NET-09. Keep source credentials and authorization tokens out of that evidence.

NET-10. Keep previous complete results during failed retries, as DATA-11 requires.

NET-11. Do not show "System updated" for an empty list when a source check failed.

NET-12. Do not infer a network failure from a missing Release file or invalid signature alone.

NET-13. Keep native repository authentication effective during retries.

NET-14. Do not change the user's connectivity setting to implement network recovery.

The existing connectivity check can delay checks until Qt reports an online connection.
The user can enable it under Settings -> General -> Misc -> Network.
An online indication does not prove access to each update server. [S28]
APT requires authenticated repository metadata. [S29]

## 15. Implementation sequence

STEP-01. Read this request and the current repository instructions.

STEP-02. Make sure that owner approval permits product source changes.

STEP-03. Write the actual source commit and local changes in the implementation report.

STEP-04. Prove the private APT refresh design in a disposable test system.

STEP-05. Prove Snap API access with the permitted standard-library modules.

STEP-06. Resolve operation exclusions through native solver and hold tests.

STEP-07. Add the helper result format and backend capabilities.

STEP-08. Add stable identities and cache migration.

STEP-09. Add APT and Snap discovery.

STEP-10. Add foreground operations and lifecycle results.

STEP-11. Add management menus without fzf.

STEP-12. Add settings, interface actions, and translations.

STEP-13. Add automated tests and applicable CI steps.

STEP-14. Change README.md and package descriptions to include the new functions.

STEP-15. Complete the acceptance tests.

STEP-16. Report the exact changes, test evidence, and remaining limitations.

The prototype has three exit conditions:

- APT gets current metadata without administrator authorization or system-directory writes.
- The selected plan respects native policy and operation exclusions.
- Snap discovery needs no additional dependency or background password prompt.

STEP-17. If a prototype condition fails, report the exact obstacle.

STEP-18. Do not replace an owner requirement with a weaker behavior.

## 16. Acceptance tests

The test identifiers below define the minimum acceptance evidence.
Each test must state the tested versions and the observed result.

| Test | Required result | Requirement groups |
| --- | --- | --- |
| AT-01 | New APT functions work without jq, curl, fzf, python3-apt, requests, or PackageKit | DEP, ARCH |
| AT-02 | New Snap functions work with only existing snapd, Python 3, and the current terminal stack | DEP, SNAP |
| AT-03 | An absent Python dependency disables only affected capabilities | DEP, CONF |
| AT-04 | An absent snapd installation does not break APT or existing backends | CONF, SNAP |
| AT-05 | A stopped snapd service gives an unavailable result without loss of the enable setting | CONF, SNAP |
| AT-06 | Private APT refresh writes only in the approved user area | APT, SAFE |
| AT-07 | Private APT refresh uses real dpkg state and system policy | APT |
| AT-08 | Source formats, Signed-By keys, multiple architectures, and proxy settings remain effective | APT |
| AT-09 | Signature errors and partial-source failures keep the previous result and synchronization time; metadataCurrent remains false | APT, DATA |
| AT-10 | APT holds, pinning, phased updates, and dependency restrictions remain effective | APT, RULE |
| AT-11 | Safe mode keeps removals out of the plan | CONF, EXEC |
| AT-12 | KDE neon auto mode uses full mode | CONF, EXEC |
| AT-13 | Epochs, tildes, revisions, and foreign architectures retain exact native meaning | APT, DATA |
| AT-14 | New dependencies and removals do not increase the available-update count | APT, DATA |
| AT-15 | APT operation exclusions keep excluded packages unchanged without persistent hold changes | RULE |
| AT-16 | An unsatisfied operation exclusion stops its transaction | RULE |
| AT-17 | Snap holds remain effective unless the user explicitly approves a manual override | SNAP, RULE |
| AT-18 | Equal Snap version text with different candidate revisions still identifies an update | SNAP, DATA |
| AT-19 | A running Snap application produces a blocked result without process termination | SNAP |
| AT-20 | A native automatic Snap update removes the obsolete displayed update | SNAP, DATA |
| AT-21 | APT, Snap, and Flatpak packages with the same display name remain distinct | DATA |
| AT-22 | Existing cache data and rules migrate without unrelated behavior changes | DATA, RULE |
| AT-23 | Management supports search, pagination, selection, details, and cancellation without fzf | UI |
| AT-24 | Remove, purge, autoremove, cache removal, and revision return need explicit user actions | EXEC, SNAP |
| AT-25 | Classic confinement needs explicit consent | SNAP |
| AT-26 | Empty stderr does not hide a nonzero command exit | DATA, LIFE |
| AT-27 | Cancellation, terminal closure, and daemon continuation do not produce false success | LIFE, SNAP |
| AT-28 | Pre-upgrade and post-upgrade scripts each run once for an APT-only sequence | LIFE |
| AT-29 | A busy native database does not cause lock removal or process termination | EXEC |
| AT-30 | Package text, unusual paths, quotes, and shell metacharacters cannot become commands | ARCH, SAFE |
| AT-31 | Notifications and cache results remain correct after one backend fails | DATA, LIFE |
| AT-32 | Existing Arch, AUR, Flatpak, widget, and firmware actions retain their behavior | SCOPE |
| AT-33 | New resources and executable scripts are present in the built plasmoid | SCOPE, STEP |
| AT-34 | Connection settings, schedules, restart preferences, and configuration overrides remain effective | CONF, LIFE |
| AT-35 | A single-package upgrade that needs another package's removal stops in safe mode without package changes | APT, EXEC |
| AT-36 | One source succeeds and another has a transient failure; the dependent APT install or upgrade does not start | APT, EXEC |
| AT-37 | NAME:ARCH=VERSION reaches APT as one argument after separate field validation; invalid fields cannot introduce options or arguments | ARCH, SAFE |
| AT-38 | Unreadable source configuration or required keys preserve the previous APT result and synchronization time; metadataCurrent remains false | APT, DATA |
| AT-39 | Quoted arguments retain their boundaries without code evaluation; invalid quotes stop the affected operation | ARCH, SAFE, LIFE |
| AT-40 | A firmware check failure preserves its previous result with an old-result indication | DATA, LIFE |
| AT-41 | A changed Flatpak candidate commit can produce one notification when version text remains unchanged; notification preferences remain effective | DATA |
| AT-42 | Widget updates use an existing compatible archive tool; download, archive, and installation failures cannot produce a successful transaction | SCOPE, LIFE |
| AT-43 | Development checks enforce documented coverage thresholds and save reports without additional application dependencies | SCOPE, STEP |
| AT-44 | Transient network failures use bounded retries; preferences, native errors, previous results, and empty error states remain correct | NET, DATA |
| AT-45 | Shell tests complete without terminal input when the developer starts the suite from an interactive terminal | TEST, STEP |
| AT-46 | Each coverage invocation updates marked README results; failed checks, unavailable reports, unchanged results, and user content retain correct states | TEST, STEP |

TEST-01. Use Python unittest for new automated helper tests.

TEST-02. Use fixtures and simulated native-command results for parser tests.

TEST-03. Use a temporary local Unix socket for snapd API tests.

TEST-04. Use subprocess substitutes for privileged-command tests.

TEST-05. Do not require pytest or another new test framework.

TEST-06. Do not install or remove host packages during automated unit tests.

TEST-07. Run native installation tests only in approved disposable systems.

TEST-08. Include a real private APT refresh test before acceptance.

TEST-09. Include real foreground package-operation tests before acceptance.

TEST-10. Include the following system matrix.

| System | Minimum evidence |
| --- | --- |
| Kubuntu 26.04 with Plasma 6 | APT and existing Snap; default-tool dependency test |
| Ubuntu 26.04 with Plasma 6 | Terminal integration, authorization, APT, and existing Snap |
| Debian 13 with Plasma 6 | APT; graceful Snap absence; Snap tests where snapd already exists |
| KDE neon User Edition with Plasma 6 | Native full mode and the actual Ubuntu base |
| An existing supported Arch system | Existing backends; Snap where snapd already exists |

TEST-11. Write the tested KDE neon base release in the test report.

TEST-12. Write actual APT, dpkg, Python, Plasma, and snapd versions in the test report.

TEST-13. Do not describe fixture tests as native integration tests.

TEST-14. Include a single-package upgrade fixture whose native plan removes another installed package.

TEST-15. Do the fixture tests with --no-remove in both simulation and execution paths.

TEST-16. Include a refresh fixture with one successful source and one transient download failure.

TEST-17. Make sure that --error-on=any produces a failure in both private and foreground refresh tests.

TEST-18. Make sure that no dependent APT install or upgrade starts after that foreground refresh failure.

TEST-19. Include valid and invalid field combinations in native-selector tests.

TEST-20. Do a separate check of the final subprocess argument list in native-selector tests.

TEST-21. Update the README coverage status after each normal or handled interrupted coverage invocation.

TEST-22. Use only current invocation reports for that status.

TEST-23. Keep test results separate from coverage threshold results.

TEST-24. Keep README content outside the coverage markers unchanged.

TEST-25. Publish README updates through an explicit Git commit and push.

## 17. Delivery and completion

DONE-01. Include application changes, tests, translations, and documentation in the implementation review.

DONE-02. Keep the implementation installable through KDE Widget Store.

DONE-03. List the existing runtime tools that the implementation uses.

DONE-04. Prove that the new paths need no additional package installation.

DONE-05. Include acceptance evidence for every test above.

DONE-06. Identify any untested system explicitly.

DONE-07. Do not claim complete platform support without its acceptance evidence.

DONE-08. Keep source changes limited to the approved request.

DONE-09. Complete the language review before a full ASD-STE100 conformity declaration.

DONE-10. Do not accept the implementation when a mandatory acceptance test fails.

### 17.1 Implementation record

The implementation uses source commit e971e7c3ff568e061b5ff8d066411135dc4c7219 as its baseline.
The changes remain in the working tree.
No release commit or deployment forms part of this delivery.
Unrelated local files, including .idea files, remain unchanged by this implementation.

| Area | Delivered change |
| --- | --- |
| Native integration | package/contents/tools/backends.py; Python standard library only |
| APT discovery | Private signed indexes, system dpkg state, native simulation, and strict refresh errors |
| APT operations | Terminal authorization, native previews, safe-mode removal protection, exclusions, and version-decrease confirmation |
| Snap discovery | Local snapd API, revision identities, holds, and refresh restrictions |
| Snap operations | Native CLI, separate hold and classic consent, snapshots, revision removal, and change completion |
| Package management | Numbered lists, pagination, details, search, installation, removal, history, and applicable earlier-version functions |
| Shared data | Source identities, cache migration, atomic cache replacement, old-result markers, and revision notifications |
| Existing sources | Source-specific rules, scoped Flatpak references, and preserved legacy management routes |
| Interface | APT and Snap settings, upgrade actions, package details, and management availability |
| Lifecycle | Per-stage results, cancellation, external-update reconciliation, and one pre-script and post-script execution |
| Delivery | README, translation template, Python extraction, automated tests, and CI checks |

Both new sources are disabled by default.
The existing system Python 3, APT, and dpkg commands supply the APT runtime tools.
An existing snapd installation supplies the optional Snap runtime tools.
The existing terminal stack supplies interactive authorization.
No additional runtime package was installed for this implementation.

The translation template includes the new interface and terminal messages.
Existing translated catalogs retain their current text.
New messages use English until translators supply their translations.
The independent ASD-STE100 dictionary review remains open.
This revision does not declare full ASD-STE100 conformity.

### 17.2 Local verification

The application versions below were recorded on 2026-10-24.
The coverage tool was recorded on 2026-10-25.
An installed Plasma package version does not prove an interactive desktop test.

| Component | Tested or inspected version |
| --- | --- |
| Operating system | Ubuntu 26.04.1 LTS, amd64 |
| APT | 3.2.0 |
| dpkg | 1.23.7 |
| System Python | 3.14.4 |
| Installed plasma-workspace | 4:6.6.6-0ubuntu0.1 |
| snapd | 2.77.1+ubuntu26.04.2 |
| Flatpak | 1.16.6-1 |
| Development Node.js | 25.9.0 |
| Development QML compiler | Qt 6.10.2 through existing PyQt6 |
| Development coverage.py | 7.17.0 |

The verification run on 2026-10-25 passed 148 Python tests and 63 JavaScript tests.
The optional QML check compiled 18 files without errors.
Python 3.10 syntax checks, shell syntax checks, JSON checks, XML checks, and whitespace checks passed.
The messages file contains translation data and is excluded from shell syntax checks.

Use these commands to repeat the automated checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --test tests/test_*.js
python3 -B tests/check_qml.py
```

Some execution environments restrict temporary Unix sockets, local HTTP servers, or child processes.
The tests need those capabilities.
They do not need privileged package operations.
The QML check skips when PyQt6 is absent.
Node.js and PyQt6 are development tools, not application dependencies.

The native APT regression tests use isolated repositories and package databases in temporary directories.
They run simulation and repository refresh commands.
Their local test repository has explicit test-only trust.
The application checker retains normal system signature checks.
These tests do not install or remove host packages.

A separate real check ran as desktop user 1000 with a temporary Apdatifier cache.
APT completed a private repository refresh and returned metadataCurrent=true with zero selected updates.
Snap returned metadataCurrent=true with one available update.
The Snap installed-package endpoint returned 41 packages.
These observations prove local discovery, not foreground package changes.

### 17.3 Acceptance evidence and open work

Local pass means that the stated automated or native check passed.
Partial means that local evidence exists but the complete acceptance scenario remains open.
No row below grants complete platform acceptance.

| Test | Local result | Evidence and remaining work |
| --- | --- | --- |
| AT-01 | Partial | Standard-library import audit and real APT discovery passed. Clean-image dependency test remains open. |
| AT-02 | Partial | Unix-socket tests and real Snap discovery passed. Interactive terminal acceptance remains open. |
| AT-03 | Local pass | JavaScript tests preserve legacy capabilities and terminal detection when system Python is absent. |
| AT-04 | Partial | Capability checks isolate optional Snap availability. A Debian system without snapd remains necessary. |
| AT-05 | Partial | API failure tests preserve error state. A stopped real daemon remains necessary. |
| AT-06 | Local pass | Private-path audit, temporary-directory tests, and a real unprivileged refresh passed. |
| AT-07 | Local pass | The checker validates the system dpkg path. Native discovery used the host package database. |
| AT-08 | Partial | Existing signed Ubuntu sources worked. Other formats, foreign architectures, authentication, and proxy combinations need system tests. |
| AT-09 | Partial | Native HTTP failure and snapshot-retention tests passed. Real signature-failure acceptance remains open. |
| AT-10 | Partial | Native operation-pin tests passed. The full hold, phasing, and dependency matrix remains open. |
| AT-11 | Local pass | Unit tests and native simulations enforce --no-remove for safe operations. |
| AT-12 | Partial | KDE neon mode-selection tests passed. Native KDE neon acceptance remains open. |
| AT-13 | Partial | Exact version and multiarch parser fixtures passed. Native foreign-architecture acceptance remains open. |
| AT-14 | Local pass | Plan fixtures separate installed upgrades, new dependencies, and removals. |
| AT-15 | Local pass | Native temporary-pin simulations preserve excluded packages without persistent hold changes. |
| AT-16 | Local pass | An excluded-package change stops execution in the foreground-plan tests. |
| AT-17 | Partial | Global and selected hold-consent tests passed. Live hold-override acceptance remains open. |
| AT-18 | Local pass | Snap fixtures identify different candidate revisions with equal version text. |
| AT-19 | Partial | Refresh-inhibition fixtures produce a blocked state. A running real Snap application remains necessary. |
| AT-20 | Partial | Installed-state fixtures remove completed automatic updates. A live automatic-refresh test remains open. |
| AT-21 | Local pass | Identity tests separate APT, Snap, and scoped Flatpak records with equal names. |
| AT-22 | Partial | Cache, widget-identity, rule-scope, and legacy-ignore tests passed. Existing-user desktop acceptance remains open. |
| AT-23 | Partial | Selection-boundary tests passed. Full interactive pagination, details, and cancellation need desktop testing. |
| AT-24 | Partial | Command and consent tests passed. Real destructive operations require an approved disposable system. |
| AT-25 | Partial | Classic-confinement consent tests passed. Real classic installation remains open. |
| AT-26 | Local pass | Python and JavaScript tests reject nonzero exits with empty stderr. |
| AT-27 | Partial | Process identity, cancellation, stage-result, and Snap-watch tests passed. Live daemon continuation remains open. |
| AT-28 | Local pass | An APT-only shell test runs each user script once with a failing substitute administrator command. |
| AT-29 | Partial | Native errors propagate without lock removal or foreign-process termination. Real database contention remains open. |
| AT-30 | Local pass | Selector validation, shell round trips, configuration escapes, and Unicode cache tests passed. |
| AT-31 | Local pass | Failed-source tests retain scoped old data and suppress new-update notifications from that data. |
| AT-32 | Partial | Legacy dependency, rule, identity, syntax, and scoped Flatpak tests passed. Full Arch regression remains open. |
| AT-33 | Partial | Source archive resource checks passed. KDE Widget Store installation acceptance remains open. |
| AT-34 | Partial | Configuration persistence and user-script tests passed. Interactive scheduling, terminals, and restart behavior remain open. |
| AT-35 | Local pass | A native APT fixture reproduces the removal. --no-remove stops it, and execution-argument tests retain that guard. |
| AT-36 | Local pass | A native HTTP 503 fixture proves strict refresh failure. Foreground tests stop before dependent installation or upgrade. |
| AT-37 | Local pass | Separate-field tests and subprocess-boundary tests preserve NAME:ARCH=VERSION as one argument. |
| AT-38 | Local pass | Native mode-000 source tests preserve the snapshot. Directory, key, binary-key, embedded-key, and access-loss fixtures passed. |
| AT-39 | Local pass | Substitute-command tests preserve quoted Arch, administrator, wrapper, and Flatpak arguments. Invalid quotes stop before native execution. |
| AT-40 | Local pass | Both fwupdmgr and fwupd error identifiers preserve only the previous firmware result and suppress update notifications. |
| AT-41 | Local pass | Commit-change, duplicate-notification, version fallback, old-result, and notification-preference tests passed. |
| AT-42 | Local pass | Eleven widget tests cover archive tools and failure propagation. A real KDE Control Station archive also passed with a substitute installer. |
| AT-43 | Local pass | Both coverage gates passed. Deliberately higher thresholds failed. HTML, XML, JSON, and LCOV reports were generated. |
| AT-44 | Partial | Retry, preference, cancellation, native-code, and diagnostic tests passed. Eighteen QML files compiled. A real desktop sleep and recovery test remains open. |
| AT-45 | Local pass | A pseudoterminal test reproduced the failure before correction. The complete coverage command then passed with interactive terminal input. |
| AT-46 | Local pass | Report, threshold, failure, preparation, interruption, marker, preservation, and atomic-write tests passed. The complete coverage command generated README results. |

The complete system matrix in Section 16 remains open.
Kubuntu, Debian 13, KDE neon, and Arch desktop acceptance was not performed.
The current Ubuntu system supplied discovery evidence and QML compilation evidence only.
No real privileged APT or Snap package change was tested.
Use approved disposable systems for that work.
Record the actual KDE neon base release when its tests run.

### 17.4 Review corrections on 2026-10-25

The owner identified four defects after the initial implementation.
The previous 53 Python tests and 22 JavaScript tests did not detect them.
The implementation now includes the following corrections.

| Defect | Correction and evidence |
| --- | --- |
| APT returned a current empty result after source access failed | The checker reads effective source paths before and after refresh. Unreadable files, directories, and required keys produce a capability error. AT-38 covers snapshot retention. |
| Configured quoted arguments lost their boundaries | The Bash parser in package/contents/tools/sh/arguments preserves quotes, escapes, and empty arguments without evaluation. It needs no Python. AT-39 covers full and individual operations. |
| Firmware failures removed cached updates | New errors use fwupd. Cache retention also accepts the older fwupdmgr identifier. AT-40 covers both forms. |
| Flatpak commit changes did not produce notifications | The fingerprint uses CM when present. Older records retain the version fallback. AT-41 covers unchanged version text and duplicate suppression. |

Native APT 3.2.0 reproduced exit code zero for unreadable main, .list, and .sources files despite --error-on=any.
The corrected checker kept the previous package records and synchronization time in each case.
The real system source and key readability audit also passed without changes to the host configuration.

The source audit uses the paths from apt-config.
It follows native source-fragment names and source formats. [S04, S22]
It accepts optional absent default files, disabled fragments, embedded keys, and binary key material.
Native APT still performs source parsing, repository authentication, and signature verification.

All new regression tests use temporary data or substitute commands.
The full distribution matrix and real privileged package operations remain open.

### 17.5 Widget archive correction on 2026-10-25

The owner reported a failed KDE Control Station update with a successful widgets stage result.
The installed version was 2.11.0.
The selected version was 2.13.0.

The downloaded file was a valid XZ-compressed tar archive of 1,019,112 bytes.
The system had GNU tar and unzip, but no bsdtar.
The old updater required bsdtar and described its absence as an unsupported format.
A bare exit after the error then returned zero.

The corrected updater keeps the existing bsdtar route.
It can also use existing tar or unzip for compatible archives.
It does not install an archive tool.
The downloader uses curl --fail to reject HTTP failures before extraction. [S23]
Each operation uses a separate temporary directory.
The updater validates package metadata before installation.
Download, extraction, metadata, and installer errors retain nonzero results.
A failed widget in a batch keeps the batch result unsuccessful.

The eleven new tests use local archives and substitute services.
They include the terminal lifecycle record for a failed archive.
They preserve the previous APT and Snap regression tests.

The corrected script also processed the actual KDE Control Station archive without bsdtar.
A substitute installer received package ID KdeControlStation and version 2.13.0.
This check did not install the live widget or restart Plasma.
The owner subsequently confirmed that the corrected widget update works.

### 17.6 Development coverage on 2026-10-25

The owner requested additional test coverage.
The owner approved coverage.py as a development dependency only.
The application retains its standard-library Python dependency policy.

The baseline contained 74 Python tests and 26 JavaScript tests.
That coverage change produced 115 Python tests and 55 JavaScript tests.
The new cases cover menus, CLI commands, inventories, source failures, cancellation, scheduling, and lifecycle results.
Native package changes remain substituted in the new interface tests.

| Measured area | Baseline | Result after this coverage change |
| --- | --- | --- |
| Python statements | 58.83% | 88.75% |
| Python branches | 47.60% | 77.20% |
| Python combined statements and branches | 55.30% | 85.12% |
| JavaScript lines | 49.63% | 94.33% |
| JavaScript branches | 61.76% | 74.14% |
| JavaScript functions | 68.25% | 91.28% |

The Python report includes the complete backends.py file.
The JavaScript report includes the complete tools.js file.
No application region was excluded to increase these results.
The JavaScript tests assign the actual source filename to code executed in a test VM.
The native Node.js runner can therefore identify and measure the application script.

The minimum Python combined result is 80%.
The minimum JavaScript results are 80% for lines, 70% for branches, and 70% for functions.
The documented report configurations enforce these thresholds. [S24, S25]
The normal coverage command passed.
A deliberate 100% threshold failed for each language, as required.

Run ./tests/run_coverage.sh from the repository.
The command prepares and selects the development virtual environment automatically.
The command writes reports below coverage/.
The Git ignore rules exclude that directory and the local development virtual environment.

| Report | Location |
| --- | --- |
| Python HTML | coverage/python/index.html |
| Python XML | coverage/python.xml |
| Python JSON | coverage/python.json |
| JavaScript LCOV | coverage/javascript.lcov |

The CI configuration selects Python 3.12 and 3.14 with Node.js 24.
It preserves reports as workflow artifacts after success or failure.
Release builds use the same coverage command before packaging.
The local verification used Python 3.14.4 and Node.js 25.9.0.
The remote workflow matrix has not been run during this local change.

Bash operations have functional tests through substitute commands and local archives.
No Bash line percentage is reported.
The QML check compiled 18 components without errors.
Compilation does not measure QML execution or interactive desktop behavior.
The full distribution acceptance matrix remains open.

### 17.7 Automatic test environment on 2026-10-25

The owner requested automatic virtual environment creation and selection.
The coverage command now creates .venv when the directory is absent.
It installs the pinned test requirements inside that environment.
The command invokes that environment's Python directly.
Manual shell activation is unnecessary. [S26]

Later runs reuse the environment.
A pip dry run checks the pinned requirements without an index request.
Missing or changed requirements start an installation inside the environment. [S27]
An incomplete existing environment produces an error and remains unchanged.
Creation and installation failures stop before the tests.

APDATIFIER_TEST_PYTHON selects the interpreter for environment creation.
APDATIFIER_TEST_VENV selects an alternative environment directory.
The CI workflows use the same preparation command.
They no longer install coverage.py outside that environment.

Eight additional tests cover preparation, reuse, changed requirements, custom paths, failures, and pip repair.
They use substitute interpreters and never install packages during unit tests.
A real first run created the project environment and passed 123 Python tests and 55 JavaScript tests.
The application coverage percentages in Section 17.6 remain unchanged.

### 17.8 Network recovery correction on 2026-10-25

The owner reported simultaneous Flatpak, widget, firmware, and APT check failures after startup or wake.
The owner confirmed that later checks worked.
The active configuration disabled the connectivity check and used a 120-minute interval.
The previous scheduler applied that full interval after each failed attempt.

The NetworkManager journal showed a transition from disabled to full connectivity.
After recovery, HTTP requests to Ubuntu Release metadata, Flathub, and the widget API returned status 200.
A fresh APT check in a temporary private cache also succeeded.
It returned status ok, metadataCurrent true, no errors, and no updates.
These checks did not change system repositories, system indexes, or installed packages.

Automatic checks now follow NET-01 through NET-14.
Detected network failures start up to three retries with increasing delays.
The retry state stays in memory and does not change the configured interval.
Success restores the normal schedule.
Explicit cancellation clears pending retries.
Manual mode remains manual.

The APT helper previously preferred stderr and could discard connection errors from stdout.
It now includes limited network evidence from both streams when a failed command reports a connection error.
The shared interface keeps the original native exit code and error category.
Missing Release files, invalid signatures, and other native errors remain visible.
A missing Release file alone does not start the retry sequence.
The correction does not weaken APT authentication or change repository settings.

The empty-list view now distinguishes a failed check from a successful empty result.
It also shows a waiting message when the enabled connectivity check reports an offline state.
The user's existing connectivity preference remains unchanged.

Four additional Python tests cover network evidence, native failures, successful fallback, and credential redaction.
Eight additional JavaScript tests cover classification, retry limits, recovery, preferences, cancellation, scheduling, and native codes.
The full run passed 127 Python tests and 63 JavaScript tests.
The QML check compiled 18 components without errors.

| Measured area | Current local result |
| --- | --- |
| Python statements | 88.82% |
| Python branches | 77.29% |
| Python combined statements and branches | 85.21% |
| JavaScript lines | 94.61% |
| JavaScript branches | 75.52% |
| JavaScript functions | 91.33% |

The installed applet was not replaced or restarted during this correction.
Live desktop recovery after sleep remains an acceptance task.
The full distribution acceptance matrix also remains open.

### 17.9 Terminal input in tests on 2026-10-25

The owner reported ten timeout errors during the coverage command.
Each error occurred in a test that started the upgrade shell script.
The subprocesses inherited the developer's terminal input.
After each simulated operation, the script waited for Enter before closing.
The test then reached its 15-second timeout.
The previous verification used noninteractive input and did not expose this condition.

Shell lifecycle and widget test subprocesses now use subprocess.DEVNULL for standard input.
Their output capture and operation assertions remain effective.
The test correction does not need a larger timeout.

A new regression test starts two existing lifecycle cases with pseudoterminal input.
It confirms that the parent test process has terminal input.
The cases must complete without an Enter key or other user input.
A timeout terminates the test process group and removes its temporary files.
The regression failed before the correction and passed afterward.

The complete coverage command also ran with terminal input attached.
It passed 128 Python tests and 63 JavaScript tests.
The application coverage percentages in Section 17.8 remain unchanged.
This correction changes test files and documentation only.

### 17.10 Automatic README coverage status on 2026-10-25

The owner approved automatic local README updates after each coverage invocation.
The owner selected normal Git commit and push for publication.
The coverage command does not commit or push changes itself.

The standard-library script tests/update_coverage_readme.py reads the Python JSON and JavaScript LCOV reports.
The command removes earlier copies of those two reports before preparation.
The generator rejects missing, incomplete, or invalid reports.
An unavailable source does not remove the other source's valid measurements.
Python uses combined statement and branch coverage for its main badge.
JavaScript uses line coverage for its main badge.
The detailed table includes all six measurements and their applicable thresholds.

Python thresholds come from .coveragerc.
JavaScript thresholds use the same shell variables as the native Node.js coverage options.
The generator respects Python report precision and the exact 100% requirement.
The badges use static Shields URLs with generated percentages. [S30]
Report generation does not contact Shields or upload coverage data.
README viewers request the badge images when they display the page.

The README has separate coverage-badges and coverage-summary marker pairs.
The generator replaces only their contents.
An atomic replacement preserves other content, line endings, and file permissions.
Identical results leave the README file unchanged.
Invalid markers stop publication without overwriting user text.

The summary distinguishes PASSED, FAILED, NOT RUN, and INTERRUPTED states.
A high coverage percentage does not hide failed checks.
Preparation failures show unavailable current measurements.
Normal exits and handled SIGINT or SIGTERM update the status through an exit handler.
If publication fails, the command keeps the original failure or returns a nonzero result.
Publication requires an available Python interpreter and a writable README.
Forced termination that bypasses exit handlers cannot publish a new status.

Twenty additional Python tests cover generation and command integration.
The command passed 148 Python tests and 63 JavaScript tests with terminal input attached.
The application coverage percentages in Section 17.8 remain unchanged.
The measured application scope remains backends.py and tools.js.
No Bash line coverage or QML execution coverage is added.

## 18. Sources

The source review date is 2026-10-24.
The sources below explain native behavior and the language reference.
The requirements above define the selected product design.

| ID | Primary source | Use |
| --- | --- | --- |
| S01 | [ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf); [official description](https://www.asd-ste100.org/about_STE.html); [current downloads](https://asd-ste100.org/STE_downloads.html) | Writing rules, dictionary, and conformity limits |
| S02 | [Ubuntu 26.04 ubuntu-minimal](https://packages.ubuntu.com/resolute/ubuntu-minimal) | Default Python 3 dependency |
| S03 | [Ubuntu 26.04 python3](https://packages.ubuntu.com/en/resolute/python3) | Standard-library dependency |
| S04 | [apt.conf(5)](https://manpages.debian.org/trixie/apt/apt.conf.5.en.html) | Paths, configuration order, and list clearing |
| S05 | [apt(8)](https://manpages.debian.org/trixie/apt/apt.8.en.html) | Script interface choice |
| S06 | [apt-get(8)](https://manpages.debian.org/trixie/apt/apt-get.8.en.html) | Simulation, upgrade modes, and native operations |
| S07 | [KDE neon FAQ](https://neon.kde.org/faq.php) | Required full-upgrade behavior and current base |
| S08 | [Debian dpkg FAQ](https://wiki.debian.org/Teams/Dpkg/FAQ) | Native lock behavior |
| S09 | [Snap REST API use](https://snapcraft.io/docs/how-to-guides/snap-development/use-the-rest-api/) | Unix socket, response envelopes, and asynchronous results |
| S10 | [Python socket](https://docs.python.org/3.13/library/socket.html); [Python http.client](https://docs.python.org/3.13/library/http.client.html); [Python subprocess](https://docs.python.org/3.13/library/subprocess.html) | Standard-library transport and process control |
| S11 | [snapd find implementation](https://github.com/canonical/snapd/blob/master/daemon/api_find.go); [Snap API reference](https://forum.snapcraft.io/t/snapd-rest-api/17954) | Refresh candidates and API access |
| S12 | [Snap revisions](https://snapcraft.io/docs/explanation/how-snaps-work/revisions/) | Revision identity and channel selection |
| S13 | [Snap update management](https://snapcraft.io/docs/how-to-guides/manage-snaps/manage-updates/) | Holds and manual refresh behavior |
| S14 | [Snap package management](https://snapcraft.io/docs/tutorials/get-started/) | Installation, removal, snapshots, and revision return |
| S15 | [Snap security policies](https://snapcraft.io/docs/explanation/security/security-policies/) | Classic confinement |
| S16 | [apt_preferences(5)](https://manpages.debian.org/trixie/apt/apt_preferences.5.en.html); [Ubuntu phased updates](https://ubuntu.com/server/docs/explanation/software/about-apt-upgrade-and-phased-updates/) | Native version policy |
| S17 | [apt-mark(8)](https://manpages.debian.org/trixie/apt/apt-mark.8.en.html); [dpkg-query(1)](https://manpages.debian.org/trixie/dpkg/dpkg-query.1.en.html); [apt-cache(8)](https://manpages.debian.org/trixie/apt/apt-cache.8.en.html) | Metadata and installation reasons |
| S18 | [Snap refresh awareness](https://snapcraft.io/docs/explanation/how-snaps-work/refresh-awareness/) | Running-application restrictions |
| S19 | [Ubuntu restart guidance](https://ubuntu.com/blog/ubuntu-updates-best-practices-for-updating-your-instance) | Native restart indications |
| S20 | [Kubuntu releases](https://www.kubuntu.org/download/); [Debian KDE release plan](https://wiki.debian.org/PkgQtKde/TrixieReleasePlans) | Plasma 6 system scope |
| S21 | [Flatpak command reference](https://docs.flatpak.org/en/latest/flatpak-command-reference.html) | Scoped discovery and native references for existing Flatpak records |
| S22 | [sources.list(5)](https://manpages.debian.org/trixie/apt/sources.list.5.en.html) | Source fragments, Deb822 fields, disabled sources, and Signed-By keys; checked on 2026-10-25 |
| S23 | [curl command reference](https://curl.se/docs/manpage.html#-f) | HTTP failure reporting with --fail; checked on 2026-10-25 |
| S24 | [coverage.py configuration](https://coverage.readthedocs.io/en/latest/config.html) | Source scope, branch measurement, report formats, and fail_under; checked on 2026-10-25 |
| S25 | [Node.js coverage](https://nodejs.org/api/test.html#collecting-code-coverage); [coverage thresholds](https://nodejs.org/api/cli.html#--test-coverage-linesthreshold) | Native V8 measurement, LCOV reports, and minimum coverage options; checked on 2026-10-25 |
| S26 | [Python venv](https://docs.python.org/3/library/venv.html) | Environment creation and direct interpreter use; checked on 2026-10-25 |
| S27 | [pip install](https://pip.pypa.io/en/stable/cli/pip_install/) | Requirement checks with --dry-run and --no-index; checked on 2026-10-25 |
| S28 | [Qt QNetworkInformation](https://doc.qt.io/qt-6/qnetworkinformation.html#reachability-prop) | Connectivity indications and their limitations; checked on 2026-10-25 |
| S29 | [Ubuntu apt-secure(8)](https://manpages.ubuntu.com/manpages/resolute/man8/apt-secure.8.html) | Release metadata authentication and native error handling; checked on 2026-10-25 |
| S30 | [Shields static badges](https://shields.io/badges/static-badge) | Labels, messages, percentage encoding, colors, and flat badge style; checked on 2026-10-25 |
