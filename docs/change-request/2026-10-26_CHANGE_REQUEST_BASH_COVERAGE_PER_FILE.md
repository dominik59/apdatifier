# Change request: Bash coverage of at least 80 percent for each file

| Field | Value |
| --- | --- |
| Request ID | CR-BASH-COVERAGE-PER-FILE-001 |
| Revision | 1.4 |
| Date | 2026-10-26 |
| Product | Apdatifier for KDE Plasma 6 |
| Repository | https://github.com/dominik59/apdatifier |
| Source commit | 21e48f555cf23facc405cd885a12d444d24941f4 |
| Status | Implemented. Local verification passed |
| Current approval | Implementation, local verification, Git commit, and push, 2026-10-26 |
| Document language | English |
| Language reference | ASD-STE100, Issue 9, 2025-01-15 |
| Language status | STE rules applied. Full word check remains open |

## 1. Purpose and authority

Increase Bash coverage to at least 80 percent for each application script.
Make the coverage command fail when one script is below this minimum.
Show the result for each script in README.md.
The development target is approximately 85 percent for each script.
The acceptance minimum is 80 percent.

This document gives the source evidence, requirements, test cases, and acceptance criteria.
No previous conversation is necessary.
Repository paths start at the repository root.
Local links start at this document's directory.

The owner first asked for analysis of an overall Bash minimum of 80 percent.
The owner then specified a minimum of 80 percent for each file.
The owner accepted the enforcement requirements in section 5.
On 2026-10-26, the owner asked for this change request.
The owner then gave approval for implementation and local verification.
The owner also gave approval for a Git commit and push on 2026-10-26.

AUTH-01. Limit implementation changes to the scope in section 9.

AUTH-02. Use the owner's implementation approval from 2026-10-26 for this change.

AUTH-03. Keep unrelated local work.

AUTH-04. Use the owner's approval for this change's Git commit and push from 2026-10-26.

AUTH-05. Get owner approval before changes to host packages or the installed applet.

AUTH-06. Get owner approval before a Plasma restart.

### 1.1 Start in a new session

This document requires the repository source, but not the previous conversation.
The related change requests give background only.
Their approval records do not give implementation approval for this request.
The local reports, trace files, and development environment can be absent.
Their absence does not remove the requirements or the baseline table.

1. Read this document and the applicable AGENTS.md files.

2. Record the current repository state.

   ```bash
   git status --short --branch
   git rev-parse HEAD
   ```

3. Compare the current source with the baseline commit in section 3.

   If the baseline commit is unavailable, record that condition.
   Use the current repository source for implementation.
   Do not restore old code only to match the baseline commit.

4. Use the latest owner instruction to determine the current approval scope.

   An explicit request to implement this document gives implementation approval.
   The metadata records the implementation approval available for this revision.
   Implementation approval alone does not give approval for the actions in AUTH-04 through AUTH-06.

5. If implementation approval is available, record it in the metadata.

6. After implementation approval, regenerate missing or old reports with tests/run_coverage.sh.

   The command can create the development environment and change the marked README results.
   The implementation can proceed without the original local reports or an earlier environment.

7. Use section 10 for acceptance and section 12 for completion evidence.

## 2. Terms and language

| Technical noun | Meaning in this document |
| --- | --- |
| Application script | A shell source file in package/contents/tools/sh that meets the source rules in section 4 |
| Baseline | The source commit and local measurements in section 3 |
| Command line | A source line that the existing Bash parser identifies as executable |
| Covered line | A command line with at least one recorded execution |
| Coverage | The percentage of command lines with recorded execution |
| Coverage gate | The software decision that compares coverage with its minimum |
| Collector | The program at tests/bash_coverage.py |
| Runner | The program at tests/run_coverage.sh |
| README updater | The program at tests/update_coverage_readme.py |
| Badge | The coverage image link in the marked README section |
| Fixture | Temporary data or files that a test uses |
| Stub | A substitute external command with controlled output, arguments, and exit code |
| Source snapshot | The source text that the Bash trace records |
| Source scope | The set of application paths that the coverage measurement includes |
| Trace | Records of source locations from the Bash DEBUG trap |
| Branch coverage | A measure of execution through alternative code paths |
| Pseudo-terminal | A software terminal that supplies interactive input to a subprocess |
| Process group | A set of related processes that the test can stop together |
| Command substitution | The Bash operation that uses command output as part of another command |
| Declared interpreter | The interpreter that a script's shebang names |
| Line set | The set of command-line numbers for one current source file |
| Launch helper | A test program that starts a script with a specified interpreter |
| Compatibility case | A test that compares Bash results with results from the declared interpreter |
| Native command | A real package, desktop, or system command outside the test fixture |
| Exit code | The integer result that a process gives when it ends |
| Git commit | A record of file changes in the Git repository |

The technical verbs below refer to software processes. [S01]

| Technical verb | Meaning in this document |
| --- | --- |
| Call | Start a software function |
| Create | Make a software file, data object, or process |
| Discover | Find source files through the shared source rules |
| Parse | Read software text into a structure that the parser can examine |
| Print | Write text to terminal output |
| Publish | Write current coverage results to the marked README sections |
| Push | Send Git commits to a remote repository |
| Run | Start a software program or command |
| Return | Give an exit code or result from a software function or process |
| Update | Change a software data file or install a software package version |
| Validate | Compare software data with its specified format |

