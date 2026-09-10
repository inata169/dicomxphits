## 1. Proposal

- [x] 1.1 Inspect current progress, stop, runtime and tally boundaries.
- [x] 1.2 Define observation authority, version scope, metrics and unavailable states.
- [x] 1.3 Validate this proposal and run required public checks.
- [x] 1.4 Obtain human approval of the proposal before implementation.

## 2. Implementation after approval

- [x] 2.1 Document exact supported 3.35 grammar/version markers from official evidence; stop if insufficient.
- [x] 2.2 Add bounded read-only parsers and authored synthetic fixtures.
- [x] 2.3 Add generation-bound staged observation and atomic optional sidecar.
- [x] 2.4 Add responsive GUI availability, remaining-batch and per-cell error presentation.
- [x] 2.5 Cover stale/torn/unsafe/oversized data, reset races, excluded values and mismatched dose/error pairs.
- [x] 2.6 Verify unchanged input/output/control bytes, run outcomes, retry, stop and downstream gates.

## 3. Validation and closeout after implementation

- [x] 3.1 Run focused parser, runner, GUI, retry, stop and downstream regressions.
- [x] 3.2 Run compile, full pytest, public-tree audit, OpenSpec strict and Git diff/status checks.
- [x] 3.3 Report synthetic versus separately approved real-tool/desktop verification explicitly.
- [x] 3.4 Complete review within repository stopping rules; resolve only verified blockers.
- [x] 3.5 Promote accepted deltas, archive the completed change and validate the resulting tree.

The checklist above is the current status. The dated records below preserve
historical approval gates and failures; earlier blocked statements are not the
current state. See the final acceptance review for scope and verification limits.

Historical proposal status: human approved; implementation paused at task 2.1. Real
PHITS, distribution inspection, patient data and external workspaces have not
been used. Real-tool verification is not authorized by proposal creation.

Proposal validation (2026-09-09; repository Python 3.12 virtual environment):

