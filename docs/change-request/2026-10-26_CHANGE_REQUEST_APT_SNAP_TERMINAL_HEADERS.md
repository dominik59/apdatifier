# Change request: APT and Snap terminal headers

| Field | Value |
| --- | --- |
| Request ID | CR-APT-SNAP-TERMINAL-HEADERS-001 |
| Revision | 1.4 |
| Date | 2026-10-26 |
| Product | Apdatifier for KDE Plasma 6 |
| Repository | https://github.com/dominik59/apdatifier |
| Source commit | 468a5d0ea4e2ee7d5fd10a4a575fc7f2326357c7 |
| Status | Implemented. Local tests passed. Desktop verification remains open |
| Current approval | Implementation and local verification |
| Document language | English |
| Language reference | ASD-STE100, Issue 9 |
| Language check | Known rule errors corrected. Full dictionary check by a second person remains open |

## 1. Purpose and authority

Add terminal start headers for APT and Snap updates.
Use the same frame style as the Flatpak start header at the source commit.
This document gives the scope, source evidence, design, and acceptance criteria.
No previous conversation is necessary.
Repository paths start at the repository root.
Markdown links use paths from this document's directory.

The owner found that APT and Snap updates did not show a terminal start header.
The owner asked for this change request on 2026-10-26.
The owner then gave approval for changes to this document.
On 2026-10-26, the owner gave approval for implementation and local verification.

AUTH-01. Limit implementation changes to the files in section 7.

AUTH-02. Use the owner's implementation approval from 2026-10-26 for this change.

AUTH-03. Before you create a Git commit, get approval from the owner.

AUTH-04. Do not change other local work.

AUTH-05. Do not install host packages under the current approval.

AUTH-06. Do not update the installed applet under the current approval.

AUTH-07. Do not restart Plasma under the current approval.

AUTH-08. Before you push this change, get approval from the owner.

## 2. Terms and language

| Technical noun | Meaning in this change request |
| --- | --- |
| Start header | The frame and title that the terminal shows before the stage's foreground command starts |
| Frame | The border, colors, and spacing from the printMsg function |
| Backend | The software component for APT, Snap, or another package source |
| Stage | One backend operation in the shell upgrade sequence, with its result |
| Native identity | The package identifier that the backend uses. An APT identifier includes its architecture. A Snap identifier includes its instance name |
| Helper | The Python program at package/contents/tools/backends.py |
| Foreground command | The helper's foreground command, which starts one APT or Snap package operation |
| Full sequence | The full shell operation, which updates all enabled backends in their configured order |
| Argument | One input value for a command or function |
| Administrator prompt | The question that the administrator command shows for authorization |
| Exit code | The integer result that a process gives when it ends |
| Fixture | Test data or substitute software that a test uses instead of the real package operation |
| Translation template | The gettext POT file that contains the source text for translations |
| Change request | This document, its requirements, and its acceptance criteria |
| Git commit | A record of file changes in the Git repository |

The technical verbs below refer to computer processes and applications.
Their meanings apply only to the software operations in this document. [S01]

| Technical verb | Meaning in this change request |
| --- | --- |
| Call | Start a software function |
| Create | Make a software file, data object, or Git commit |
| Load | Read software data into a program |
| Print | Write text to terminal output |
| Push | Send Git commits to a remote repository |
| Quote | Add shell quotation marks so text stays in one argument |
| Route | Send an operation to its software function |
| Run | Start a program or command |
| Update | Install a newer software version or change a software data file |
| Validate | Do a check of software data against its specified format |

LANG-01. Use short sentences.

LANG-02. Use the active voice.

LANG-03. Give one instruction in each procedural sentence.

LANG-04. Keep procedural sentences within 20 words.

LANG-05. Keep descriptive sentences within 25 words.

LANG-06. Keep exact command, path, identifier, and product spellings.

LANG-07. Use technical terms only with the meanings given above.

LANG-08. Before you say that the text obeys ASD-STE100, get another person to do a check of all words.

ASD-STE100 also controls word meanings, parts of speech, verb forms, and sentence structure. [S01]
Sentence length alone does not show full conformity.
The full dictionary check remains open.
In STE, check is a noun, not a verb. [S02]

## 3. Current source evidence

The baseline is source commit 468a5d0ea4e2ee7d5fd10a4a575fc7f2326357c7.
If later changes move line numbers, read the named functions.