Use imperative sentences for requirements and work steps.
Keep each instruction within 20 words.
Keep each descriptive sentence within 25 words.
Use the active voice.
Give each technical term one meaning. [S01]

The dictionary also controls meanings, parts of speech, and word forms.
The word check has the noun form in this document. [S02]
Exact commands, identifiers, paths, and source titles keep their original spelling.
A word count alone cannot prove conformity with ASD-STE100.
The full word check against Issue 9 remains open.

LANG-01. Before a full conformity statement, do a word and rule check against ASD-STE100 Issue 9.

## 3. Baseline and source evidence

The baseline commit is 21e48f555cf23facc405cd885a12d444d24941f4.
The working tree had no file changes during the source analysis.
The local Bash report had source hashes that matched all nine scripts.
The report is an ignored local artifact.
The table below preserves its measurements for a later implementation session.

| Script | Covered lines | Total command lines | Coverage | Minimum covered lines | Additional covered lines |
| --- | ---: | ---: | ---: | ---: | ---: |
| arguments | 23 | 23 | 100.00% | 19 | 0 |
| init | 0 | 20 | 0.00% | 16 | 16 |
| management | 0 | 348 | 0.00% | 279 | 279 |
| mirrorlist | 0 | 82 | 0.00% | 66 | 66 |
| terminal | 0 | 31 | 0.00% | 25 | 25 |
| upgrade | 117 | 158 | 74.05% | 127 | 10 |
| utils | 76 | 325 | 23.38% | 260 | 184 |
| vars | 30 | 38 | 78.95% | 31 | 1 |
| widgets | 163 | 257 | 63.42% | 206 | 43 |
| Total | 409 | 1282 | 31.90% | See text below | 624 |

The minimum for each file is the smallest integer at or above 0.8 times its command-line count.
The sum of these individual minimum counts is 1029.
The arguments script already has four covered lines above its minimum.
With all existing covered lines, the minimum final count is 1033 of 1282 lines.
Thus, the tests must execute at least 624 additional command lines at this baseline.

These counts give the minimum necessary increase.
They do not give final measured results.

Source corrections can change the command-line counts.
The final decision uses the final source files and their current reports.
The baseline counts do not replace that measurement.

| Source | Evidence at the baseline |
| --- | --- |
| [Collector](../../tests/bash_coverage.py), sources | Selects shell scripts from the source directory without subdirectories |
| [Collector](../../tests/bash_coverage.py), executable_lines | Uses Tree-sitter syntax nodes to identify command lines |
| [Collector](../../tests/bash_coverage.py), collect | Includes scripts with no execution and matches fixture source text |
| [Collector](../../tests/bash_coverage.py), main | Creates reports without a minimum coverage gate |
| [Trace hook](../../tests/bash_coverage.sh) | Records Bash source locations during the Python test phase |
| [Runner](../../tests/run_coverage.sh) | Creates the development environment and continues after a Bash report failure |
| [README updater](../../tests/update_coverage_readme.py), bash_metrics | Validates source hashes and counts but returns only overall Bash coverage |
| [README updater](../../tests/update_coverage_readme.py), update | Shows a blue Bash badge and no Bash minimum |
| [Shell tests](../../tests/test_backends.py), ShellLifecycleTests | Exercise upgrade scripts through temporary fixtures and stubs |
| [Widget tests](../../tests/test_widgets.py), WidgetUpdateTests | Exercise local archives and substitute external services |
| [Development guide](../DEVELOPMENT.md) | Describes Bash coverage as informational |

The baseline Python minimum is 80 percent for combined statements and branches.
The baseline JavaScript minimums are 80 percent for lines, 70 percent for branches, and 70 percent for functions.
This change keeps those minimums.

## 4. Source scope and measurement

COV-01. Include each application script in package/contents/tools/sh.

COV-02. Use the existing Bash or sh shebang rule to identify scripts.

COV-03. Include applicable scripts in subdirectories of that source directory.

COV-04. Exclude only the named data resources messages and widgets-id from that source scope.

COV-05. Include scripts with no recorded execution at zero coverage.

COV-06. Discover the current source set during each coverage run.

COV-07. Use one shared source discovery function in the collector and README updater.

COV-08. Keep the existing definition of command lines.

COV-09. Keep all command lines in each file's total count.

COV-10. Count fixture execution only when the fixture source matches the current application source.

COV-11. Reject reports with missing sources, duplicate sources, invalid counts, or source hashes from an earlier version.

COV-12. Return a measurement error for an empty source set or a script with zero command lines.

COV-13. Keep branch coverage outside this Bash acceptance minimum.

COV-14. Keep test scripts and development scripts outside the application source scope.

COV-15. Give each new application script a Bash or sh shebang.

COV-16. Keep execution records for different source paths separate, even when names and contents are the same.

COV-17. Keep the runner's trace settings when fixtures start application Bash scripts for coverage.

COV-18. Validate each record's lines keys against executable_lines() for the current source bytes.

COV-19. Reject missing command lines or extra nonexecutable lines, even when the source hash and totals are consistent.

COV-20. Use the same source bytes for the hash and command-line calculation.