- `openspec.cmd validate add-phits-live-observation --strict`: passed.
- `python -m pytest -q -p no:cacheprovider tests/test_segment_stop.py --basetemp <outside-repository-temp-directory>`: 33 passed.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>`: 1078 passed, 10 skipped.
- `python tools/verify_public_tree.py`: 307 tracked files passed.
- `openspec.cmd validate --all --strict`: 16 items passed.
- `git diff --cached --check`, `git diff --cached --stat`, and `git status --short`: reviewed; only these five proposal files changed.

No runtime or accepted-specification changes. Full tests observe the existing
implementation, not implementation of this proposal. No real PHITS or desktop
verification is claimed. Implementation remains incomplete, so the
change is deliberately active and has not been promoted or archived.

## Implementation prerequisite check (2026-09-09)

The human approved implementation. No runtime changes have been made: task 2.1
requires stopping if the exact supported grammar cannot be established.
The official 3.35 manual, section 4.9 (printed pages 44-45), describes a
T-Track example whose version caption is 3.28, rather than a complete 3.35
Windows OpenMP 3D T-Deposit dose/error pair. Section 3.2 describes the remaining
batch counter but does not provide the complete record grammar required by
this proposal. These examples do not establish the exact version/mode markers
and paired history/restart metadata needed by the proposed parser. This is an
evidence gap, not proof that PHITS 3.35 lacks the feature or uses a different
format. The current public HTML manual is version 3.37 and is not substituted.

Source: https://phits.jaea.go.jp/manual/manualE-phits335.pdf

Needed evidence: a documented complete target-format example, or separately
approved synthetic PHITS 3.35 OpenMP observations of batch output, version
identity and the matching generated 3D dose/error pair. No installed tool,
distribution, real output or external workspace was inspected. No new execution
permission is inferred. A minimal synthetic verification plan may be proposed
to the human; this note does not authorize its execution. Do not fabricate a
3.35 fixture by replacing the version string in an older example.

## Proposed evidence acquisition

The human authorized preparation of a minimal synthetic verification plan.
See [verification-plan.md](verification-plan.md) for the single-run envelope,
private-path and artifact approval gates, read-only capture, resource limits,
inconclusive outcomes and acceptance matrix. This does not authorize real PHITS
execution. At the plan-only checkpoint no input deck, collector or external
workspace had been created; the preparation-only update below supersedes that
artifact status without granting real execution permission.
Task 2.1 remains incomplete pending sufficient target-version evidence.

Plan-only validation (2026-09-09): focused `test_segment_stop.py` passed
(33 passed); full `python -m pytest -q -p no:cacheprovider --basetemp
<outside-repository-temp-directory>` passed (1078 passed / 10 skipped).
`python -m compileall src`, `python tools/verify_public_tree.py` (308 tracked
files), `openspec.cmd validate --all --strict` (16 items) and Git diff checks
passed. These results validate the unchanged public code and document structure,
not the proposed real-PHITS input, collector, output grammar or live behavior.

## Preparation-only kit

The human approved authoring the test input and collector without launching
PHITS. Added `tools/phits_observation_probe/observation-probe.inp`, `collect.py`,
and `README.md`, plus `tests/test_phits_observation_probe.py`. This is the
isolated diagnostic kit, not implementation of the production observer/parser.
The input follows the proposed water/source/27-cell/100000-history envelope;
its real PHITS acceptance is unverified. The collector defaults to check-only,
requires a separately approved private plan digest for execution, rejects
existing destinations and mismatched artifact hashes, preserves inherited
ownership and drains both streams without automatic termination or retry.
No installed PHITS, external workspace or real output was inspected or run.

Focused synthetic validation: 16 passed / 1 skipped. Related probe/stop tests
before the final two test additions: 47 passed / 1 skipped. The skipped test
requires symlink creation privilege. Temporary Python children, not PHITS,
verified capture, byte caps, stdout/stderr draining and lease exclusion; the
Windows execution-entry test substitutes a fake collector and forbids Popen.
Compilation of `src` and `tools/phits_observation_probe` passed. Final full
pytest passed (1094 passed / 11 skipped), public-tree audit passed (312 tracked
files), OpenSpec strict passed (16 items), and Git diff checks passed. The CLI
help command was also checked without accessing any installation. Task 2.1
and production implementation remain incomplete;
do not promote or archive this change based on preparation-kit tests.

## First separately approved real probe (2026-09-10)

The human separately approved installation inspection, private-plan preparation,
and one exact digest-bound synthetic PHITS launch. That launch has now occurred;
the earlier no-execution statements describe their historical checkpoints.
Raw outputs, the frozen plan, and offline assessment remain outside Git.

The probe exited naturally with code zero in about 2.19 seconds. Required files
were present, the three geometry diagnostic counts were zero, approved inputs
were unchanged, and all four final output digests matched a later read.
The owned output identified version 3.350 and stdout reported two OpenMP workers.
The final pair contained all three slices / 27 cells and matching restart fields
(`istdev`, `resc2`, `resc3`, `maxcas`, `bitrseed`). Offline numerical assessment
excluded plot-legend numbers and evaluated the actual mesh cells separately.

Live batch records and multiple distinct complete dose/error pairs were captured.
However, **no pair met the required two consecutive stable in-run captures**;
the workload updated too quickly. One error capture was incomplete and unstable.
A later pair had individually stable file reads but disagreeing history/restart
metadata. Final matching files do not repair the missing live confirmation.
These observations reinforce the approved torn/mismatched-data rejection rules.

Task 2.1 therefore remains incomplete. No production parser, observer or GUI
implementation is authorized past this evidence gate, and the change remains
active. The capture used about 319 KiB with no capture disablement. Its read
overhead was not independently timed; total observed duration cannot establish
performance equivalence to an unobserved calculation. Complete manual/grammar
cross-check and real desktop validation remain outstanding.

No additional PHITS launch or history increase was performed. A proposed next
probe would use a separately approved larger diagnostic batch workload and fresh
destinations, preserving the first run. Preparation and launch require separate
decisions. The provisional implementation/validation estimate remains 4-8 hours
**after** the evidence gate is satisfied; another probe and its assessment must
be added, and same-day completion is not assured by this short transport time.

Post-assessment validation (repository Python 3.12 environment): focused
`python -m pytest -q -p no:cacheprovider tests/test_phits_observation_probe.py
--basetemp <fresh-private-test-directory>` passed (16 passed / 1 skipped).
`python -m compileall src` passed; full `python -m pytest -q -p no:cacheprovider
--basetemp <fresh-private-test-directory>` passed (1094 passed / 11 skipped,
192.64 seconds). `python tools/verify_public_tree.py` passed (313 tracked files);
`openspec.cmd validate --all --strict` passed (16 items); Git diff checks passed.
Only this task record changed in the repository. These synthetic/fake-runner
checks do not satisfy the unmet real live-pair acceptance condition.

## Revised probe preparation (2026-09-10)

The human approved preparation, not execution, of a revised diagnostic probe
with maxcas=100000 and unchanged maxbch=10 / two threads (1000000 total histories).
Only maxcas changes in the deck; the collector and lease implementation remain
unchanged. The deck test now checks exact lines, so an accidental longer numeric
prefix cannot satisfy the approved workload assertion. Instructions and this
verification plan describe the revised envelope. A new private plan binds its
actual checked-out deck bytes and fresh run/evidence destinations. The previous
private plan, its copied original input and all first-run evidence are preserved.
No second PHITS launch has occurred; task 2.1 remains incomplete.

Revised preparation validation: check-only passed against the new private plan;
focused probe pytest passed (16 passed / 1 skipped); full pytest passed (1094
passed / 11 skipped, 186.97 seconds). Both used Python 3.12, `-q -p
no:cacheprovider` and fresh private `--basetemp` directories. Compilation
(`python -m compileall src`), public-tree audit (313 tracked files), OpenSpec
`validate --all --strict` (16 items) and Git diff/status checks passed.
The two original private plan/input hashes were rechecked unchanged. Production
runtime code and accepted public specifications remain unchanged; no promotion,
archive, commit, push or PR transition was performed during this preparation.

## Second separately approved real probe (2026-09-10)

The revised exact launch was separately approved and executed once. It naturally
exited zero in about 15.28 seconds with geometry-clean diagnostics, unchanged
inputs and later matching final output digests. Version 3.350 and two OpenMP
workers were identified from owned output. Nine different live generations each
had two stable consecutive matching complete 27-cell/three-slice pairs; the
independent offline assessment checked shared input echoes and all restart fields.
This satisfies the missing live evidence condition. See supported-format.md for
the grammar and official-manual cross-check. Private evidence remains outside Git.
Task 2.1 is complete; the earlier blocked statements describe prior checkpoints.
Production implementation and its tests, saved-real-output compatibility checks
and GUI verification remain required before closeout. No additional real launch
is authorized. The provisional remaining implementation/validation estimate is
4-8 hours, excluding approval waits and further real/desktop verification.

## Synthetic desktop observation check (2026-09-10)

Production parser, observer, process-stream adapter and GUI presentation are
implemented in the current diff. Saved private real snapshots were checked
without launching PHITS: no unexplained parser mismatches remained, and the
unstable first-probe snapshot was rejected. Prior implementation validation
passed 29 observation tests and the full suite (1123 passed / 11 skipped).

The human separately approved GUI verification without PHITS. The opt-in
`tests/test_phits_observation_tk.py` builds the actual Tk application at its
1120x720 minimum size with authored sidecar data. It forbids subprocess launch,
stage execution and settings writes, and injects the independently tested
summary-ownership selection boundary. It checks visible StringVar-bound labels,
non-overlap with execution controls, remaining-count updates, provisional/stale
states, foreign-run and workspace resets, success/stopped/failed cleanup and Tk
event processing. It is not an end-to-end PHITS or ownership-validation test.

Initial test failure: the synthetic summary injection omitted the separate
run-ID validation boundary. One test-only correction supplied that boundary;
the same focused test then passed. No production code was changed for this
test. A second run retaining both display states for desktop inspection also
passed (61.35 seconds). Computer Use screenshot capture failed with
`foreground window did not report a process id`; refreshed window selection
found the already-completed test closed. Pixel-level visual inspection is
therefore not claimed. Automated real-Tk widget/event checks did pass.

Run this opt-in test with `DICOMXPHITS_TEST_TK=1`; optional
`DICOMXPHITS_GUI_REVIEW=1` retains each display state for 30 seconds. Ordinary
headless CI skips it. No real PHITS launch, output reuse for downstream work,
private-artifact cleanup, push or PR transition occurred. Real-PHITS desktop
responsiveness remains unverified and requires separate execution approval;
the change remains active pending final acceptance review and closeout.

Post-GUI validation (repository Python 3.12, `DICOMXPHITS_TEST_TK=1`, fresh
private `--basetemp` per pytest command):

- `python -m pytest -q -p no:cacheprovider tests/test_phits_observation_tk.py
  tests/test_phits_live_observation.py tests/test_gui.py
  tests/test_segment_retry.py tests/test_segment_stop.py`: 216 passed / 1 skipped.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider`: 1124 passed / 11 skipped,
  167.58 seconds; includes the real-Tk synthetic test, not a PHITS launch.