| Location at the baseline | Observed behavior |
| --- | --- |
| [upgrade:29](../../package/contents/tools/sh/upgrade#L29), state start | Runs the helper's lifecycle start command before the update stages |
| [upgrade:135](../../package/contents/tools/sh/upgrade#L135), flatpak_upgrade | Calls printMsg before the Flatpak update |
| [upgrade:186](../../package/contents/tools/sh/upgrade#L186), native_upgrade | Starts the Python helper without a start header |
| [upgrade:207](../../package/contents/tools/sh/upgrade#L207), fullSystemUpgrade | Routes APT and Snap stages through native_upgrade |
| [upgrade:258](../../package/contents/tools/sh/upgrade#L258), operation dispatch | Routes source and single-package APT and Snap updates through native_upgrade |
| [utils:55](../../package/contents/tools/sh/utils#L55), printMsg | Prints the colored frame and title |
| [messages](../../package/contents/tools/sh/messages) | Contains the Flatpak header and the shared Upgrade text |
| [vars](../../package/contents/tools/sh/vars) | Loads terminal text through gettext |
| [test_backends.py](../../tests/test_backends.py), ShellLifecycleTests | Includes tests of shell arguments and lifecycle behavior. Includes no test for APT or Snap start headers |

The installed scripts and the repository scripts were the same during the source check.
The native_upgrade function does not print a start header.
The shell script already prints the exit code, execution time, and terminal-close text for these stages.
This change request concerns the start header.
The lifecycle start command keeps its position before the update stages.
Start headers apply to the foreground command in native_upgrade.

## 4. Necessary terminal behavior

The table gives the English titles.
The terminal uses its configured language for translated titles.
If a translation is not available, the terminal shows the English title.
Package identities and backend names keep their exact spelling.

The helper request column gives arguments to the Python helper's foreground command.
These entries are not commands for the apt or snap executable.

| User action | Helper request | Start header title |
| --- | --- | --- |
| Update the APT source | apt upgrade | APT Upgrade |
| Update the Snap source | snap refresh, without a package name | Snap Upgrade |
| Update one APT package | apt upgrade-package example:amd64 | Upgrade: example:amd64 (APT) |
| Update one Snap package | snap refresh example | Upgrade: example (Snap) |
| Run the APT stage in a full sequence | apt upgrade | APT Upgrade |
| Run the Snap stage in a full sequence | snap refresh, without a package name | Snap Upgrade |

HEAD-01. Print exactly one start header for each APT or Snap stage that starts.

HEAD-02. Before the helper's foreground command starts, print the start header.

HEAD-03. Show the start header before backend command output or an administrator prompt.

HEAD-04. Use the printMsg frame, colors, and spacing from the source commit.

HEAD-05. If a translation is not available, use the English title from the table.

HEAD-06. Keep the architecture in a displayed APT native identity.

HEAD-07. Keep all characters of the Snap instance name in a single-package title.

HEAD-08. After a stage failure or cancellation, keep its start header in the terminal.

HEAD-09. If cancellation skips a stage, do not print its start header.

HEAD-10. Do not change the start headers for Arch, AUR, Flatpak, widgets, or firmware.

HEAD-11. If a stage finds no updates, keep its start header in the terminal.

## 5. Proposed implementation

Keep header selection in native_upgrade within package/contents/tools/sh/upgrade.
This function starts every affected source operation and single-package operation.
One location for header selection prevents duplicate start headers in full sequences.

For the APT upgrade action, select the source title.
For the APT upgrade-package action, select the single-package title.
If Snap refresh has no package argument, select the source title.
If Snap refresh has a package argument, select the single-package title.
Before the Python availability check, print the selected start header.
Keep the lifecycle start command before the update stages.

Add these resources to package/contents/tools/sh/messages:

```text
UPGRADE_FULL_APT = i18n("APT Upgrade")
UPGRADE_FULL_SNAP = i18n("Snap Upgrade")
```

Use UPGRADE_PACKAGE again for the translated Upgrade text in single-package titles.
Use APT and Snap as the backend names in these titles.
Quote the title as one printMsg argument.
Do not add the start header to helper arguments.

Update package/translate/template.pot for the new message identifiers.
Do not change translations for other source text.
If a new title has no translation, keep its English title.
New translations for every supported language are outside this change request.

If xgettext is not available, package/translate/merge can install gettext.
Do not run that installation path.
If the necessary development tools are available, use them to update the translation template.
If the tools are not available, change only the necessary template entries by hand.
Do not run shell syntax checks on messages.
The messages file contains data for text extraction.
It does not contain executable shell statements.

## 6. Behavior to keep

KEEP-01. Do not change package selection, native identities, or command arguments.

KEEP-02. Do not change APT safe-mode guards, native holds, or operation exclusions.

KEEP-03. Do not change how Snap handles holds, channels, refresh restrictions, or transaction completion.

KEEP-04. Do not change administrator prompts or user confirmations.

KEEP-05. Do not change native exit codes, stage results, or cancellation behavior.

KEEP-06. Do not change pre-update scripts, post-update scripts, stage order, or idle inhibition.

KEEP-07. Do not change completion output or terminal-close behavior.

KEEP-08. Do not change JSON output from background helper commands.

KEEP-09. Do not change how terminals start, how package management menus work, or when widgets show.

KEEP-10. Do not add runtime dependencies or administrator policy changes.

KEEP-11. Keep lifecycle commands in their current positions.

Background check, capability, cache, and lifecycle commands must not print a start header.
No change to the Python package-operation implementation is necessary for this change request.

## 7. Expected implementation files

| File | Change after implementation approval |
| --- | --- |
| package/contents/tools/sh/upgrade | Select and print the APT and Snap start titles |
| package/contents/tools/sh/messages | Add the two translated source-title resources |
| package/translate/template.pot | Include the new message identifiers |
| tests/test_backends.py | Extend shell output checks for the affected routes |
| README.md | Update marked coverage results if verification includes tests/run_coverage.sh |
| This document | Record implementation evidence and remaining acceptance work |

These paths show the scope of this change request.
The owner gave approval for implementation in these files on 2026-10-26.
Owner approval is necessary before changes to the installed applet.

## 8. Acceptance criteria

Use substitute commands and a temporary helper fixture for shell output checks.
Do not run real package updates to verify a display change.

| Test | Necessary result |
| --- | --- |
| AT-01 | An APT source update prints APT Upgrade once before foreground command output |
| AT-02 | A Snap source update prints Snap Upgrade once before foreground command output |
| AT-03 | An APT package update prints its exact name and architecture with the APT label |
| AT-04 | A Snap package update prints its exact instance name with the Snap label |
| AT-05 | A full sequence prints one start header for each started APT and Snap stage, in the order at the source commit |
| AT-06 | An earlier cancellation skips later headers with their stages |
| AT-07 | A started stage keeps its start header after helper failure, no updates, or cancellation |
| AT-08 | Stage results, exit codes, confirmations, and completion output are the same as before this change |
| AT-09 | Header text uses gettext resources. A title with no translation uses its specified English text |
| AT-10 | A start header does not change command arguments or cause execution of package text |
| AT-11 | Flatpak and other backend start headers are the same as before this change |
| AT-12 | A stage with no available system Python prints its start header before the dependency error |
| AT-13 | With system Python available, lifecycle start runs before the first APT or Snap start header |

Use the shell fixtures in ShellLifecycleTests where possible.
Make sure that each stage prints its start header once before its foreground command output.
Do tests of foreground command success, failure, cancellation, and no available updates.
Make sure that a missing system Python does not remove the start header.
Use subprocess.DEVNULL for test subprocess standard input.

### Verification procedure

The commands below start from the repository root.
The owner's implementation approval includes these local verification commands.

1. Run the shell regression tests.

   ```bash
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -B -m unittest -v test_backends.ShellLifecycleTests
   ```

2. Do a syntax check of the executable shell script.

   ```bash
   bash -n package/contents/tools/sh/upgrade
   ```

3. If msgfmt is available, validate the translation template.

   ```bash
   msgfmt --check --check-format -o /dev/null package/translate/template.pot
   ```

4. If msgfmt is not available, record that template validation is not completed.

5. Run the coverage command.

   ```bash
   ./tests/run_coverage.sh
   ```

The coverage command can create a development virtual environment and install pinned test dependencies there.
It also updates marked results in README.md.
It does not install application dependencies or change host packages.

Record the commands and results in this change request.
Do not state that an acceptance criterion passed without its test result.

## 9. Completion and final checks

The change is completed when all applicable acceptance criteria pass.
Record the source revision, changed files, and verification results in this document.
Record the checks that are not available.
Do not claim interactive desktop verification from substitute-command tests.

Before you create a Git commit, get approval from the owner.
Before you push this change, get approval from the owner.
Before you install the applet, get approval from the owner.
Before you restart Plasma, get approval from the owner.
This change request does not give those approvals.

### Document check on 2026-10-26

Revision 1.1 corrects the word and rule errors found in revision 1.0.
The corrections include verb forms, semicolons, conditions, and sentences with more than one instruction.
Technical term tables give the software meanings used in this change request.
The verification procedure gives exact commands.
Implementation approval was not available at revision 1.1.
No product code changed during this document check.

The source check found the expected commit and valid local links.
An automated check counted words in prose lines.
The same check included a search for listed error patterns.
That word count did not include tables, commands, or titles.
That check does not replace a full dictionary check by another person.

Revision 1.2 removes the remaining uses of check as a verb.
The changes include instructions, term definitions, and source descriptions.
HEAD-02 names the helper's foreground command.
The earlier lifecycle start command keeps its position.
The acceptance criteria include that order.

Revision 1.3 corrects four additional dictionary errors. [S01]
The corrections include approval statements, time expressions, and the scope of document approval.
The instruction for unavailable checks uses a different sentence structure.
These corrections do not change the technical scope.
The full dictionary check remains open.

### Implementation on 2026-10-26

The implementation uses source commit 468a5d0ea4e2ee7d5fd10a4a575fc7f2326357c7 with local file changes.
The owner gave approval for these changes on 2026-10-26.
The current approval does not include a Git commit, applet installation, or Plasma restart.

The native_upgrade function selects the title from the backend, action, and package argument.
It prints the start header before the Python availability check and foreground command.
The lifecycle start command keeps its position before the update stages.
The foreground command keeps its original arguments and exit code.

The messages file includes APT Upgrade and Snap Upgrade resources.
Single-package titles use UPGRADE_PACKAGE and the exact native identity.
The translation template includes the two new source titles.
No Python helper code changed.

The test fixture copies the shell scripts to a temporary directory.
A substitute helper records foreground arguments and returns specified exit codes.
Lifecycle commands use the original helper with temporary configuration and cache directories.
The fixture uses no real APT, Snap, or Flatpak update command.

Six additional shell regression tests include cases of titles, ordering, translations, failure, cancellation, and no available updates.
They also include cases of package text as data and a missing system Python.
The missing-Python fixture changes only the detection line in its temporary script copy.
The Flatpak single-package test also verifies its start header.

Before implementation, the source-title test failed for all four APT and Snap routes.
After implementation, all 11 ShellLifecycleTests passed.
The executable shell script passed bash -n.
The msgfmt program was not available.
Native translation-template validation is not completed.
Python checks of POT string syntax and the new message entries passed.

The full coverage command passed 160 Python tests and 66 JavaScript tests.
Python combined statement and branch coverage was 85.52 percent.
JavaScript coverage was 95.33 percent for lines, 76.00 percent for branches, and 91.88 percent for functions.
The README coverage values are the same as before this change.
The Git whitespace check passed.

| Acceptance criteria | Local evidence |
| --- | --- |
| AT-01 through AT-04, AT-13 | Four routes print one title before foreground output and its simulated administrator prompt. Lifecycle start runs first |
| AT-05, AT-11 | A mixed full sequence keeps APT, Snap, and Flatpak order. The Flatpak single-package title remains present |
| AT-06 | Cancellation in the APT stage skips the Snap and Flatpak stages and their titles |
| AT-07, AT-08 | Failure, cancellation, and no-update cases keep their titles. Native stage codes and sequence results keep their meanings |
| AT-09 | Substitute gettext output verifies translated titles. Tests with no translation verify the English titles |
| AT-10 | Names with spaces, quotes, and shell substitution text reach the fixture as data without command execution |
| AT-12 | Both backends print their title before the missing-Python error. Their stage exit code remains 127 |

The Arch, AUR, widget, and firmware header code did not change.
No real package update ran during these tests.
The installed applet and desktop configuration did not change.
Interactive terminal verification is not completed.
The full STE dictionary check remains open.

## 10. Related record

The [APT and Snap implementation request](2026-10-25_CHANGE_REQUEST_APT_SNAP.md) records the backend design at the source commit.
This change request adds terminal start headers to that design.
The current approval is for implementation and local verification only.

## 11. Language source

| ID | Source | Use |
| --- | --- | --- |
| S01 | [Official ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf), 2025-01-15 | Parts 1 and 2. Page 2-0-17 gives recurring word errors |
| S02 | [Official ASD-STE100 FAQ](https://asd-ste100.org/STE_faq.html) | The approved part of speech for check |
