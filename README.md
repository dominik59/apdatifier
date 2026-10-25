<div align="center">

<!-- <img src="./screenshots/header.png" width="200px" alt="banner"/> -->



# Apdatifier
### Package Update Notifier for Plasma 6

<br>

![License](https://img.shields.io/github/license/exequtic/apdatifier?style=flat&logo=gnu&logoColor=white&label=License&color=brown)&nbsp;&nbsp;
![Downloads](https://img.shields.io/github/downloads/exequtic/apdatifier/total?style=flat&logo=kdeplasma&logoColor=white&label=Downloads&color=red)&nbsp;&nbsp;
![Stars](https://img.shields.io/github/stars/exequtic/apdatifier?style=flat&logo=github&logoColor=white&label=Stars&color=blue)

<!-- coverage-badges:start -->
[![Python coverage: 85.21%](https://img.shields.io/badge/Python%20coverage-85.21%25-brightgreen?style=flat)](#coverage)
[![JavaScript lines: 94.61%](https://img.shields.io/badge/JavaScript%20lines-94.61%25-brightgreen?style=flat)](#coverage)
<!-- coverage-badges:end -->

<br>

</div>

## Features
- Searching updates for APT, [Snap](https://snapcraft.io), [pacman](https://archlinux.org/packages/), [AUR](https://aur.archlinux.org/packages), [Plasma Widgets](https://store.kde.org/browse?cat=705), [Flatpak](https://flathub.org), [Firmware](https://fwupd.org/lvfs/vendors/)
- Notifications for updates and news
- Bash script with useful options for managing packages
- Full system upgrade in the selected [terminal](#supported-terminals)
- Refresh the [mirrorlist](https://archlinux.org/mirrorlist) with the latest mirrors filtered by speed
- APT and Snap integration for Plasma 6, with the existing terminal workflow

<br>

## Screenshots (outdated)

<div align="center">

<img src="./screenshots/screenshot_1.png" width="300px" alt="screenshot"/>
&nbsp;&nbsp;&nbsp;
<img src="./screenshots/screenshot_2.png" width="300px" alt="screenshot"/>
&nbsp;&nbsp;&nbsp;

<br>

<img src="./screenshots/screenshot_4.png" width="500px" alt="screenshot"/>

<br>

<img src="./screenshots/screenshot_3.png" width="500px" alt="screenshot"/>

<br><br>

https://github.com/exequtic/apdatifier/assets/29355358/9751fc8f-29c2-4f7d-8f1f-c346c0748df3

</div>

<br>

## Requirements
Plasma 6 is required. APT and Snap use the existing system Python 3 standard
library and native package commands. These backends do not require
python3-apt, jq, curl, fzf, requests, or PackageKit.

Snap is available only where snapd is already installed. Missing dependencies
disable the affected capabilities. Apdatifier does not install them.

### Optional dependencies
- `paru`, `yay`, `pikaur` - for AUR updates support
- `flatpak` - for Flatpak updates support
- `fwupdmgr` - for Firmware updates support
- `jq` - for KDE Widgets updates and News
- `curl`, `xmllint` - for KDE Widgets metadata and downloads
- `bsdtar`, or existing `tar` and `unzip` - for applicable KDE Widget archive formats
- `tmux` - for upgrade and management in a terminal multiplexer
- `fzf` - for interactive package selection in management

APT and Snap management use numbered, paginated lists without fzf. The existing
Arch and Flatpak management functions retain their optional dependencies.

### Supported terminals
alacritty, foot, gnome-terminal, ghostty, konsole, kitty, lxterminal, ptyxis, terminator, tilix, xterm, yakuake, wezterm

Flatpak installations of these terminals are also supported.

<br>

<!-- # Translation
Feel free to help translate to new languages or update and improve the ones that are already available. Please refer to the [ReadMe.md](https://github.com/exequtic/apdatifier/blob/main/package/translate/ReadMe.md) for instructions on how to do it.

<br> -->

## APT and Snap

Enable APT or Snap in **Settings -> General -> Search**. Both sources are
disabled by default. Choose the administrator command in
**Settings -> Upgrade & Management -> General**.

APT checks download signed repository indexes into the user's Apdatifier cache.
They read the system package database without administrator authorization.
They do not replace the system indexes. The private indexes use additional disk
space and download traffic. Existing repository sources, architectures, keys,
pinning, and phased-update policy remain effective.
An unreadable source file, source directory, or required key keeps the last
complete result and its synchronization time.

Automatic APT mode selects safe upgrades on Ubuntu and Debian. Safe upgrades use
`--no-remove`, including individual upgrades. KDE neon uses full mode, which can
remove packages to resolve dependencies. Foreground APT operations refresh the
system indexes with `--error-on=any` before installation or upgrade. An incomplete
refresh stops the dependent operation.

Snap checks use the local snapd API. They keep Snap channels, holds, and update
schedules unchanged. A manual refresh can bypass an automatic-refresh hold.
Apdatifier requests separate consent for that override. Running applications can
block a refresh; Apdatifier does not terminate them.

The terminal management menu includes search, package details, installation,
removal, history, and applicable cache and earlier-version operations. Removal,
purge, unused-dependency removal, classic confinement, and revision return need
explicit user actions. Native prompts remain in the terminal.

Rules can select a package source. Visual exclusions do not create system holds.
APT and Snap operation exclusions apply only to the selected manual operation.
Legacy ignore rules retain their Arch meaning.

Failed checks keep the last complete source result and show its age. Package
identities include their source; APT also includes architecture, and Flatpak
includes installation scope and native reference. Snap notifications compare
revisions even when version text remains unchanged.
Flatpak notifications use native candidate commits when available.

Automatic checks retry network failures after 30, 60, and 120 seconds.
After three retries, the normal schedule resumes. Manual mode does not retry.
Retries respect connectivity and metered connection settings. An empty result
with source errors does not show "System updated".

Enable **Settings -> General -> Misc -> Network -> Connectivity check** to wait
for a network connection before checking. This is useful after startup or wake.
Connectivity detection cannot guarantee access to each update server.
Apdatifier keeps native repository and signature errors; it does not bypass them.

Configured upgrade arguments support quotes, escaped spaces, and empty values.
Apdatifier preserves those arguments without evaluating shell substitutions.

## Development checks

No additional Python modules are needed for the backend tests:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --test tests/test_*.js
python3 -B tests/check_qml.py
```

Node.js is a development test tool already present on GitHub Actions. It is not
an application dependency. The optional QML compiler check uses an existing
PyQt6 installation and skips when that development binding is absent.

Native APT regression tests use temporary local repositories and simulation.
They do not install or remove host packages. Snap API tests use a temporary Unix
socket. Integration acceptance on each target desktop, including real privileged
package operations, remains necessary before complete platform support is claimed.

Widget updater tests use local tar.xz and ZIP archives with substitute downloads
and installers. They cover missing tools, invalid packages, HTTP errors, native
installer errors, and partial batch failures without installing live widgets.

Shell tests disconnect child standard input to prevent terminal prompts from
blocking the suite. A regression test uses a pseudoterminal to check this behavior
when tests run from an interactive developer terminal.

### Coverage

<!-- coverage-summary:start -->
Last coverage run: **PASSED**.

Python checks: **PASSED**. JavaScript checks: **PASSED**.

| Metric | Coverage | Minimum | Coverage gate |
| --- | ---: | ---: | --- |
| Python: statements and branches | 85.21% | 80% | PASS |
| Python: statements | 88.82% | Not gated | Not gated |
| Python: branches | 77.29% | Not gated | Not gated |
| JavaScript: lines | 94.61% | 80% | PASS |
| JavaScript: branches | 75.52% | 70% | PASS |
| JavaScript: functions | 91.33% | 70% | PASS |

Measured scope: `package/contents/tools/backends.py` and `package/contents/tools/tools.js`.
<!-- coverage-summary:end -->

Each invocation of `./tests/run_coverage.sh` updates the badges and table above
from that run's reports, including failed checks. Missing results are unavailable;
they do not reuse an earlier percentage. Identical results keep README unchanged.
The run status includes tests, report generation, and coverage gates.

The script updates only the marked README sections. Commit and push README to
publish the results on GitHub. Running the script does not commit, push, or upload
reports to an external coverage service. Badge images use Shields, as above.

Coverage uses Python 3.11 or later with venv support and Node.js 22.8 or later.
Run both suites with one command:

```sh
./tests/run_coverage.sh
```

The script creates `.venv` when it is absent and installs the pinned development
dependencies from `requirements-test.txt`. It selects that environment's Python
automatically. Later runs
reuse the environment and check installed dependencies without network access.
Missing or changed dependencies trigger installation inside that environment.
An incomplete existing environment produces an error and is preserved.

Set `APDATIFIER_TEST_PYTHON` to select the Python interpreter used to create the
environment. Set `APDATIFIER_TEST_VENV` to select another environment directory.
No manual activation or global pip installation is needed.

`coverage.py` is a development dependency. The installed widget still uses only
the Python standard library. JavaScript coverage uses the built-in Node.js test
runner and V8; no npm package is required.

The command creates these ignored files:

| Report | Location |
| --- | --- |
| Python HTML, with missing lines and branches | `coverage/python/index.html` |
| Python XML and JSON | `coverage/python.xml`, `coverage/python.json` |
| JavaScript LCOV, for coverage viewers | `coverage/javascript.lcov` |
| Both test results and coverage summaries | Terminal output and GitHub Actions logs |

The enforced minimum is 80% combined statement and branch coverage for
`backends.py`. JavaScript requires 80% lines, 70% branches, and 70% functions for
the complete `tools.js` file. The configuration does not omit menu or CLI code.
These are independent gates; either failure makes the coverage command fail.

GitHub Actions runs the checks on Python 3.12 and 3.14 with Node.js 24. It uploads
reports for each version, including reports from failed runs. Release builds run
the same coverage gate before packaging.

The percentages cover the Python helper and JavaScript application logic.
The Python suite also tests Bash operations through substitute commands and local
archives. Bash line coverage and QML execution coverage are not measured.
The separate QML check compiles components without creating a live applet.
Full desktop, package-manager, and distribution acceptance remains separate.

The implementation follows [CR-APT-SNAP-001](CHANGE_REQUEST_APT_SNAP.md).
The change request records its acceptance criteria and current evidence.

## Installation

Just install directly from KDE Widget Store ("+ Add widgets..." -> "Get New Widgets..." -> "Download New Plasma Widgets").

After installation, you can either enable it to appear in the system tray or place it on the panel or desktop instead.


### Update to the latest commit
```
Settings -> General -> Misc -> Install Development version
```

If script doesn't work, you can do it manually:

```bash
git clone -n --depth=10 --filter=tree:0 -b main https://github.com/exequtic/apdatifier
cd apdatifier
git sparse-checkout set --no-cone package
git checkout
kpackagetool6 -t Plasma/Applet -u ./package
systemctl --user restart plasma-plasmashell.service
```

<br>

## Uninstalling
Uninstall plasmoid and remove all related files (config, icons, notifyrc):

```bash
bash ~/.local/share/plasma/plasmoids/com.github.exequtic.apdatifier/contents/tools/sh/utils uninstall
```

<br>