COV-21. Use the shared parser for report validation in the collector and README updater.

COV-22. Return a measurement error when the parser cannot validate a report.

COV-23. Run selected sh scripts through Bash when their execution contributes to Bash coverage.

COV-24. Use separate tests with each sh script's declared interpreter to verify its native results.

COV-25. Do not count an execution without a source trace as covered.

COV-26. Record the interpreter and arguments for each sh coverage test.

COV-27. Make the compatibility test fail when Bash and the declared interpreter give different results.

COV-28. Use Bash's normal mode and preserved trace settings for measured sh scripts.

COV-29. Include the source path and line-set error in the diagnostic.

The messages resource has shell-like text but contains translation data.
The widgets-id resource contains identifier data.
These exceptions refer to the two existing resource paths.
A different file with the same name does not receive an automatic exception.

The existing method uses the Bash DEBUG trap and Tree-sitter.
It measures command lines, not separate commands or branches on one line.
This change does not replace that method with another coverage tool.

### 4.1 Measurement contract

The baseline parser selects the following Tree-sitter node types:

```text
command
declaration_command
variable_assignment
test_command
arithmetic_command
for_statement
c_style_for_statement
case_statement
```

A variable assignment within a command or declaration does not add a separate command line.
The collector counts each selected source line once, regardless of the number of nodes on that line.
The line calculation uses the node's start_byte and the preceding newline count.
The existing grammar adjustment for ${value:$index:1} applies only to parser input.
It keeps byte offsets and leaves the application source unchanged.

The trace records source text and source locations.
It does not record expanded command arguments.
The final file counts use the final application source and current trace records.

### 4.2 Exact line-set validation

A correct source hash does not prove that a report contains every command line.
At the baseline, bash_metrics() validates counts without comparison with executable_lines().
A report can omit uncovered lines and keep a valid hash and consistent totals.
For example, removal can change upgrade from 117/158 to 117/117.
The validator rejects that report before a coverage gate or README publication.

For each current source file, the validation decision includes this equality:

```python
expected_keys = {str(line) for line in executable_lines(contents)}
set(record["lines"]) == expected_keys
```

The contents value contains the same current source bytes that supply the source hash.
The comparison uses the complete key sets, not only their sizes.
It rejects omitted command lines, added comment lines, and replacements that keep the same number of keys.
The validator also keeps the existing count, hash, source-list, and schema checks.

A missing parser or parser failure makes the current Bash report unavailable.
The validator does not accept report totals without source parsing.
The runner still performs the independent JavaScript phase.
The preparation-failure path keeps its not-run status without a parser import for an absent report.

### 4.3 Execution contract for sh scripts

Source discovery includes Bash and sh shebangs.
The measurement method requires Bash's BASH_ENV startup file and DEBUG trap.
A direct execution through /bin/sh can finish without those trace records.
The GNU Bash startup rules give different procedures for the names bash and sh. [S04]

For coverage, the launch helper uses this command shape:

```bash
bash --noprofile --norc -- "$script" "$@"
```

The launch helper receives the script path and its original arguments.
It starts ordinary noninteractive Bash with the name bash.
It keeps BASH_ENV and APDATIFIER_BASH_COVERAGE_DIR from the runner.
It does not use the name sh or the --posix option for measurement.
The application source and shebang remain unchanged.

If a parent starts a child directly through sh, that child execution can have no trace.
Its dedicated coverage case starts the unchanged child through the same Bash launch helper.
Each applicable script remains in the source set, regardless of its launch method.
An untraced execution contributes zero hits.
It cannot supply evidence for the 80 percent minimum.

Separate compatibility cases start each sh script through its declared interpreter with the same inputs and equivalent temporary fixtures.
They compare standard output, standard error, exit code, and fixture changes with the Bash case.
A difference causes a compatibility test failure.
The Bash report describes execution under Bash.
The native tests give separate evidence about the declared interpreter.

## 5. Coverage gates and execution order

GATE-01. Set the acceptance minimum to 80 percent for each application script.

GATE-02. Define the minimum in one shared test module.

GATE-03. Use the same comparison function in the collector and README updater.

GATE-04. Compare integer counts before any percentage display calculation.

GATE-05. Accept a file only when 100 times its covered count is at least 80 times its total count.

GATE-06. Return a nonzero runner exit code when one file is below the minimum.

GATE-07. Use the same minimum for new scripts without manual registration.

GATE-08. Do not add exceptions that reduce an individual script's minimum.

GATE-09. Write Bash JSON, LCOV, and HTML reports before a failure exit for low coverage.

GATE-10. Continue the JavaScript phase after a Bash coverage gate failure.

GATE-11. Publish the current results after a Bash coverage gate failure.

GATE-12. Keep the baseline response to Python failures, report failures, and interrupted runs.

GATE-13. Clear reports and traces from earlier runs before the current test phase.

GATE-14. Keep the existing Python and JavaScript coverage minimums.

GATE-15. Validate line completeness before a coverage gate or README publication.

GATE-16. Keep preparation-failure reporting available without installed parser packages.

GATE-17. Remove coverage/bash/index.html before environment preparation or test execution.

For each file, let covered be its covered-line count and total be its command-line count.
The decision is:

```text
PASS when total > 0 and 100 * covered >= 80 * total
FAIL when total > 0 and 100 * covered < 80 * total
MEASUREMENT ERROR when total <= 0
```

For example, 80 of 100 lines gives PASS.
The count 19999 of 25000 gives FAIL.
Its exact percentage is 79.996 percent, although a display with two decimal places shows 80.00 percent.
The displayed percentage does not control the decision.

A second example has two files with counts of 100/100 and 0/1.
Their overall coverage is approximately 99.01 percent.
The second file causes the Bash coverage gate to fail.

A valid report with low coverage remains available for diagnosis.
A missing or invalid report gives a measurement error.
The runner gives a nonzero exit code for either condition.
An overall test failure remains a failure even when every coverage gate passes.

## 6. README and report output

READ-01. Keep the existing README marker pairs.

READ-02. Keep the overall Bash percentage in the coverage summary.

READ-03. Add a table with one row for each application script.

READ-04. Show the path, covered count, total count, percentage, minimum, and gate result in each row.

READ-05. Sort rows by source path.

READ-06. Use a green Bash badge only when every file passes its coverage gate.

READ-07. Use a red Bash badge when a valid current report has a file below 80 percent.

READ-08. Use an unavailable result and a gray badge when the current Bash report is absent or invalid.

READ-09. Keep the overall run status separate from the coverage badge result.

READ-10. Keep valid Python and JavaScript results when Bash measurement fails.

READ-11. Keep README text outside the marked sections.

READ-12. Do not rewrite README.md when the generated text is the same.

The existing marker pairs are:

```html
<!-- coverage-badges:start -->
<!-- coverage-badges:end -->

<!-- coverage-summary:start -->
<!-- coverage-summary:end -->
```

The badge continues to display the overall Bash percentage.
Its color shows the decision for all individual files.
Thus, an overall percentage above 80 can have a red badge.
The table identifies the file that failed its gate.

The source path starts at the repository root.
Valid scripts with no execution show zero covered lines and FAIL.
The minimum column shows 80 percent for each script.
The summary gives the count of scripts that pass their gates.

The updater continues to handle passed, failed, not-run, and interrupted states.
It does not publish percentages from an earlier run after a current measurement failure.
Forced termination can bypass the existing exit handler.
This change does not promise publication after that condition.

## 7. Test design and isolation

TEST-01. Use the existing Python unittest framework.

TEST-02. Use the existing development virtual environment and pinned test dependencies.

TEST-03. Keep the installed application's dependencies unchanged.

TEST-04. Use temporary configuration, cache, local-data, and package directories.

TEST-05. Use stubs for external commands that can change packages, the desktop, or system files.

TEST-06. Use controlled local data for network responses.

TEST-07. Record arguments at external command boundaries.

TEST-08. Make sure that unexpected native commands cause an immediate test failure.

TEST-09. Use a pseudo-terminal for tests that require interactive input.

TEST-10. Set an execution timeout for each interactive test.

TEST-11. Stop the test process group after a timeout.

TEST-12. Remove temporary files and processes after each test.

TEST-13. Use unchanged application copies for tests that contribute to coverage.

TEST-14. Assert the expected output, exit code, arguments, or file changes for each test case.

TEST-15. Include success, failure, and cancellation cases for applicable operations.

TEST-16. Record test cases that cannot run because a necessary development tool is unavailable.

TEST-17. Do not use a skipped test as proof of its acceptance criterion.

TEST-18. Stop the complete process group after a timeout in run_script, function, or interact.

TEST-19. Stop background children after normal completion of a captured-output fixture.

The Python standard library includes subprocess, tempfile, pty, select, and process-control functions.
The existing requirements-test.txt supplies coverage.py and the Tree-sitter packages.
The runner already creates or reuses the development environment.
No additional Bash test framework is necessary for this design.

The fixture uses these environment settings:

| Setting | Fixture value |
| --- | --- |
| APDATIFIER_CONFIG_DIR | Temporary configuration directory |
| APDATIFIER_CACHE_DIR | Temporary cache directory |
| XDG_LOCAL_HOME | Temporary local-data directory |
| TMPDIR | Temporary scratch directory |
| PATH | Controlled command directory and necessary utilities |
| APDATIFIER_BASH_COVERAGE_DIR | Trace directory from the runner |
| BASH_ENV | Trace hook from the runner at tests/bash_coverage.sh |

Tests can use modified source copies for isolated cases.
Those copies do not contribute to application coverage.
The fixture does not erase or replace the runner's trace settings for application coverage tests.

Python 3.11 or later with venv support is necessary for development.
Node.js 22.8 or later is necessary for the JavaScript tests.
The baseline test package versions are:

| Development package | Version |
| --- | --- |
| coverage | 7.17.0 |
| tree-sitter | 0.26.0 |
| tree-sitter-bash | 0.25.1 |

The Python management tests do not replace tests of the Bash management script.
The --legacy argument selects the shell menu in the Bash management script.
A pseudo-terminal supplies menu keys and confirmation input.
The test timeout also stops children that still hold output pipes.

