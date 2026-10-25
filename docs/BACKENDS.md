# Backends and requirements

[Back to README](../README.md)

Apdatifier uses the package tools already available on your system. Missing
dependencies disable affected capabilities; the widget does not install tools.
Enable sources in **Settings -> General -> Search**.

## Sources and tools

| Source or function | Existing tools needed |
| --- | --- |
| APT | System `/usr/bin/python3`, APT, and dpkg |
| Snap | System `/usr/bin/python3`, the Snap command, and a running snapd service |
| Arch repositories | `pacman` and its existing Arch tools |
| AUR | An installed wrapper such as `paru`, `yay`, or `pikaur` |
| Flatpak | `flatpak` |
| KDE widgets | `jq`, `curl`, `xmllint`, `kpackagetool6`, and a compatible archive tool |
| Widget archives | `bsdtar`, or existing `tar` and `unzip` for the applicable formats |
| Firmware | `fwupdmgr` |
| News | `jq` and `curl` |
| Terminal multiplexer | `tmux`, when enabled |
| Legacy interactive package selection | `fzf`, when required by Arch or Flatpak management |

APT and Snap use only the Python standard library and native package tools.
They do not require `python3-apt`, `jq`, `curl`, `fzf`, `requests`, or PackageKit.
Their management menus use numbered, paginated lists.

The APT integration targets Plasma 6 on Kubuntu, Ubuntu with Plasma, Debian, and
KDE neon. The complete distribution acceptance matrix remains open; see the
[implementation record](change-request/2026-10-25_CHANGE_REQUEST_APT_SNAP.md#173-acceptance-evidence-and-open-work).

## APT

APT is disabled by default. Enable it in **Settings -> General -> Search**.
Select the administrator command in **Settings -> Upgrade & Management -> General**.

Background checks download signed repository indexes into the user's Apdatifier
cache. They read the system package database without administrator authorization
and do not replace the system indexes. The private indexes use additional disk
space and download traffic.

Existing sources, architectures, keys, pinning, and phased-update policy remain
effective. An unreadable source file, source directory, or required key keeps the
last complete result and its synchronization time.

Automatic mode selects safe upgrades on Ubuntu and Debian. Safe upgrades use
`--no-remove`, including individual upgrades. KDE neon uses full mode, which can
remove packages to resolve dependencies.

Foreground operations use the selected terminal and administrator command.
They refresh system indexes with `--error-on=any` before installation or upgrade.
An incomplete refresh stops the dependent operation. Native repository and
signature errors remain effective.

## Snap

Snap is disabled by default and is available only where snapd is installed.
Checks use the local snapd API. They keep channels, holds, and update schedules
unchanged.

A manual refresh can bypass an automatic-refresh hold. Apdatifier requests
separate consent for that override. Running applications can block a refresh;
Apdatifier does not terminate them.

Snap update notifications compare candidate revisions even when version text
does not change.

## Package management and rules

The terminal management menu includes search, package details, installation,
removal, history, and applicable cache and earlier-version operations.
Removal, purge, unused-dependency removal, classic confinement, and revision
return require explicit user actions. Native prompts remain in the terminal.

Rules can select a package source. Visual exclusions do not create system holds.
APT and Snap operation exclusions apply only to the selected manual operation.
Legacy ignore rules retain their Arch meaning.

Configured upgrade arguments support quotes, escaped spaces, and empty values.
Apdatifier preserves argument boundaries without evaluating shell substitutions.

## Results, notifications, and network recovery

A failed check keeps the last complete source result and shows its age.
An empty list with source errors does not show "System updated".

Package identities include their source. APT also includes architecture, while
Flatpak includes installation scope and native reference. Flatpak notifications
use native candidate commits when available.

Automatic checks retry detected network failures after 30, 60, and 120 seconds.
After three retries, the normal schedule resumes. Manual mode does not retry.
Retries respect connectivity and metered connection settings.

Enable **Settings -> General -> Misc -> Network -> Connectivity check** to wait
for a network connection before checking. This is useful after startup or wake.
Connectivity detection cannot guarantee access to each update server.

## KDE Store widgets and fork updates

The Widgets source uses KDE Store metadata to find updates for installed widgets.
This fork keeps the upstream Apdatifier widget ID and package name.
An Apdatifier self-update offered through the store therefore refers to upstream.

The built-in **Install Development** and **Install Stable** actions also target
upstream. Follow the [Git update instructions](../README.md#updating) to update
this fork. The Widgets source can still update other KDE Store widgets.

## Supported terminals

alacritty, foot, gnome-terminal, ghostty, konsole, kitty, lxterminal, ptyxis,
terminator, tilix, xterm, yakuake, and wezterm.

Flatpak installations of these terminals are also supported.

## Data directories

| Data | Default location | Overrides |
| --- | --- | --- |
| Settings and rules | `~/.config/apdatifier/` | `APDATIFIER_CONFIG_DIR`, otherwise `XDG_CONFIG_HOME` |
| Cached results and private APT indexes | `~/.cache/apdatifier/` | `APDATIFIER_CACHE_DIR`, otherwise `XDG_CACHE_HOME` |
| Installed icons | `~/.local/share/icons/breeze/status/22/apdatifier-*.svg` | `XDG_LOCAL_HOME` |
| Notification definition | `~/.local/share/knotifications6/apdatifier.notifyrc` | `XDG_LOCAL_HOME` |

The shell integration uses `XDG_LOCAL_HOME` for its shared-data directory.
The [uninstall instructions](../README.md#uninstalling) distinguish package
removal from optional removal of saved data and integration files.
