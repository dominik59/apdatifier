# Change request for the APT operation summary

| Field | Value |
| --- | --- |
| Request ID | CR-APT-OPERATION-SUMMARY-001 |
| Revision | 1.5 |
| Date | 2026-10-28 |
| Product | Apdatifier for KDE Plasma 6 |
| Repository | https://github.com/dominik59/apdatifier |
| Source commit | 7adc546ac5bd826405df953067506db90bc48e32 |
| Status | Optional cleanup explanation implemented. Local verification passed |
| Current approval | Implementation and local verification, 2026-10-28 |
| Document language | English |
| Language reference | ASD-STE100, Issue 9, 2025-01-15 |
| Language status | STE writing rules applied. Full dictionary review remains open |

## 1 Purpose and authority

Show a complete APT operation summary before the user gives confirmation.
Put each package in a group for its operation.
Show possible autoremove packages in a separate information group.
Use the language of the user's session for application text.

The owner supplied an APT terminal log on 2026-10-28.
The owner requested this document after analysis without file changes.
On 2026-10-28, the owner gave approval for implementation and local verification.

AUTH-01. Get implementation approval before changes to application code, executable tests, or translation catalogs.

AUTH-02. Use the latest owner instruction to determine the approval scope in a later session.

AUTH-03. Keep unrelated local work.

This document gives the requirements, source evidence, proposed design, and acceptance criteria.
No previous conversation is necessary.
Repository paths start at the repository root.
Local links start at this document's directory.

### 1.1 Work in a later session

1. Read this document and the applicable AGENTS.md files.
2. Record the current Git commit and working tree state.
3. Compare the current source with the baseline in section 3.
4. Use current source if the baseline commit is unavailable.
5. Apply the latest owner approval before implementation.
6. Use section 9 for verification after implementation.

Related change requests supply background only.
Their approval records do not authorize this implementation.

## 2 Terms and language

| Technical noun | Meaning in this document |
| --- | --- |
| Operation summary | The application report before confirmation of an APT package operation |
| Transaction | The package operations that one APT command selects |
| Simulation | An APT command that calculates operations without changes to installed packages |
| Record | One operation line from an APT simulation |
| Native identity | A package name and architecture, such as example:amd64 |
| Native selector | The package token before version details in an APT operation record |
| Architecture | The package architecture that APT or dpkg identifies |
| Candidate version | The version that the transaction selects for installation |
| Downgrade | Installation of an earlier package version |
| Reinstallation | Installation of the same package version |
| Purge | Removal that also removes package configuration files |
| Configuration | The dpkg operation that completes package setup |
| Autoremove candidate | A package that APT identifies as an unused automatic dependency |
| Deferred update | An available update that APT does not select under its current policy |
| Phased update | An update that Ubuntu supplies to groups of computers at different times |
| Helper | The Python program at package/contents/tools/backends.py |
| Parser | The software that reads command text into data records |
| Diagnostic | A command warning, error, or other necessary explanatory message |
| Locale | The language and regional settings of the user's session |
| Translation catalog | A gettext PO source file or its compiled MO file |
| Fallback text | The English source text shown when no applicable translation is available |
| Fixture | Test data or substitute software for a controlled test |
| Baseline | The source commit and observations in section 3 |

The technical verbs below refer to software operations. [S01]

| Technical verb | Meaning in this document |
| --- | --- |
| Call | Start a software function |
| Compile | Convert a translation source file into its runtime catalog |
| Parse | Read command text into data records |
| Print | Write text to terminal output |
| Run | Start a software program or command |
| Return | Give a result or exit code from a function or process |
| Translate | Supply text in another language through a translation catalog |
| Update | Change a software data file or install a later package version |

Use the active voice and short sentences.
Give one instruction in each procedural sentence.
Use a maximum of 20 words in a procedural sentence.
Use a maximum of 25 words in a descriptive sentence.
Use each technical term with one meaning.
Keep exact product names, commands, paths, and identifiers. [S01]

ASD-STE100 also controls word meanings, parts of speech, and word forms.
Use check as a noun in this document. [S02]
A sentence-length check alone does not prove full conformity.
Complete the dictionary review before a full ASD-STE100 conformity statement.

These language rules apply to the English change request.
The application's translated text uses the spelling and grammar of its target language.

## 3 Baseline and source evidence

The baseline commit is 7adc546ac5bd826405df953067506db90bc48e32.
The working tree had no changes before preparation of this document.
The local APT version reported 3.2.0.
Function names identify source locations if later changes move line numbers.

| Source location | Observed behavior |
| --- | --- |
| [backends.py](../../package/contents/tools/backends.py), redact | Removes credentials and keeps only the last 6000 characters |
| backends.py, parse_simulation | Reads Inst, Remv, and Conf records. Omits Conf records from its result |
| backends.py, parse_simulation | Ignores Purg records because its operation filter does not include them |
| backends.py, AptBackend.installed | Reads package versions and architectures. Keeps only packages with the installed state |
| backends.py, AptBackend.command | Selects native commands for upgrades, installation, removal, purge, and autoremove |
| backends.py, apt_foreground | Parses the simulation, applies transaction guards, and prints redact(preview) |
| backends.py, apt_foreground | Uses dpkg --compare-versions to identify downgrades before confirmation |
| backends.py, Runner.run | Sets LC_ALL=C and LANGUAGE=C for captured command output |
| backends.py, gettext.translation | Selects the user's translation catalog with English fallback text |
| [Translation sources](../../package/translate/po) | Contains 14 language or regional catalogs |
| [merge](../../package/translate/merge) | Extracts Python messages into the translation template |
| [build](../../package/translate/build) | Compiles PO catalogs into the application's locale directory |
| [APT tests](../../tests/test_backends.py), AptPlanTests | Covers dependencies, removals, architecture identity, annotations, exclusions, and downgrade consent |
| [Interface tests](../../tests/test_backend_interfaces.py), NativeBoundaryTests | Covers native command arguments and confirmation behavior |