- `python tools/verify_public_tree.py`: 319 tracked files passed.
- `openspec.cmd validate --all --strict`: 16 items passed.
- `git diff --check`, `git diff --stat`, `git status --short`: reviewed.

This GUI-verification increment adds only the Tk test and this record. Existing
uncommitted implementation changes are preserved. Physics, DICOM semantics and
accepted public specifications were not changed in this increment.

## Private live-GUI diagnostic preparation (2026-09-10)

The human approved private-plan preparation only. A new private diagnostic
script and plan bind the unchanged second-probe workload, exact executable,
input/library bytes, script and current production Python module digests to
fresh absent run/evidence destinations. The default is check-only; execution
requires the exact separately approved outer plan digest. No PHITS was launched
and neither planned real-run destination was created during preparation.

The proposed test uses a dedicated Tk diagnostic window with the production
Observer, Presentation, inherited lease and observed subprocess adapter. It is
not the full GUI workflow: its private in-memory observation identity is not a
valid segment execution summary and cannot authorize any downstream operation.
It measures GUI callback gaps and records provisional/stale/terminal displays
alongside private output evidence. Production sampling remains at most 1 Hz;
the earlier diagnostic 100-ms raw-file capture is not repeated during transport.
Missing twice-confirmed live samples remain inconclusive, with no automatic
retry or workload increase. The existing production stdout/stderr result
accumulation is unchanged; this is not a stream-memory stress test.