| Script | Necessary test cases |
| --- | --- |
| arguments | Keep quoted arguments, empty values, literal shell text, and invalid quotation tests |
| init | First use, second use, migration of both old cache files, existing cache files, icons, and notification data |
| management | Menu movement, selection, return, help, small terminal, hidden options, missing commands, empty selection, and cancellation |
| management | Package install and removal, orphan removal, cache cleanup, cached package selection, rebuild selection, and Flatpak actions |
| mirrorlist | Valid and invalid lists, download failure, mixed server results, ordering, count limit, progress modes, confirmation, and write failure |
| terminal | Terminal argument variants, quoted command data, invalid operation, Flatpak terminal, tmux states, and Yakuake visibility |
| upgrade | Keep existing APT, Snap, and Flatpak tests. Add idle inhibition, firmware, widget stages, and applicable confirmation paths |
| utils | RSS and Atom, invalid XML, feed limit, duplicate entries, obsolete entries, invalid cache, and partial feed failure |
| utils | Cache combination, icons, installed versions, database synchronization, command detection, and terminal messages |
| utils | Installation preconditions, current version, installation failure, confirmation, cancellation, and removal of temporary installation data |
| vars | Both icon-font settings, translation availability, and configuration values |
| widgets | Available updates, no updates, installed list, API page count, invalid pages, package types, metadata, and download selection |

The test cases above define the necessary functional scope.
The final coverage report determines which additional cases are necessary to meet every file's minimum.
Tests of installation and removal use a temporary applet tree.
Their package and desktop commands are stubs.

## 8. Small source corrections

The main implementation work concerns tests and coverage reports.
Some test cases can expose source defects.
The proposed implementation includes the source changes below.
The owner gave implementation approval on 2026-10-26.

### 8.1 Mirror result handling

The rank_mirrors function has two defects at the baseline.
The source is [mirrorlist](../../package/contents/tools/sh/mirrorlist), near lines 33 through 35.

The declaration local response=$(curl ...) gives the exit code of local.
The assignment loses the exit code of curl.
The GNU Bash manual describes the successful return status of local. [S03]
A small Bash probe confirmed a zero result after local response=$(false).

The declaration local time status does not reset status for each loop iteration.
After one unsuccessful server result, the next iteration can keep Unreachable.
A second small Bash probe confirmed that variable lifetime.
The probes did not perform network requests or change project files.

SRC-01. Separate the response variable declaration from the curl assignment.

SRC-02. Record the curl exit code immediately after its assignment.

SRC-03. Clear the result variables before each server request.

SRC-04. Add regression tests for a connection failure and an unsuccessful server followed by a successful server.

### 8.2 File paths and other source defects

The mirrorlist script sets /etc/pacman.d/mirrorlist directly.
The recentlyInstalled function sets /var/log/pacman.log directly.
These paths make some fixture cases difficult without system access.

SRC-05. Use an optional path override when a specified test case requires a temporary system-file path.

SRC-06. Keep the existing system path as the default value.

SRC-07. Put optional path overrides in environment variables.

SRC-08. Limit other source corrections to defects from the specified test cases.

SRC-09. Record a regression test failure before each source correction.

SRC-10. Record the source defect and its correction in the completion evidence.

SRC-11. Use explicit nonzero exit codes for operation refusal and detected command failures.

SRC-12. Keep the original command exit code after terminal-close output.

The mirror path override is the recommended first source change for fixture isolation.
The management log override is optional if the other tests already meet the file's minimum.
Neither override changes normal user configuration or package-manager policy.
No source rewrite is necessary only to increase the measured percentage.

If implementation uses these overrides, use the names and defaults below.

| Optional environment variable | Default path |
| --- | --- |
| APDATIFIER_MIRRORLIST_FILE | /etc/pacman.d/mirrorlist |
| APDATIFIER_PACMAN_LOG_FILE | /var/log/pacman.log |

An unset or empty variable selects its default path.
The fixture supplies a path in its temporary directory.

## 9. Implementation files and limits

| File or directory | Proposed change |
| --- | --- |
| tests/bash_coverage.py | Shared minimum, integer gate, exact line-set validation, current source discovery, and reports with gate results |
| tests/run_coverage.sh | Failure status for low Bash coverage with continued reports and JavaScript tests |
| tests/update_coverage_readme.py | Exact line-set validation, individual file results, shared gate decision, badge color, and summary |
| tests/test_bash_coverage.py | Source discovery, exact line sets, sh execution contract, count boundaries, new scripts, and report output |
| tests/test_coverage_runner.py | Failed Bash gate, continued execution, report publication, and failure status |
| tests/test_coverage_readme.py | Individual rows, badge decisions, exact counts, altered line sets, invalid reports, and unchanged text |
| tests/test_backends.py | Additional shell upgrade cases and shared fixture use |
| tests/test_widgets.py | Additional discovery, list, API, and metadata cases |
| tests/test_shell_*.py | New shell interface, utility, menu, and mirror test cases |
| tests/shell_fixtures.py | Shared temporary directories, Bash launch helper, command stubs, and pseudo-terminal control if necessary |
| package/contents/tools/sh/mirrorlist | Result handling corrections and an optional fixture path override |
| Other application scripts | Small source corrections under section 8 only |
| README.md | Generated file table, gate results, and corrected coverage description |
| docs/DEVELOPMENT.md | Scope, minimums, test method, output, and limitations |
| This document | Implementation evidence and final acceptance results |