### 3.1 Supplied transaction

The [source-log fixture](../../tests/fixtures/apt/2026-10-28-upgrade-preview.txt) contains the simulation segment from the owner's supplied terminal log.
It starts at Reading package lists and ends after the final Conf record.
It preserves package names, versions, architectures, dependency annotations, line order, and line wrapping.
It omits the terminal frame, repository-refresh output, authentication prompt, and final application question.
The retained segment contains no account names, credentials, or repository URLs.
The fixture uses UTF-8 text with LF line endings and a final newline.
Captured output is test data, not STE prose.

The original log does not show the captured command's display settings.
Tests must supply the preview conditions from section 5.3 separately.
The fixture must not serve as evidence that those settings were active in the original command.

The supplied log contains these results:

| Item | Package count |
| --- | ---: |
| New installations | 8 |
| Upgrades | 12 |
| Downgrades | 0 |
| Removals in this transaction | 0 |
| Updates deferred because of phasing | 6 |
| Possible autoremove packages | 7 |
| Packages with an operation in this transaction | 20 |

An in-memory parser test reproduced the 8 installations and 12 upgrades.
A separate test parsed all 250 packages from an 11000-character simulation.
The current print path kept only 6000 characters and lost the first package.
A Purg test returned no operation from the current parser.
These tests did not run package changes or write application files.

Use this fixture directly for AT-01, AT-13, and AT-19.
Do not recreate their input from the expected report in section 7.
Supply separate package-data fixtures when a test needs metadata absent from the supplied log.
Do not present such additional metadata as captured source data.

### 3.2 Native behavior

APT simulation records describe unpacking, configuration, and removal operations. [S03]
APT also emits Purg for removal with configuration files. [S04]
The application must combine matching Inst and Conf records into one package row.

APT can print the candidate version in a Conf record without a matching Inst record. [S04]
The owner reproduced this behavior in a private APT 3.2.0 simulation.
The dpkg state contained an unpacked package at version 1.0-1.
The simulation emitted Conf with candidate version 2.0-1 and no Inst operation for that package.
The report must obtain the current version from dpkg for this case.

APT already supplies the possible autoremove list during the supplied upgrade simulation.
APT display configuration can hide this list or replace it with a count. [S05]
Thus, an absent list does not always prove that no candidates exist.
APT normally omits the candidate section when its candidate count is zero. [S05]
The owner also reproduced a hidden nonempty list with quiet=2 and HideAutoRemove=false.
APT output initialization suppresses the list's output stream at that quiet level. [S11]

The candidate list describes the selected simulation state.
It does not guarantee the result of a later autoremove command.
Other package operations can change the candidate list.

## 4 Scope

Apply the report to these foreground helper actions:

| Action | Report scope |
| --- | --- |
| upgrade | All package operations in the selected upgrade plan |
| upgrade-package | The selected package and all dependency operations |
| install | The selected packages and all dependency operations |
| install-version | The selected version and all dependency operations |
| local-install | The local DEB package and all dependency operations |
| remove | The selected packages and all related removals |
| purge | The selected packages and removal of their configuration files |
| autoremove | The package removals selected by this explicit action |

The APT stage in a full update sequence uses the same report.
The clean and autoclean actions keep their archive-removal message.
They do not show archive files as package removals.

This request concerns packages, not a list of paths inside each DEB archive.
It does not add a second package solver, a translation service, or a new runtime dependency.
It does not change reports for Snap or other package sources.

## 5 Required report behavior

### 5.1 Operation groups

Use the following English source labels.
Translate these labels through the application's catalogs.

| Group | Selection rule | Version display |
| --- | --- | --- |
| Install | Inst selects a package without a previous installed version | New version |
| Upgrade | Inst selects a version later than the installed version | Old version -> new version |
| Downgrade | Inst selects a version earlier than the installed version | Old version -> new version |
| Reinstall | Inst selects the same version as the installed version | Current version -> same version |
| Remove | Remv or Purg selects removal | Previous version, when available |
| Configure | Conf selects configuration without a matching Inst record | Current version from dpkg |

REPORT-01. Print the operation summary before the existing transaction confirmation.

REPORT-02. Print each package on its own row within its applicable group.

REPORT-03. Show the complete native identity and version fields on each operation row.

REPORT-04. Sort rows by package name and architecture within each group.

REPORT-05. Use the group order in the table above.

REPORT-06. Show a count of zero for each empty operation group.

REPORT-07. Keep complete names and versions when the terminal wraps a long row.

REPORT-08. Print every planned package without a character or row limit.

REPORT-09. Combine an Inst record and its matching Conf record into one operation row.

REPORT-10. Identify Purg as removal that also removes package configuration files.

REPORT-11. Include purge operations in the Remove count only once.

REPORT-12. Show a separate Configure row for each package with only a Conf operation.

REPORT-13. Calculate the transaction total from distinct native identities with actual operations.

REPORT-14. Keep deferred updates and autoremove candidates outside the transaction total.

REPORT-15. Show an explicit message when the transaction contains no package operations.

REPORT-16. Keep useful APT diagnostics that the new report does not replace.

REPORT-17. Remove duplicate package lists and raw operation records from the application report.

REPORT-18. Keep credential removal for diagnostic text without a length limit on package rows.

REPORT-19. Do not infer missing package identities, architectures, or versions.

REPORT-20. Stop before execution if required transaction data is invalid or contradictory.

REPORT-21. Combine Conf only with an Inst operation for the same native identity.

REPORT-22. Reject Conf with Remv or Purg before confirmation, regardless of record order.

APT controls its output during the subsequent real operation.
This change replaces the application's simulation report before confirmation.
It does not suppress the real operation's progress, diagnostics, or native questions.

### 5.2 Version comparisons and removal data

Use dpkg version rules for version order. [S06]
Alphabetic sorting cannot determine Debian package version order.
Different version strings can compare as equal under dpkg rules.