Private focused preparation tests passed (2 tests, 8.95 seconds): the child was
restricted to Python, exercising production observation through the Tk event
loop and terminal clear; an occupied target was rejected without launch. The
real frozen plan passed check-only. These are not real PHITS validation results.
The launch, its resulting diagnostics and real-desktop acceptance remain
subject to a new human decision. No runtime or accepted-specification changes
were made for this preparation; private artifacts remain outside Git.

Preparation closeout checks: private focused pytest used `-q -p no:cacheprovider`
and a fresh private `--basetemp` (2 passed); `python -m compileall src` passed;
full `python -m pytest -q -p no:cacheprovider --basetemp <fresh-private-directory>`
with `DICOMXPHITS_TEST_TK=1` passed (1124 passed / 11 skipped, 183.60 seconds).
`python tools/verify_public_tree.py` passed (319 files), `openspec.cmd validate
--all --strict` passed (16 items), and Git diff/status checks passed. The exact
frozen-plan check-only was repeated successfully with its expected digest.
Only this sanitized task record changed in the repository during preparation.
No archive, commit, push or PR transition was performed.

## Separately approved live diagnostic execution (2026-09-10)

After successful frozen-plan revalidation, the human-approved GUI diagnostic
launched PHITS exactly once. The unchanged second-probe input naturally exited
zero in about 13.765 seconds. All three geometry diagnostic counters were zero;
actual 3.350/two-worker OpenMP identity was established. Input, executable and
frozen implementation digests remained unchanged, and all four final output
digests matched a later offline read. Capture remained enabled and private
evidence occupied about 81 KiB. Independent final 27-cell statistics agreed
with the production parser; all cells were evaluable.

The one-Hz production observer emitted 14 records and accepted three distinct
provisional generations (remaining batches 8, 4 and 1). The Tk presentation
displayed two of them (8 and 4); the last accepted generation was not displayed
before retirement. This is consistent with bounded sampling and terminal clear,
not evidence of a completed batch. The GUI recorded provisional-to-stale and
stale-to-provisional transitions, 128 callbacks, a maximum callback gap of
0.125 seconds (within the private 0.5-second target), and terminal clear.
The terminal diagnostic window was captured successfully with Computer Use,
visually checked, and closed normally only after child completion. The harness
then exited zero and persisted its GUI report. No signals or retries occurred.

The approved dedicated-diagnostic acceptance conditions are satisfied. This is
real PHITS plus production observation modules in a dedicated Tk window, not a
real end-to-end launch through the complete gui.py workflow. Intermediate raw
pairs were not archived by this diagnostic; earlier probes supply raw format
evidence. It does not establish clinical validity, performance equivalence,
every intermediate counter, or other runtime/output variants. No downstream
execution summary was generated and no output was handed to Sumtally.

Offline assessment code/report and all real outputs remain private. This
increment changes only this task record in Git, not runtime code, physics,
DICOM semantics or accepted specifications. The active change still awaits
final implementation/acceptance review and required promotion/archive cleanup;
this diagnostic alone is not a declaration that all closeout tasks are complete.

