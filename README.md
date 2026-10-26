# Apdatifier

Package update notifications and terminal-based upgrades for KDE Plasma 6.
This fork adds APT and Snap support alongside pacman/AUR, Flatpak, Plasma
widgets, and firmware updates.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat)](LICENSE.md)
<!-- coverage-badges:start -->
[![Python coverage: 85.52%](https://img.shields.io/badge/Python%20coverage-85.52%25-brightgreen?style=flat)](#coverage)
[![JavaScript lines: 95.33%](https://img.shields.io/badge/JavaScript%20lines-95.33%25-brightgreen?style=flat)](#coverage)
<!-- coverage-badges:end -->

[Install](#installation) · [Update](#updating) · [Uninstall](#uninstalling) · [Coverage](#coverage)

The KDE Widget Store/openDesktop listing provides the upstream version.
Install this fork from this repository.

## Installation

You need **Linux with Plasma 6**, `kpackagetool6`, and Git for the commands below.
APT and Snap also use the existing system `/usr/bin/python3` and native package
tools. See [backend requirements](docs/BACKENDS.md#sources-and-tools).

Run these commands as your desktop user:

```bash
git clone --branch main https://github.com/dominik59/apdatifier.git
cd apdatifier
kpackagetool6 -t Plasma/Applet -i ./package
```

**Already have Apdatifier installed?** Use this last command instead:

```bash
kpackagetool6 -t Plasma/Applet -u ./package
```

The fork uses the same widget ID, `com.github.exequtic.apdatifier`, and replaces
an existing user installation. Both versions share the same settings.

Apdatifier is enabled in the system tray by default. Its icon stays visible even
when no updates are available. Plasma keeps earlier explicit tray preferences;
if you previously disabled or hid Apdatifier, enable it in **System Tray Settings**.
You can also add it to a panel or desktop through **Add Widgets**.
If Plasma still shows the earlier version, [reload Plasma](#reload-plasma).

## Updating

From your existing checkout:

```bash
git pull --ff-only
kpackagetool6 -t Plasma/Applet -u ./package
```

Then [reload Plasma](#reload-plasma) to load the updated code.

> Update this fork from Git. The built-in **Install Development** and
> **Install Stable** actions target upstream. An **Apdatifier** self-update
> offered by the Widgets source also refers to upstream.

### Reload Plasma

```bash
systemctl --user restart plasma-plasmashell.service
```

If your session does not provide that service, log out and log in again.

## First setup

1. Open **Settings -> General -> Search** and enable the sources you need.
   **APT and Snap are disabled by default.**
2. Select your terminal and administrator command under
   **Settings -> Upgrade & Management -> General**.
3. Enable **Settings -> General -> Misc -> Network -> Connectivity check**
   to wait for a connection after startup or wake.

Missing commands disable the affected capabilities. Apdatifier does not install
them. See [backend behavior and supported terminals](docs/BACKENDS.md).

## Uninstalling

First remove Apdatifier from your panels and desktop, and disable its system
tray entry if enabled. Then remove the package for your user account:

```bash
kpackagetool6 -t Plasma/Applet -r com.github.exequtic.apdatifier
```

This keeps your Apdatifier settings and cached results for a later installation.

<details>
<summary>Also remove settings, cached data, and integration files</summary>

After removing the widget and package, these commands permanently delete your
Apdatifier settings, cached results, notification definition, and installed icons.
They use Apdatifier's directory overrides when set.

```bash
rm -rf -- "${APDATIFIER_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/apdatifier}" \
          "${APDATIFIER_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/apdatifier}"
rm -f -- "${XDG_LOCAL_HOME:-$HOME/.local/share}/knotifications6/apdatifier.notifyrc" \
         "${XDG_LOCAL_HOME:-$HOME/.local/share}/icons/breeze/status/22/apdatifier-plasmoid.svg" \
         "${XDG_LOCAL_HOME:-$HOME/.local/share}/icons/breeze/status/22/apdatifier-packages.svg" \
         "${XDG_LOCAL_HOME:-$HOME/.local/share}/icons/breeze/status/22/apdatifier-package.svg" \
         "${XDG_LOCAL_HOME:-$HOME/.local/share}/icons/breeze/status/22/apdatifier-flatpak.svg"
```

The built-in uninstaller removes settings and integration files too, but leaves
the cache. The commands above include the cache.

</details>

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Package is already installed | Use `-u ./package` instead of `-i ./package`. |
| Widget is missing or still shows the earlier version | [Reload Plasma](#reload-plasma), then check Add Widgets or System Tray Settings. |
| APT or Snap updates are missing | Enable the source in General -> Search and check its [requirements](docs/BACKENDS.md#sources-and-tools). |
| Checks fail after startup or wake | Enable Connectivity check. Automatic checks retry detected network failures after 30, 60, and 120 seconds. |

## Coverage

<!-- coverage-summary:start -->
Last coverage run: **PASSED**.

Python checks: **PASSED**. JavaScript checks: **PASSED**.

| Metric | Coverage | Minimum | Coverage gate |
| --- | ---: | ---: | --- |
| Python: statements and branches | 85.52% | 80% | PASS |
| Python: statements | 89.00% | Not gated | Not gated |
| Python: branches | 77.89% | Not gated | Not gated |
| JavaScript: lines | 95.33% | 80% | PASS |
| JavaScript: branches | 76.00% | 70% | PASS |
| JavaScript: functions | 91.88% | 70% | PASS |

Measured scope: `package/contents/tools/backends.py` and `package/contents/tools/tools.js`.
<!-- coverage-summary:end -->

`./tests/run_coverage.sh` refreshes these local results after each run, including
failures. Commit and push README to publish changed results on GitHub.
See [development checks](docs/DEVELOPMENT.md) for setup, reports, and limitations.

## Development

Run tests and enforce coverage with:

```bash
./tests/run_coverage.sh
```

The script creates or reuses a development `.venv` automatically.
See [the development guide](docs/DEVELOPMENT.md) and
[the implementation and acceptance record](docs/change-request/2026-10-25_CHANGE_REQUEST_APT_SNAP.md).

## License

[MIT](LICENSE.md).