DATA-01. Use dpkg --compare-versions for version comparisons.

DATA-02. Use the comparison results again for downgrade consent and report groups.

DATA-03. Put versions that compare as equal in the Reinstall group.

DATA-04. Stop before execution if dpkg cannot compare the selected versions.

DATA-05. Read package data for Purg records that refer to remaining configuration files.

DATA-06. Keep the distinction between installed packages and packages with only remaining configuration files.

DATA-07. Accept repeated dependency annotations that the current parser already accepts.

DATA-08. Reject malformed operation records before transaction execution.

DATA-09. For a standalone Conf record, read the current version, architecture, and state from dpkg.

DATA-10. Do not use the Conf candidate field as the configured version.

DATA-11. Include unpacked and half-configured packages in this lookup.

DATA-12. Keep this lookup separate from the installed-package inventory.

DATA-13. Stop before execution if required Configure data cannot be established.

DATA-14. Do not infer an upgrade or downgrade from a standalone Conf candidate field.

DATA-15. For Inst, use the installed-package inventory or the previous version explicitly supplied by APT.

DATA-16. Do not use config-files metadata as a previous installed version for Inst.

DATA-17. Do not use candidate architecture fields to identify standalone Conf operations.

DATA-18. For standalone Conf without an architecture suffix, use one applicable current dpkg package record.

DATA-19. Reject ambiguous current dpkg identities without selecting one from candidate fields.

The existing installed-package inventory omits configuration-only packages.
Purge support must obtain their identity without treating them as installed packages.
The same inventory omits unpacked and half-configured packages.
Read their current versions from dpkg for standalone Conf operations.
Use the version selected by Inst when the same transaction also contains a matching Inst record.
Use an additional read of package data only when existing data is insufficient.

### 5.3 Optional cleanup information

AUTO-01. Print a separate Optional cleanup group with a package count.

AUTO-02. Use the candidate list from the existing operation simulation.

AUTO-03. Select display options that expose the complete candidate list during that simulation.

AUTO-04. Apply those display options only to captured preview commands.

AUTO-05. Do not add a second APT simulation only to obtain the candidate list.

AUTO-06. Print each candidate on its own row.

AUTO-07. Obtain each candidate's architecture and installed version from available package data.

AUTO-08. Sort candidates by package name and architecture.

AUTO-09. Show Optional cleanup: 0 only when the zero-candidate conditions below hold.

AUTO-10. Show Candidate list unavailable when the candidate section cannot be read completely.

AUTO-11. Do not show an unavailable candidate list as a count of zero.

AUTO-12. Keep a candidate outside the Remove group unless the transaction actually selects its removal.

AUTO-13. Do not add autoremove to the real command because candidates exist.

AUTO-14. For an explicit autoremove action, show the selected packages in the Remove group.

AUTO-15. Do not duplicate selected removals in the Optional cleanup group.

AUTO-16. Keep APT protection rules for kernel packages in control of candidate selection.

AUTO-17. Set the preview display options to the values in the table below.

AUTO-18. Override inherited quiet and candidate-display settings without changing the real command.

AUTO-19. Unless autoremove was explicitly requested, treat missing candidate output as unavailable when a zero-candidate condition is unverified.

AUTO-20. Do not infer zero from a failed, incomplete, suppressed, or unfamiliar preview.

AUTO-21. Identify the displayed candidates as optional cleanup.

AUTO-22. State that the current operation does not remove the listed candidates.

AUTO-23. Explain that removal requires a separate autoremove operation.

AUTO-24. Show these explanations only when the displayed candidate list is nonempty.

The Optional cleanup group is information for a later cleanup decision.
It does not select cleanup or provide cleanup confirmation.
A real autoremove operation requires the existing explicit autoremove action.

Use these command-line overrides for the captured operation preview:

| Option | Required value | Purpose |
| --- | --- | --- |
| quiet | 0 | Keep the candidate-list output stream enabled |
| APT::Get::HideAutoRemove | false | Show the full list instead of hiding it or showing a count |
| APT::Get::Show-Versions | false | Keep version annotations outside candidate name lists |
| APT::Get::List-Columns | false | Avoid column-dependent list formatting |
| APT::Color | false | Keep terminal color sequences outside parser input |

For example, use -o quiet=0 and -o APT::Get::HideAutoRemove=false.
Apply the overrides after inherited options that could conflict with them.
Keep LC_ALL=C and LANGUAGE=C under LANG-10.
Verify the effective options at the command boundary for supported APT output forms.
HideAutoRemove=false alone is insufficient when quiet=2 suppresses the output stream. [S05] [S11]

An absent candidate section means zero only when all these conditions hold:

1. The simulation uses an APT version and output form covered by the native fixture tests.
2. The command completes with exit code zero.
3. The helper captures complete standard output without truncation.
4. The output contains a recognized normal transaction summary.
5. The required preview display overrides take effect.
6. The effective cleanup mode has APT::Get::AutomaticRemove=false.
7. No candidate list, candidate-count message, or malformed candidate section occurs in the output.

Read the effective cleanup mode without changing its value.
Do not add another simulation to establish that mode.
For an explicit autoremove action, show actual removals under AUTO-14.
An absent information section for that action does not establish a separate empty candidate list.

| Observed preview | Candidate result |
| --- | --- |
| Complete candidate section with valid package identities | The parsed list and its package count |
| No candidate section and all seven conditions hold | Optional cleanup: 0 |
| No candidate section and at least one condition is unverified | Candidate list unavailable |
| Count-only, malformed, or incomplete candidate section | Candidate list unavailable |
| Explicit autoremove without a separate candidate section | Actual removals only. Optional cleanup information is not applicable |

Candidate availability does not alter the selected package operations.
Keep native package-selection settings intact.

### 5.4 Deferred updates and diagnostics

Ubuntu supplies phased updates to groups of computers at different times. [S09]