The existing trace hook can remain unchanged if it meets these requirements.
A necessary trace correction requires its own regression test.
The requirements-test.txt pins remain unchanged unless implementation evidence shows a specific incompatibility.

The following work is outside this change request:

- A different Bash coverage engine.
- Bash branch coverage or QML coverage.
- A lower Python or JavaScript minimum.
- New installed application dependencies.
- New CI pipelines or hosted coverage services.
- Real package installation, removal, upgrade, or database changes on the host.
- Installation of the applet or a Plasma restart.
- Git commits and pushes without further owner approval.

## 10. Acceptance criteria

The minimum applies to the final source set.
The approximately 85 percent development target does not replace the 80 percent acceptance minimum.

| ID | Test case | Necessary result |
| --- | --- | --- |
| AT-01 | Complete coverage run | Each application script has at least 80 percent coverage from current traces |
| AT-02 | Exact boundary of 80/100 | File gate gives PASS |
| AT-03 | Counts of 19999/25000 | File gate gives FAIL, even with a displayed 80.00 percent |
| AT-04 | Files with 100/100 and 0/1 | Bash gate and runner fail although overall coverage exceeds 99 percent |
| AT-05 | New unexecuted script in the source directory | Script appears at zero coverage and fails its gate |
| AT-06 | New unexecuted script in a source subdirectory | Script appears at zero coverage and fails its gate |
| AT-07 | Low Bash coverage with valid traces | JSON, LCOV, and HTML reports remain available |
| AT-08 | Low Bash coverage | JavaScript tests still run and publish their current report |
| AT-09 | Low Bash coverage | Runner returns a nonzero exit code after report publication |
| AT-10 | Valid Bash report | README has one row for each script with counts, minimum, percentage, and result |
| AT-11 | All files pass, then one file fails | Bash badge changes from green to red |
| AT-12 | Missing, invalid, incomplete, or old Bash report | Bash result is unavailable, badge is gray, and runner fails |
| AT-13 | Bash measurement failure | Valid current Python and JavaScript results remain in README |
| AT-14 | Test failure with all coverage gates at PASS | Overall run status remains FAILED |
| AT-15 | Interrupted run and incomplete environment | Existing status rules and current-report handling remain correct |
| AT-16 | Identical generated results | README contents do not change |
| AT-17 | Report publication | README text outside the markers does not change |
| AT-18 | Empty source set or script with zero command lines | Measurement fails without a false PASS |
| AT-19 | Existing and modified fixture copies | The collector counts execution from unchanged copies only |
| AT-20 | Failed mirror followed by a successful mirror | The ranked result includes the successful mirror |
| AT-21 | Mirror connection failure | The request's nonzero exit code reaches the failure decision |
| AT-22 | Native-operation and interactive fixtures | Only stubs and temporary data change. Child processes stop after test completion |
| AT-23 | Existing Python and JavaScript suites | Tests and unchanged coverage gates pass |
| AT-24 | Final source discovery | The report includes every applicable current script without manual registration |
| AT-25 | Different source paths with the same name and contents | Execution of one file does not give coverage to the other file |
| AT-26 | Omitted uncovered lines with unchanged source hash and consistent revised totals | Report validation rejects the report before a gate or publication |
| AT-27 | Added comment, blank, or other nonexecutable line with consistent revised totals | Report validation rejects the report even when its source hash matches |
| AT-28 | An executable key replaced by a nonexecutable key with the same key count | Exact set comparison rejects the report |
| AT-29 | Unchanged sh fixture through the Bash launch helper with runner trace settings | Trace records contain its executed command lines and the collector counts them |
| AT-30 | Direct untraced sh execution with a separately traced control script | The sh file remains at zero coverage and fails its gate |
| AT-31 | Compatible and different results through Bash and the declared interpreter | Equivalent results pass the compatibility case. A difference causes test failure |
| AT-32 | Parser unavailable or source parsing failure during report validation | Bash result is unavailable and the runner fails without acceptance of report totals |
| AT-33 | Setup refusal, missing tool, or command failure followed by terminal-close output | Refusal returns 1. Missing tools return 127. Native command failures keep their original nonzero exit codes |
| AT-34 | Timeout or normal completion in run_script and function with background children | Each fixture stops the complete process group. A timeout still raises TimeoutExpired |
| AT-35 | Previous Bash HTML report with a preparation or collector failure | The old index.html is absent. Valid reports from the current run remain available |

## 11. Verification procedure

These steps apply after implementation approval.
The commands start at the repository root.

1. Record the implementation source commit.

   ```bash
   git rev-parse HEAD
   ```

2. Run the complete coverage command.

   ```bash
   ./tests/run_coverage.sh
   ```

   The runner can create the development environment and install pinned test packages there.
   It also changes the marked README results.
   The tests use fixtures for package and desktop operations.