## Final acceptance review (2026-09-10)

Reviewed the approved deltas against the parser, filesystem reader, lifecycle,
stdout adapter, owner-thread publication, GUI binding and authored tests.
No additional verified merge-blocking defect was found. The evidence gate is
met by the two raw-format probes and independent manual/grammar cross-check;
the separately approved third diagnostic establishes actual production-observer
display and Tk responsiveness for the tested variant. The actual GUI widget
wiring, stale/reset behavior and event loop have synthetic real-Tk coverage;
runner stop/retry/downstream contracts have the earlier focused integration
coverage. This combination satisfies the approved stage 4a acceptance scope.
The full real end-to-end GUI workflow, other PHITS variants, clinical validity
and performance equivalence remain unclaimed; they are not substituted for the
checks listed above or represented as completed tests.

No runtime changes were made after the frozen diagnostic implementation.
Closeout consists only of records, reference-link maintenance and promotion of
the already approved deltas. Do not deepen the implementation or start follow-up
work after the required final checks and archive validation pass. Push, Ready,
merge and branch deletion remain separate human decisions.

Final pre-archive validation: `python -m pytest -q -p no:cacheprovider
tests/test_phits_live_observation.py tests/test_phits_observation_tk.py
tests/test_phits_observation_probe.py --basetemp <fresh-private-directory>` with
`DICOMXPHITS_TEST_TK=1` passed (46 passed / 1 skipped). `python -m compileall src`
passed. Full `python -m pytest -q -p no:cacheprovider --basetemp
<fresh-private-directory>` with the same Tk opt-in passed (1124 passed /
11 skipped, 218.12 seconds). Public-tree audit (319 files), OpenSpec strict
validation (16 items) and Git diff/status checks passed. These pytest results
are synthetic/fake-runner checks, separate from the real diagnostic above.

Implementation correction history retained for review: initial new-test
collection failed on a missing parenthesis and passed after one syntax fix.
Saved-output compatibility checks then exposed a six-line rather than seven-line
restart block, trailing spaces on role labels, and the missing supported legend
hc line. Three bounded corrections addressed those observed mismatches, with
the focused compatibility check repeated after each. A subsequent complete
snapshot pass exposed the full initial batch record rather than a single-line
initial record; that distinct format correction updated parser, authored test
and grammar documentation, and passed the repeated snapshot check. The final
saved-snapshot pass had no unexplained mismatches and rejected the unstable
first-probe snapshot. Later diff validation found one extra EOF blank line in
the process adapter; removal passed the same diff check. No PHITS rerun or
weakened stability/identity guard was used for these corrections.

Closeout: `openspec.cmd archive add-phits-live-observation --yes` promoted four
new observation requirements and the approved guided-GUI requirement update,
then moved this change into the dated archive. Its only incomplete-task warning
was task 3.5 (archive/validation itself), marked complete after success.
`openspec.cmd validate archive/2026-09-10-add-phits-live-observation --type change
--strict` passed; `openspec.cmd validate --all --strict` passed all 16 current
specifications. The generated Purpose placeholder was replaced with a concise
non-normative description, and live links in probe instructions and the old
handoff were updated without re-running the handoff's historical instructions.
Stage 4a implementation and approved acceptance checks are complete; verification
limitations above remain explicit. No push, Ready transition, merge, tag change,
branch deletion or private-evidence cleanup is authorized by this closeout.

Post-archive public-tree audit passed (320 tracked files). The archive command
added an extra EOF blank line to the guided-GUI specification; a single
formatting-only correction removed it and the repeated diff check passed.
Both current-spec and archive strict validation were repeated after cleanup.
No Python behavior changed after the final full pytest run.

Changed-file inventory (relative to the resumed checkout): production
`src/dicomxphits/{gui.py,run_segments.py,workspace_execution.py,
observed_process.py,phits_observation.py,phits_observation_format.py}`;
`tests/{test_phits_live_observation.py,test_phits_observation_tk.py,
test_phits_observation_probe.py}`; `tools/phits_observation_probe/{README.md,
observation-probe.inp}`; link-only updates to
`docs/development-handoff-2026-09-09-phits-observation-preparation.md`;
`openspec/specs/{guided-gui-workflow,phits-live-observation}/spec.md`;
and this seven-file archived change (proposal, design, tasks, verification plan,
supported grammar and two requirement deltas), moved from its active path.