INFO-01. Show deferred packages in a separate information group.

INFO-02. Show the package count for each deferred-update reason that APT supplies.

INFO-03. Identify phased updates only when APT supplies that reason.

INFO-04. Do not label all unselected updates as phased updates.

INFO-05. Keep native holds, exclusions, and phased-update decisions effective.

INFO-06. Keep useful warnings from standard output and standard error visible.

INFO-07. Preserve unfamiliar explanatory text instead of silently discarding it.

INFO-08. Use translated application text to identify unavailable optional information.

INFO-09. Capture both standard output and standard error for every APT simulation preview.

INFO-10. Keep stderr diagnostics separate from operation records.

INFO-11. Remove credentials from captured stderr before any terminal output.

INFO-12. Apply the same rule to preliminary eligibility checks and cleanup-policy reads.

INFO-13. Keep interactive terminal access available for administrator authentication.

An unreadable information group does not prove that the transaction contains no operations.
Invalid required transaction data must stop execution under REPORT-20.
Optional candidate information can show an unavailable state without changing a valid transaction.

## 6 Language requirements

Use the language of the desktop session that starts the operation.
This follows the user's language preferences, which can differ from the computer's default locale.
The existing gettext mechanism reads LANGUAGE, LC_ALL, LC_MESSAGES, and LANG in that order. [S07]

LANG-01. Use the existing gettext domain and locale directory for new application text.

LANG-02. Use the session language for group labels, totals, explanatory messages, and affected confirmation text.

LANG-03. Add complete translations for affected messages to all 14 existing catalogs.

LANG-04. Keep existing translations outside this change's message set.

LANG-05. Use English fallback text when a message or applicable catalog is unavailable.

LANG-06. Keep correct language characters, spelling, and grammar in each translation.

LANG-07. Use gettext plural forms when a sentence changes with the package count.

LANG-08. Keep count-independent labels when they remove the need for plural sentences.

LANG-09. Do not translate package names, architectures, version strings, or native operation identifiers.

LANG-10. Keep LC_ALL=C and LANGUAGE=C local to commands whose captured output the parser reads.

LANG-11. Do not replace the helper's session language with the parser's command language.

LANG-12. Include new messages and necessary plural forms in the translation template.

LANG-13. Compile catalogs through the existing translation build process before package delivery.

LANG-14. Do not require a network connection or translation service for report text.

LANG-15. Keep accepted confirmation answers consistent with the displayed prompt.

The existing catalog codes are:

```text
de  es  fr  hu_HU  ko  nl  pl  pt_BR  ru  tr  uk  zh_CN  zh_HK  zh_TW
```

The English source messages supply the fallback text.
English does not require a separate catalog.
Additional languages require additional translated catalogs, but not new report logic.

Application translations cover the report and its own explanatory messages.
They do not translate arbitrary native diagnostics from captured APT output.
Preserve such diagnostics with a translated application label when necessary.

## 7 Example operation summary

The following example uses the source-log fixture from section 3.1.
It shows the English source labels before translation.
Terminal wrapping can change the visual layout.
The package data and counts must remain complete.

```text
Install (8)
  linux-headers-7.0.0-42:all -> 7.0.0-42.42
  linux-headers-7.0.0-42-generic:amd64 -> 7.0.0-42.42
  linux-image-7.0.0-42-generic:amd64 -> 7.0.0-42.42
  linux-main-modules-v4l2loopback-7.0.0-42-generic:amd64 -> 7.0.0-42.42
  linux-main-modules-zfs-7.0.0-42-generic:amd64 -> 7.0.0-42.42
  linux-modules-7.0.0-42-generic:amd64 -> 7.0.0-42.42
  linux-tools-7.0.0-42:amd64 -> 7.0.0-42.42
  linux-tools-7.0.0-42-generic:amd64 -> 7.0.0-42.42

Upgrade (12)
  bpftool:amd64 7.7.0+7.0.0-38.38 -> 7.7.0+7.0.0-42.42
  google-chrome-stable:amd64 156.0.8078.47-1 -> 156.0.8078.73-1
  linux-generic:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-generic-hwe-24.04:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-generic-hwe-26.04:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-headers-generic:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-headers-generic-hwe-26.04:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-image-generic:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-image-generic-hwe-26.04:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-libc-dev:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-perf:amd64 7.0.0-38.38 -> 7.0.0-42.42
  linux-tools-common:all 7.0.0-38.38 -> 7.0.0-42.42

Downgrade (0)
Reinstall (0)
Remove (0)
Configure (0)

Deferred because of phasing (6)
  drkonqi
  gir1.2-mutter-18
  libmutter-18-0
  mutter-common
  mutter-common-bin
  rtkit

Optional cleanup: 7
These packages will not be removed during this operation.
You can remove them with a separate autoremove operation.
  linux-headers-7.0.0-38
  linux-headers-7.0.0-38-generic
  linux-image-7.0.0-38-generic
  linux-main-modules-zfs-7.0.0-38-generic
  linux-modules-7.0.0-38-generic
  linux-tools-7.0.0-38
  linux-tools-7.0.0-38-generic

Transaction total: 20
Install: 8, Upgrade: 12, Downgrade: 0, Reinstall: 0, Remove: 0, Configure: 0
Deferred updates: 6
Optional cleanup: 7

Run this APT operation? [y/N]:
```

The supplied log does not identify architectures or installed versions for the autoremove candidates.
The implementation adds those fields from package data under AUTO-07.
It also retains architecture suffixes that APT supplies for deferred packages.
The real report translates its labels and confirmation text through the session's catalog.

## 8 Proposed implementation and affected files

Keep transaction selection in APT.
Use the simulation that apt_foreground already obtains.
Do not replace apt-get with apt for this change.
APT recommends its specialized command tools for scripts. [S08]