3. Verify the source files, line keys, and integer counts with independent assertions.

   ```bash
   PYTHONPATH=tests "${APDATIFIER_TEST_VENV:-.venv}/bin/python" -B - <<'PY'
   import hashlib
   import json
   from pathlib import Path
   from bash_coverage import executable_lines, sources

   root = Path.cwd()
   expected = {path.relative_to(root).as_posix(): path for path in sources(root)}
   report = json.loads(Path("coverage/bash.json").read_text())
   assert report["files"], "No application scripts in the report"
   seen = set()
   covered_sum = total_sum = 0
   for source in report["files"]:
       name = source["path"]
       assert name in expected and name not in seen, name
       seen.add(name)
       contents = expected[name].read_bytes()
       assert source["sha256"] == hashlib.sha256(contents).hexdigest(), name
       expected_keys = {str(line) for line in executable_lines(contents)}
       assert set(source["lines"]) == expected_keys, name
       assert all(type(hit) is int and hit >= 0 for hit in source["lines"].values()), name
       covered, total = source["covered"], source["total"]
       assert total == len(expected_keys) and total > 0, name
       assert covered == sum(hit > 0 for hit in source["lines"].values()), name
       assert 100 * covered >= 80 * total, name
       covered_sum += covered
       total_sum += total
       print(f"{name}: {covered}/{total} PASS")
   assert seen == set(expected), "Incomplete source set"
   assert (report["covered"], report["total"]) == (covered_sum, total_sum)
   PY
   ```

   This command uses the development environment that the runner selected.
   The assertions compare current source files, exact line sets, source hashes, and final counts.
   The collector and updater also validate report integrity and schema.

4. Do a syntax check of every application script through the shared source rules.

   ```bash
   PYTHONPATH=tests python3 -B - <<'PY'
   from pathlib import Path
   import subprocess
   from bash_coverage import sources

   for source in sources(Path.cwd()):
       subprocess.run(["bash", "-n", str(source)], check=True)
   PY
   ```

5. Do a whitespace check of the implementation diff.

   ```bash
   git diff --check
   ```

6. Examine the generated README table and badge decisions.

7. Record acceptance results in section 12.

The runner creates these Bash artifacts:

| Artifact | Path |
| --- | --- |
| JSON counts and source hashes | coverage/bash.json |
| LCOV counts | coverage/bash.lcov |
| HTML source lines and results | coverage/bash/index.html |
| Current trace files | coverage/bash-traces |

Local regression tests supply evidence for the deliberate failure cases in section 10.
The final complete run supplies evidence for the actual application source set.
A successful command alone does not prove all acceptance criteria.

## 12. Completion evidence

The owner gave implementation approval on 2026-10-26.
Implementation and local verification completed on that date.
The source consists of the baseline commit with the file changes in section 9.
The owner gave approval for a Git commit and push on 2026-10-26.
The installed applet and Plasma session kept their previous state.

### Implementation results

The collector and README updater share source discovery, report validation, and the integer coverage gate.
Source discovery includes subdirectories.
Fixture source paths keep independent execution counts.
Validation compares exact line sets with the parser output from current source bytes.
The runner already continued after a Bash report failure, so its execution order required no change.

The README includes individual script counts and gate results.
The Bash badge uses the result for all files.
The new fixtures use controlled commands, private data, and pseudo-terminals.
The timeout regression verifies that process-group cleanup stops a background child.
The sh regression compares native and Bash results and verifies trace collection through Bash.

The source corrections are:

| Source | Correction and regression evidence |
| --- | --- |
| mirrorlist, rank_mirrors | Separate the curl assignment from local. Reset result variables for each server. MirrorTests verifies both failures |
| mirrorlist, path and completion | Use the optional fixture path. Give zero for a successful write or a fresh list. MirrorTests verifies these results |
| management, rebuildPython | Return to the menu after cancellation. The detected-rebuild test verifies confirmation and cancellation |
| management, recentlyInstalled | Use the optional log path. The recent-history test verifies package dates and status |
| utils, sync_dbs | Give zero after successful synchronization. The private-database test verifies success and native failure |
| utils, printClose and callers | Keep terminal output separate from operation status. Explicit exits preserve refusal and command failure codes |
| utils, install_devel | Use metadata.json for the tray flag. Preserve Git, archive, installer, and restart failure codes |

The new regression cases failed before these corrections.
All final regression cases passed.
The tests performed package and desktop operations through stubs.
The test fixtures changed only temporary files.

### Final coverage

| Script | Covered lines | Total command lines | Coverage | Gate |
| --- | ---: | ---: | ---: | --- |
| arguments | 23 | 23 | 100.00% | PASS |
| init | 19 | 20 | 95.00% | PASS |
| management | 319 | 348 | 91.67% | PASS |
| mirrorlist | 83 | 84 | 98.81% | PASS |
| terminal | 31 | 31 | 100.00% | PASS |
| upgrade | 150 | 158 | 94.94% | PASS |
| utils | 304 | 335 | 90.75% | PASS |
| vars | 38 | 38 | 100.00% | PASS |
| widgets | 220 | 257 | 85.60% | PASS |
| Total | 1187 | 1294 | 91.73% | PASS |

All nine scripts exceed the acceptance minimum of 80 percent.
All nine also exceed the development target of approximately 85 percent.

The final complete run passed 228 Python tests and 66 JavaScript tests.
Python combined statement and branch coverage was 85.52 percent.
JavaScript coverage was 95.33 percent for lines, 76.00 percent for branches, and 91.88 percent for functions.
The Python and JavaScript minimums did not change.

The sandbox caused EPERM in Node.js subprocess tests during the first baseline run.
The final complete run used an execution environment without that restriction.
The command used the same repository files and existing development dependencies.

### Acceptance results