1. Extend the record parser for Purg and configuration-only operations.
2. Obtain current dpkg data for standalone Conf records and missing removal identities.
3. Apply transaction guards to both Remv and Purg.
4. Compare versions through a shared comparison function.
5. Read optional information groups from the same captured simulation.
6. Print complete translated rows and counts from the resulting data.
7. Request the existing downgrade consent when necessary.
8. Request the existing transaction confirmation.
9. Start the original real command after confirmation.

Build a package-name index once when architecture lookup requires it.
Use the installed-package data again for report fields and candidate details.
Do not start one metadata command for each displayed package.
Do not repeat a version comparison only to print a row.
Test gt before lt when different version strings need an order.
If both comparisons are false, use Reinstall.
Sorting can use O(n log n) time for n displayed rows.
Report preparation must not require another dependency-resolution pass.

Separate diagnostic credential removal from diagnostic length limits where necessary.
Do not remove the existing length limit from unrelated error paths.
Do not print a package report through a function that keeps only its final characters.

| File | Expected change after implementation approval |
| --- | --- |
| [backends.py](../../package/contents/tools/backends.py) | Read complete operation data, apply guards, and print the translated report |
| [test_backends.py](../../tests/test_backends.py) | Extend parser, policy, and version-comparison tests |
| [test_backend_interfaces.py](../../tests/test_backend_interfaces.py) | Verify command boundaries, confirmation order, and locale separation |
| tests/test_apt_summary.py | Add focused report, candidate-list, and translation tests if a separate test file helps |
| [Source-log fixture](../../tests/fixtures/apt/2026-10-28-upgrade-preview.txt) | Preserve the supplied simulation input for tests and the report example |
| [template.pot](../../package/translate/template.pot) | Add source messages and necessary plural entries |
| [Translation catalogs](../../package/translate/po) | Add the affected messages in all 14 catalogs |
| [merge](../../package/translate/merge) | Adjust extraction only if new gettext calls require it |
| package/contents/locale | Generate ignored MO files for local verification and package delivery |
| [README.md](../../README.md) | Refresh marked coverage results through the normal verification command |
| This document | Record implementation approval, results, and any remaining acceptance work |

The source baseline ignores compiled locale files in Git.
Keep source translations in PO files.
Use the existing package delivery process for compiled catalogs.

KEEP-01. Keep native holds, exclusions, safe-mode guards, and phased-update policy effective.

KEEP-02. Keep package-selection arguments and real operation commands unchanged.

KEEP-03. Keep administrator authorization, downgrade consent, transaction confirmation, and cancellation behavior effective.

KEEP-04. Keep current JSON schemas and output for background helper commands.

KEEP-05. Keep source order, lifecycle operations, start headers, and terminal-close behavior.

KEEP-06. Keep Python runtime imports within the standard library.

## 9 Acceptance criteria and verification

Use captured data, substitute commands, and private native fixtures.
Do not install, upgrade, downgrade, or remove host packages to verify this report.
Use the existing test infrastructure where possible.

| Test | Necessary result |
| --- | --- |
| AT-01 | The section 3.1 fixture shows 8 installations, 12 upgrades, 0 downgrades, and 0 removals |
| AT-02 | All 20 transaction packages appear with complete names, architectures, and versions |
| AT-03 | Matching Inst and Conf records produce one operation row and one package count |
| AT-04 | A mixed transaction correctly separates installation, upgrade, downgrade, reinstallation, removal, and configuration |
| AT-05 | Version cases include epochs, tilde suffixes, numeric order, and different strings that dpkg considers equal |
| AT-06 | A Purg record appears as removal with configuration files and counts once |
| AT-07 | Purge of remaining configuration files obtains a valid identity without treating the package as installed |
| AT-08 | Remv and Purg both obey exclusions and applicable safe-mode guards |
| AT-09 | Existing repeated dependency annotations and architecture distinctions remain valid |
| AT-10 | Malformed or contradictory required data prevents execution before the real command |
| AT-11 | A report above 6000 characters includes its first package, final package, and every intermediate package |
| AT-12 | Narrow terminal output retains complete identities and versions without a pager dependency |
| AT-13 | The section 3.1 fixture supplies seven autoremove candidates outside the transaction removal count |
| AT-14 | Empty, singular, plural, wrapped, and multicolumn candidate sections produce correct lists |
| AT-15 | Inherited quiet=2 and HideAutoRemove=true or small cannot hide a nonempty list after the preview overrides |
| AT-16 | Unreadable optional candidate data shows an unavailable message without false counts |
| AT-17 | A normal upgrade never starts autoremove because the candidate group is nonempty |
| AT-18 | Explicit autoremove shows actual removals once and does not duplicate them as possible cleanup |
| AT-19 | The section 3.1 fixture supplies six phased updates outside the transaction total |
| AT-20 | Other deferred-update reasons retain their distinction from phased updates |
| AT-21 | Useful diagnostics from both output streams remain visible with credentials removed |
| AT-22 | All affected actions use the report before their existing transaction confirmation |
| AT-23 | A rejected downgrade or transaction confirmation prevents the real package command |
| AT-24 | Empty plans, clean, and autoclean show accurate messages without invented package operations |
| AT-25 | Captured APT output uses C locale while the application report uses the session language |
| AT-26 | LANGUAGE preferences and regional locale fallback select the applicable available catalog |
| AT-27 | Every affected report or confirmation message has a complete translation in all 14 existing catalogs |
| AT-28 | Missing messages or catalogs use English fallback text without an exception |
| AT-29 | Counts of 0, 1, 2, 5, and 22 use correct plural forms where applicable |
| AT-30 | Catalog compilation and placeholder checks pass for every changed translation |
| AT-31 | A catalog for an additional language works without report-logic changes |
| AT-32 | Native command counts show no additional APT simulation or repeated comparison for report display |
| AT-33 | Background JSON output, other package sources, lifecycle order, and terminal headers retain their current behavior |
| AT-34 | Translated confirmation prompts show the accepted answer tokens and preserve cancellation on empty input |
| AT-35 | An unpacked dpkg version 1.0-1 with standalone Conf candidate 2.0-1 shows Configure version 1.0-1 only |
| AT-36 | Missing or ambiguous current dpkg data for standalone Conf prevents execution without candidate-version substitution |
| AT-37 | A successful normalized preview with no candidates omits the section and satisfies all seven zero-candidate conditions |
| AT-38 | A nonempty list hidden by quiet=2 remains unavailable without verified overrides and becomes visible with the required overrides |
| AT-39 | Failed, truncated, unfamiliar, or count-only output never establishes zero candidates |
| AT-40 | Tests AT-01, AT-13, and AT-19 read the stored source-log fixture directly |
| AT-41 | Config-files version 3.0-1, Inst version 2.0-1, and another package's standalone Conf produce Install without downgrade consent |
| AT-42 | Remv or Purg with Conf for the same identity prevents confirmation and execution in either record order |
| AT-43 | Actual subprocess stderr retains useful diagnostics but exposes no credentials on successful or failed primary and eligibility previews |
| AT-44 | Captured stderr leaves controlling-terminal prompts and input available without a real administrator operation |
| AT-45 | Standalone Conf with candidate architecture all uses current dpkg identity example:amd64 and version 1.0-1 |
| AT-46 | Conf combines with its matching Inst across an architecture change in either record order |
| AT-47 | An installation for another architecture does not hide standalone configuration of the current package |
| AT-48 | A nonempty Optional cleanup group explains that its packages require a separate autoremove operation |
| AT-49 | Empty lists, unavailable data, and actual autoremove removals do not receive the optional-cleanup explanation |

Record tests of supported native output forms with their APT version.
Include native fixture coverage for APT 3.2.0 when available.
Use native private fixtures for AT-35, AT-37, and AT-38.
For AT-35, set the dpkg state to unpacked without an Inst operation.
Give the repository a different candidate version from the current dpkg version.
Verify that the resulting report does not invent an upgrade or downgrade.
For AT-37 and AT-38, compare empty and nonempty automatic-dependency states.
Include quiet=2 with HideAutoRemove=false before preview normalization.
Do not claim compatibility with untested output forms.
Use compiled test catalogs for language-selection tests.
Use catalog-content checks to detect empty or fuzzy affected translations.
Do not claim translation quality from placeholder validation alone.
The development guide defines the existing coverage gates. [S10]

### 9.1 Verification after implementation approval

Run commands from the repository root unless a step states another directory.

1. Run the focused parser and command-boundary tests.

   ```bash
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -B -m unittest -v \
     test_backends.AptPlanTests test_backend_interfaces.NativeBoundaryTests
   ```

2. Run the added report and language tests.

   Use their final module and class names.

3. Make sure that the necessary gettext tools are available before translation scripts run.

   The existing scripts can attempt host package installation when tools are missing.
   Do not use that installation path for this change.

4. Do a syntax check of the translation template with msgattrib.

   ```bash
   msgattrib --no-obsolete -o /dev/null package/translate/template.pot
   ```

   The template can contain placeholder values for plural rules.
   Do not treat those template values as compiled catalog rules.

5. Do catalog and format checks of each changed PO file with msgfmt.

   ```bash
   msgfmt --check --check-format -o /dev/null package/translate/po/pl.po
   ```

   The command shows the Polish catalog as an example.
   Apply the same check to all changed PO files.

6. Compile the catalogs with the existing build script from package/translate.

7. Run the complete verification command.

   ```bash
   ./tests/run_coverage.sh
   ```

   This command can create a development environment and install its pinned test dependencies.
   It also changes the marked coverage results in README.md.
   It does not install host application packages.

8. Review the final diff for changes outside section 8.

Record command results and acceptance evidence in this document.
Record unavailable checks with their specific reason.

## 10 Completion evidence

Implementation is complete when all applicable acceptance criteria pass.
The final record must identify the source revision, changed files, test results, and translation results.
The language record must distinguish STE writing-rule checks from a complete dictionary review.

| Item | Status at revision 1.5 |
| --- | --- |
| Change request | Created |
| Implementation approval | Granted on 2026-10-28 |
| Application changes | Implemented in the repository |
| New translations | Complete for the 27 affected messages in all 14 catalogs |
| Acceptance tests | Earlier results in section 10.4. Wording verification passed in section 10.5 |
| Full STE dictionary review | Open |

### 10.1 Review corrections in revision 1.1

| Review item | Correction | Acceptance evidence required |
| --- | --- | --- |
| Configure version | Read the current dpkg version for standalone Conf records | AT-35 and AT-36 |
| Empty autoremove list | Specify preview overrides and seven conditions for zero candidates | AT-15 and AT-37 through AT-39 |
| Missing source input | Store the supplied simulation segment as a source-log fixture | AT-01, AT-13, AT-19, and AT-40 |

### 10.2 Implementation and verification on 2026-10-28

This section records the initial verification for revision 1.2.
Section 10.3 gives the latest review corrections and results.

The helper now prints complete operation groups instead of the raw simulation report.
The report retains names, architectures, versions, deferred updates, and useful diagnostics.
Possible autoremove packages remain separate from actual transaction removals.
The helper exposes the full native candidate list through the specified preview options.
An absent list establishes zero only for verified APT 3.2.0 output and effective cleanup settings.
Other unverified cases show the unavailable state.

The parser accepts Purg records and applies removal guards to them.
Standalone Conf records use current dpkg versions, including unpacked and half-configured package states.
The installed-package inventory keeps its previous fields and selection rules.
Version comparisons use dpkg rules and a shared result cache.
The downgrade confirmation uses those same comparison results.

The report uses the existing session translation mechanism.
Its count-independent labels do not require new plural sentences.
All 14 catalogs contain the 25 affected messages.
Their earlier contents remain intact.
The source template includes all additional messages.