| Criteria | Result | Evidence |
| --- | --- | --- |
| AT-01, AT-24 | PASS | The final report includes all nine current scripts with valid hashes, exact line sets, and passing integer gates |
| AT-02, AT-03 | PASS | The integer-boundary test accepts 80/100 and rejects 19999/25000 despite its rounded display |
| AT-04 | PASS | The high-total README test rejects a 99.01 percent total with one failed file. The runner rejects a failed Bash gate |
| AT-05, AT-06, AT-25 | PASS | Collector tests include unexecuted scripts and distinct nested paths with identical names and source text |
| AT-07, AT-08, AT-09 | PASS | Collector tests keep all three low-coverage reports. The runner test retains failure status and performs JavaScript tests |
| AT-10, AT-11 | PASS | README tests verify sorted individual rows and badge colors. The final README shows 9/9 files at PASS |
| AT-12, AT-13, AT-15, AT-32 | PASS | Report tests reject invalid sources, counts, and missing parsers. Preparation and interruption retain correct status and independent results |
| AT-14 | PASS | A report test keeps FAILED for a failed test run with passing coverage |
| AT-16, AT-17 | PASS | README tests preserve outside text, line endings, permissions, and the file when output is identical |
| AT-18 | PASS | Collector tests reject an empty source set and a source with no command lines |
| AT-19 | PASS | A collector test counts unchanged fixture copies and rejects execution from a modified copy |
| AT-20, AT-21 | PASS | Mirror tests keep a successful server after a failed server and reject a partial response with exit code 18 |
| AT-22 | PASS | Fixtures reject unexpected native commands. The timeout test verifies that the background child stops |
| AT-23 | PASS | The final complete run passes the Python and JavaScript suites and their unchanged coverage gates |
| AT-26, AT-27, AT-28 | PASS | Collector and README tests reject omitted, added, and replaced line keys with consistent totals and unchanged hashes |
| AT-29, AT-30, AT-31 | PASS | The sh test verifies Bash trace hits, native compatibility, an incompatible fixture result, and zero hits for untraced execution |
| AT-33 | PASS | Utility regressions verify refusal code 1, missing-tool code 127, and native failure codes 42, 43, 53, 54, 55, and 56 |
| AT-34 | PASS | CapturedProcessCleanupTests verifies children stop after normal completion and timeouts in both captured-output helpers |
| AT-35 | PASS | Runner tests remove an old HTML report before preparation failure and collector failure |

The final verification includes the complete coverage command and shell syntax checks for all nine scripts.
The Git whitespace check passed.
The independent source and integer assertions passed.
No acceptance criterion remains open.
The full STE word check remains open.

### Document revision 1.1

Revision 1.1 adds instructions for a new session without conversation history.
It gives the measurement contract, fixture settings, and exact README markers.
It also clarifies implementation approval and the use of modified source copies.
Implementation approval was not available at revision 1.1.

### Document revision 1.2

Revision 1.2 adds exact line-set validation against executable_lines().
It specifies Bash execution for measurement of sh scripts and separate native compatibility cases.
AT-26 through AT-32 give the additional acceptance criteria.
The independent verification command uses the development parser and current source bytes.
Implementation approval was not available at revision 1.2.

### Document revision 1.3

Revision 1.3 records implementation approval and local verification.
It records the initial implementation evidence for AT-01 through AT-32.
The implementation is complete.
The full STE word check remains open.

### Document revision 1.4

Revision 1.4 corrects three defects from the implementation review.
AT-33 through AT-35 give the additional acceptance criteria.

The terminal-close function returns zero after its display work.
Operation callers use explicit exit codes for refusal, missing tools, native failure, and cancellation.
The installer preserves archive, package-tool, and restart failures through later output and cleanup.

The captured-output helpers use a shared process-group cleanup function with interact.
They start private sessions and stop children after normal completion or a timeout.
A timeout still raises TimeoutExpired after cleanup.
Regression cases include children that keep the output pipes open.

The runner removes the previous Bash HTML index before environment preparation.
Tests verify this cleanup after a preparation failure and a collector failure.
A valid current report remains available after a low-coverage gate failure.

The new regression cases failed before the corrections.
The final complete run passed 228 Python tests and 66 JavaScript tests.
All 35 acceptance criteria have local evidence.
The full STE word check remains open.

## 13. References

| ID | Source | Use |
| --- | --- | --- |
| S01 | [Official ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf), 2025-01-15 | Parts 1 and 2. Rules 1.1 through 1.14, section 5, section 6, and recurring word errors |
| S02 | [Official ASD-STE100 FAQ](https://asd-ste100.org/STE_faq.html) | Technical terms, active voice, and the noun form of check |
| S03 | [GNU Bash Reference Manual](https://www.gnu.org/s/bash/manual/bash.html) | The local builtin, variable scope, and command substitution |
| S04 | [GNU Bash startup rules](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files) | BASH_ENV for ordinary Bash and startup differences for the name sh |
| R01 | [Existing coverage guide](../DEVELOPMENT.md) | Baseline development environment, measurement, and report publication |
| R02 | [APT and Snap terminal header request](2026-10-26_CHANGE_REQUEST_APT_SNAP_TERMINAL_HEADERS.md) | Existing shell fixtures and upgrade regression evidence |