GNU gettext 0.23.2 performed template, catalog, extraction, and compilation checks.
The tools ran from a package extracted into /tmp.
No host package installation was necessary.
The existing build script compiled all 14 application catalogs.
The Ukrainian catalog retained its existing Language-Team header warning.
That warning did not cause a catalog check failure.

| Verification | Result |
| --- | --- |
| Focused report, parser, and native-boundary tests | 45 tests passed |
| Complete verification command | ./tests/run_coverage.sh returned exit code 0 |
| Python suite | 244 tests passed. No skipped tests |
| JavaScript suite | 67 tests passed. No skipped tests |
| Python statement and branch coverage | 86.93 percent. Minimum 80 percent |
| JavaScript line coverage | 95.33 percent. Minimum 80 percent |
| JavaScript branch coverage | 76.17 percent. Minimum 70 percent |
| JavaScript function coverage | 91.88 percent. Minimum 70 percent |
| Bash line coverage | 91.73 percent overall. All nine scripts passed their 80 percent minimum |
| Template and catalog validation | Template syntax and all 14 catalog checks passed |
| Catalog compilation | The existing build script compiled all 14 catalogs |
| Source-log fixture | Reproduced 8 installations, 12 upgrades, 7 autoremove candidates, and 6 phased updates |
| Application language | The compiled Polish catalog supplied report labels and confirmation text |
| Parser language | Captured commands used C locale without changing the report language |
| README results | The complete verification command refreshed the marked coverage sections |

The first complete run encountered sandbox restrictions on sockets and Node.js child processes.
The final run used the same command outside those restrictions.
It passed without skipped tests.

| Acceptance area | Local evidence |
| --- | --- |
| Supplied log and complete output | AptSummaryTests.test_supplied_log_drives_operations_candidates_and_phasing and test_full_report_and_diagnostics_are_not_truncated |
| Operation groups and Debian versions | test_all_operation_kinds_and_debian_version_order and test_comparisons_are_reused_and_incomplete_plans_are_rejected |
| Purge, configuration data, and guards | test_purge_and_configuration_state_validation and existing AptPlanTests |
| Actual standalone Conf behavior | NativeSummaryTests.test_standalone_configuration_uses_actual_unpacked_version |
| Foreground dpkg lookup | test_foreground_configuration_uses_one_batched_state_read |
| Empty, hidden, and unreadable candidate lists | test_candidate_lists_and_availability and NativeSummaryTests.test_quiet_can_hide_nonempty_candidates_and_normalization_restores_them |
| Native cleanup settings and explicit autoremove | NativeSummaryTests.test_native_cleanup_policy_and_explicit_autoremove |
| Deferred reasons and unfamiliar messages | test_unfamiliar_messages_and_deferred_reasons_remain_visible |
| All affected foreground routes | test_each_foreground_action_reports_before_confirmation |
| Command count and real command arguments | test_foreground_uses_one_preview_and_keeps_real_command |
| Comparison failure and cancellation | test_comparison_failure_and_consent_prevent_execution and existing confirmation tests |
| Languages, counts, and catalog fallback | SummaryTranslationTests and GNU gettext validation |
| Other package sources and background behavior | Complete Python and JavaScript suites |

The native private fixtures used APT 3.2.0 without changes to host packages.
Native fixtures reproduced Conf candidate 2.0-1 for unpacked version 1.0-1 without an Inst record.
They also reproduced a nonempty candidate list hidden by quiet=2.
The specified preview overrides restored that list.

Interactive verification in the installed desktop applet remains separate from these local tests.
The full STE dictionary review also remains open.

### 10.3 Review corrections in revision 1.3

The owner identified three additional cases after the initial implementation.
The new regression tests failed before the corrections.
They reproduced an incorrect downgrade, accepted contradictory operations, and credentials in terminal stderr.

Inst records now obtain previous versions only from installed-package data or explicit APT version fields.
Removal and configuration operations can still obtain the applicable metadata from other dpkg states.
Conf combines with Inst only.
Conf with Remv or Purg now stops the transaction before confirmation in either record order.

APT preview commands now request stderr capture explicitly.
This includes the preliminary eligibility simulation and the cleanup-policy read.
The main report processes captured stderr as diagnostics, separately from operation records.
Credential removal applies before diagnostics reach the terminal.
Failed commands also retain credential removal in their error messages.
Other foreground commands keep their previous stderr routing.

The new terminal test uses a pseudoterminal and an authentication substitute.
It verifies visible controlling-terminal prompts and available input while stderr remains captured.
It does not request a real password or start an administrator operation.

| Regression | Evidence |
| --- | --- |
| Config-files metadata during another package's configuration | AptSummaryTests.test_config_files_metadata_does_not_turn_install_into_downgrade |
| Native APT 3.2.0 reproduction | NativeSummaryTests.test_config_files_reinstall_with_pending_configuration_is_install |
| Removal with Conf in either order | AptSummaryTests.test_removal_with_configuration_is_rejected_before_confirmation |
| Credentials in actual subprocess stderr | AptSummaryTests.test_preview_stderr_is_redacted_at_the_process_boundary |
| Interactive terminal access with captured stderr | AptSummaryTests.test_captured_stderr_keeps_controlling_terminal_input_available |

The focused report, parser, and native-boundary command passed 50 tests after these corrections.
The complete verification command then passed outside the sandbox restrictions described in section 10.2.

| Verification after review corrections | Result |
| --- | --- |
| New regression methods | Five passed. The four bug-reproduction methods failed before correction |
| Python suite | 249 tests passed. No skipped tests |
| JavaScript suite | 67 tests passed. No skipped tests |
| Complete verification command | ./tests/run_coverage.sh returned exit code 0 |
| Python statement and branch coverage | 86.93 percent. Minimum 80 percent |
| JavaScript line coverage | 95.33 percent. Minimum 80 percent |
| JavaScript branch coverage | 76.17 percent. Minimum 70 percent |
| JavaScript function coverage | 91.88 percent. Minimum 70 percent |
| Bash line coverage | 91.73 percent overall. All nine scripts passed their minimum |
| README results | The complete command refreshed the marked coverage sections |

No translation message changed in this revision.

### 10.4 Configure architecture correction in revision 1.4

The owner identified a further standalone Conf case after the previous corrections.
The unpacked package had architecture amd64 and version 1.0-1.
The repository candidate had architecture all and version 2.0-1.
APT 3.2.0 emitted Conf with the candidate architecture, without an Inst operation for that package.
The former parser looked for example:all instead of the current dpkg identity example:amd64.

The parser now resolves installation records before configuration records.
It associates matching Inst and Conf records through their native selectors.
A standalone Conf uses its explicit identity or one applicable current dpkg record.
Candidate architecture fields do not select its current identity.
Missing or ambiguous current identities still stop the operation.
An installation for another architecture does not replace the standalone configuration record.

| Verification area | Regression evidence |
| --- | --- |
| Current architecture and ambiguity | AptSummaryTests.test_standalone_configuration_uses_dpkg_architecture_and_rejects_ambiguity |
| Matching installation across an architecture change | AptSummaryTests.test_matching_install_keeps_selected_architecture |
| Separate operations for different architectures | AptSummaryTests.test_other_architecture_install_preserves_standalone_configuration |
| Native APT 3.2.0 reproduction | NativeSummaryTests.test_standalone_configuration_uses_actual_architecture_when_candidate_changes |
| Foreground lookup for both candidate architectures | AptSummaryTests.test_foreground_configuration_uses_one_batched_state_read |

The native fixture reproduced the reported failure before correction.
The focused report, parser, and native-boundary command now passes 54 tests.
The complete verification command then passed outside the sandbox restrictions described in section 10.2.

| Verification after the architecture correction | Result |
| --- | --- |
| Python suite | 253 tests passed. No skipped tests |
| JavaScript suite | 67 tests passed. No skipped tests |
| Complete verification command | ./tests/run_coverage.sh returned exit code 0 |
| Python statement and branch coverage | 86.92 percent. Minimum 80 percent |
| JavaScript line coverage | 95.33 percent. Minimum 80 percent |
| JavaScript branch coverage | 76.17 percent. Minimum 70 percent |
| JavaScript function coverage | 91.88 percent. Minimum 70 percent |
| Bash line coverage | 91.73 percent overall. All nine scripts passed their minimum |
| README results | The complete command refreshed the marked coverage sections |

No translation message changed in this revision.

### 10.5 Optional cleanup explanation in revision 1.5

The owner accepted clearer text for possible autoremove packages.
The report now uses Optional cleanup for the group and final summary.
A nonempty candidate list includes these English source messages:

```text
These packages will not be removed during this operation.
You can remove them with a separate autoremove operation.
```

The report translates the caption and both messages in all 14 supported catalogs.
The labels remain independent of grammatical number.
The affected message set now contains 27 entries.
Existing report tests verify the explanation for nonempty candidate lists and its absence for other states.
They also verify all three translations in each catalog.
The changes do not select an autoremove operation.

The focused report, parser, and native-boundary command passed 54 tests.
GNU gettext validated the template and all 14 catalogs.
The existing build script compiled the application catalogs.
The compiled Polish catalog produced the translated caption and both explanations.

| Verification after the wording change | Result |
| --- | --- |
| Python suite | 253 tests passed. No skipped tests |
| JavaScript suite | 67 tests passed. No skipped tests |
| Complete verification command | ./tests/run_coverage.sh returned exit code 0 |
| Python statement and branch coverage | 86.96 percent. Minimum 80 percent |
| JavaScript line coverage | 95.33 percent. Minimum 80 percent |
| JavaScript branch coverage | 76.17 percent. Minimum 70 percent |
| JavaScript function coverage | 91.88 percent. Minimum 70 percent |
| Bash line coverage | 91.73 percent overall. All nine scripts passed their minimum |
| README results | The complete command refreshed the marked coverage sections |

## 11 Sources

The source review date is 2026-10-28.
Native documentation explains command behavior.
This change request defines the required application behavior.

| ID | Primary source | Use |
| --- | --- | --- |
| S01 | [ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) | Controlled vocabulary, technical terms, sentence structure, and word counts |
| S02 | [ASD-STE100 FAQ](https://www.asd-ste100.org/STE_faq.html) | Approved word meanings and the noun form of check |
| S03 | [apt-get(8)](https://manpages.debian.org/trixie/apt/apt-get.8.en.html) | Simulation, package operations, and autoremove |
| S04 | [APT algorithms.cc](https://sources.debian.org/src/apt/3.0.3/apt-pkg/algorithms.cc/) | Inst, Conf, Remv, and Purg simulation records |
| S05 | [APT private-install.cc](https://raw.githubusercontent.com/Debian/apt/main/apt-private/private-install.cc) | Candidate-list generation and HideAutoRemove display settings |
| S06 | [dpkg(1)](https://manpages.debian.org/trixie/dpkg/dpkg.1.en.html) | Debian version comparisons and package states |
| S07 | [Python gettext](https://docs.python.org/3/library/gettext.html) | Session language selection, catalog fallback, and plural forms |
| S08 | [apt(8)](https://manpages.debian.org/trixie/apt/apt.8.en.html) | Command interfaces for scripts |
| S09 | [Ubuntu phased updates](https://ubuntu.com/server/docs/explanation/software/about-apt-upgrade-and-phased-updates/) | Explanation of updates that Ubuntu supplies in phases |
| S10 | [Development checks](../DEVELOPMENT.md) | Local verification, coverage gates, and generated README results |
| S11 | [APT private-output.cc](https://raw.githubusercontent.com/Debian/apt/main/apt-private/private-output.cc) | Quiet-level suppression of the candidate-list output stream |

The source-log fixture in section 3.1 preserves the supplied input for the transaction example and its counts.
The source commit provides the application observations in section 3.
