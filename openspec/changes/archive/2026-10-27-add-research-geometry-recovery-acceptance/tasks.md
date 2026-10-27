# Tasks

## Proposal

- [x] Read repository and OpenSpec rules, and inspect relevant current specifications.
- [x] Review the uncommitted prototype and record gaps G1-G11 in `design.md`.
- [x] Draft proposal, design, and delta specifications.
- [x] Validate the change: the OpenSpec CLI is unavailable in this environment, so a manual structural review was performed (every requirement has SHALL/MUST and WHEN/THEN scenarios; the MODIFIED header matches the current spec; no absolute paths).
- [x] Obtain human approval of the original one-event proposal before runtime implementation (2026-10-27; this does not approve the subsequent revised proposal).
- [x] Obtain approval and add the prospective retained-staging invocation-evidence contract (2026-10-27).
- [x] Draft consistent qualifications to exclusive terminal-success restrictions in runtime progress, compatible summary versions, retry downstream authority, and GUI progress as part of the revised proposal.
- [x] Revise the proposal at the human's request: zero lost and unrecovered counts, no recovering-count or ratio acceptance cap, and complete recorded region-pair counts.
- [x] Include confirmed GUI acceptance after the human's conditional Yes: verification and receipt creation must not recalculate PHITS.
- [x] Obtain human approval of the complete revised proposal before runtime implementation (2026-10-27).

## Implementation after approval

- [x] Preserve future geometry-failed staging on every supported platform and record its relative path, producing execution ID, segment identity, and input/output SHA-256 bindings in the formal execution record.
- [x] Reject historical records lacking the required staging binding without retrofitting them when implementing acceptance validation.
- [x] Implement eligibility with re-parsed `phits.out`, zero lost and unrecovered counts, an uncapped positive recovering total, complete region-pair counts that sum to that total, and final-batch proof. Preserve bounded parsing and every other gate; zero recoveries follow the ordinary path.
- [x] Implement explicit staging selection and failed-invocation binding without scanning.
- [x] Implement read-only preview with a canonical plan digest.
- [x] Bind the revised acceptance-policy identity, recovering total and every region-pair count into the plan and receipt; do not substitute an `nlost` parameter, history ratio, or old one-event policy for full eligibility validation.
- [x] Implement confirmation-bound apply: acknowledgement, lease, full pre-validation, new-only publication, receipt last.
- [x] Use a new receipt schema version with workspace-relative paths only; reject prototype receipts.
- [x] Centralize the downstream branch in `validate_segment_execution_for_downstream`; restore every removed ordinary validation (G1, G2).
- [x] Revalidate the receipt at Sumtally Generate/Run and RTDOSE Prepare/Run; propagate `research_exception`.
- [x] Refuse ordinary execution, selective retry, retry planning, and GUI preflight before mutation when a receipt exists, including malformed receipts.
- [x] Add GUI research-exception state, research-only banner, and explicit re-read action.
- [x] Add confirmed GUI acceptance using the same preview/apply backend as the CLI: explicit staging selection, complete evidence display, non-empty reason, affirmative confirmation, and current plan digest. The acceptance action must not launch any external tool or recalculate PHITS; Sumtally and RTDOSE remain separately invoked and gated.
- [x] Add `--verify-only` independent verification.
- [x] Update troubleshooting documentation: replace and prohibit manual evidence edits.

## Verification and closeout

- [x] Cover prospective capture using fake runners, cross-platform retention, missing or mismatched invocation bindings, and failure to capture or persist evidence safely.
- [x] Cover eligible flow through RTDOSE Prepare with fake runners.
- [x] Cover byte-immutability of summary, preflight, manifest, `phits.out`, and staging.
- [x] Cover each rejected precondition (nonzero lost or unrecovered counts, invalid totals or pair distributions, multiple failed segments, return code, incomplete batches, parse errors, other failure reasons).
- [x] Cover recovering counts above one, multiple region pairs, and larger supported positive totals without a count or history-ratio cap; distinguish eligibility from explicit operator acceptance.
- [x] Cover GUI reason entry, confirmation, decline, closure, stale evidence, workspace changes, shared-backend revalidation, and absence of any PHITS recalculation or external process during acceptance.
- [x] Cover single-byte tampering of every bound artifact, plus missing, empty, unsupported, or absolute-path receipts.
- [x] Cover staging absence, mismatched invocation, links/reparse points, and destination conflicts without partial publication.
- [x] Cover relocation revalidation and retry refusal.
- [x] Cover regression: without a receipt, ordinary downstream fail-closed behavior is unchanged.
- [x] Run `python -m compileall src` (passed during specification-addition verification; rerun after implementation).
- [x] Pass `python -m pytest -q -p no:cacheprovider` on the final implementation: 1648 passed, 16 skipped, one existing warning (262.10 seconds).
- [x] Run `python tools/verify_public_tree.py` (459 tracked files passed during specification-addition verification; rerun after implementation).
- [x] Run strict OpenSpec validation of the revised change (passed; repeat after implementation).
- [x] Run `git diff --check`, `git diff --stat`, and `git status --short` (passed/inspected during specification-addition verification; rerun after implementation).
- [x] Promote accepted deltas, archive the change, and validate the resulting tree (2026-10-27; baseline findings explicitly recorded below).

Real PHITS, real external workspaces, and DICOM attribute changes are not
authorized by this change.

## Resumed verification: 2026-10-27

- The human approved this proposal and requested installation of the OpenSpec
  CLI. Version 1.15.0 was installed in the ignored local virtual environment;
  no OpenSpec initialization or generated-rule update was run.
- `openspec validate add-research-geometry-recovery-acceptance --strict`
  returned exit code 1: seven requirement-length warnings (over 500 characters).
- Baseline `openspec validate --specs --strict --json` found 22 current
  specifications: three passed and 19 failed, with 96 requirement-length
  warnings. These baseline specifications have not been modified.
- `python tools/verify_public_tree.py` passed (459 tracked files), and
  `git diff --check` passed with line-ending notices only.
- Runtime implementation has not started. Inspection found no authoritative
  staging-directory-to-invocation identity in the current segment result
  record. Windows retains staging through its safe cleanup guard; other
  platforms remove it. Content equality alone cannot prove the invocation
  binding required by G4. This prompted the subsequent human decision below.
- Compilation, pytest, specification promotion, and archiving have not been
  performed at that checkpoint. No external workspace, real output, or
  unrelated untracked file was inspected or modified.

## Approved staging-evidence addition: 2026-10-27

- The human approved adding the future-run staging-retention and formal
  invocation-binding contract. It is now recorded in the proposal, design,
  runtime delta, acceptance delta, implementation tasks, and verification
  checklist. The prior binding decision is resolved.
- This approval does not authorize changing any historical execution record,
  accepting a prototype receipt, running real external tools, changing DICOM
  attributes, or widening the geometry threshold.
- Runtime implementation remains incomplete, so the change stays active and
  its deltas have not been promoted into current specifications.
- The seven proposal requirement-length warnings were resolved by retaining
  the complete condition text in explicit contract scenarios, with concise
  normative requirement summaries. No eligibility condition was removed.
- `openspec validate add-research-geometry-recovery-acceptance --strict`
  now passes with CLI 1.15.0. A structural review also checked SHALL/MUST,
  WHEN/THEN scenarios, and absence of personal absolute paths in all change
  documents. The delta contains nine acceptance, two runtime, one retry, and
  two GUI requirements.
- `openspec validate --specs --strict --json` still reports the unchanged
  baseline of 19 failing specifications and 96 requirement-length warnings.
- `python -m compileall src` and `python tools/verify_public_tree.py` passed.
  The system Python lacks pytest. The existing virtual environment has pytest
  9.1.1; sandboxed runs encountered temporary-directory WinError 5, including
  with a repository-local basetemp, and were stopped. Normal-permission
  synthetic testing is recorded separately below.
- Focused normal-permission `tests/test_prepare_rtdose.py -x` failed on its
  first test: the inherited prototype unconditionally reads
  `analysis/segment_execution_summary.json`, which the ordinary legacy
  Sumtally fixture does not contain. No runtime or fixture correction was made
  during this documentation addition.
- `tests/test_phits_geometry_diagnostics.py` passed: 20 tests. A full
  normal-permission pytest run was started with a fresh test-controlled
  temporary directory inside the ignored virtual environment.
- Implementation is stopped under the repository conflict rule pending the
  narrow specification consistency decision documented in `design.md`.
- The first full normal-permission run finished with 1406 passed, 159 failed,
  and 15 skipped. Its repository-local temporary location caused synthetic
  workspaces to be rejected by the intentional public-tree protection, so
  those failures are not attributed to runtime regressions. A second run uses
  a fresh OS temporary directory outside the public tree, without changing
  the protection or fixtures. The first run also exposed the independently
  reproduced inherited-prototype RTDOSE failure recorded above.

## Requested recovering-policy and GUI revision: 2026-10-27

- The human requested a proposal revision retaining `lost_particles == 0`
  and `unrecovered_errors == 0` while removing the one-event recovering cap.
  The revised policy records every positive recovering total and all region
  pairs without a count, pair-count, or history-ratio acceptance cap. Pair
  counts must sum to the total; unsupported parsing and ambiguous evidence
  remain ineligible. Exactly one failed active segment and all other
  completion, integrity, and operator-acknowledgement conditions remain.
- The human separately gave a conditional Yes to GUI acceptance: the saved
  calculation must not be recalculated. The proposed GUI action now displays
  all evidence, requests a reason and explicit confirmation, and shares the
  CLI preview/apply backend. Verification reads saved files and checks hashes;
  acceptance does not launch PHITS or any other external tool. Later Sumtally
  and RTDOSE runs retain their separate explicit actions and current gates.
- The earlier CLI-only and one-event limitations are superseded in this
  proposed revision. Approval of the complete revised proposal is still
  required before runtime implementation. Original approvals remain recorded
  as historical decisions, not as approval of unseen revised specifications.
- Consistency qualifications are now drafted in the runtime, retry, and GUI
  delta specifications. The earlier standalone consistency decision is
  incorporated into approval of this complete revised proposal; no canonical
  specification has been changed.
- The full run started before the interruption completed using the existing
  virtual-environment Python with `-m pytest -q -p no:cacheprovider
  --basetemp <fresh OS temporary directory> --tb=short`: 67 failed, 1497
  passed, 16 skipped, one warning. There are 66 failures in
  `tests/test_prepare_rtdose.py`, including the independently reproduced
  inherited-prototype missing-summary regression. One structure-relative-error
  publication test raises FileNotFoundError on Windows; its cause has not
  been established. The suite is not represented as passing and was not
  rerun for this proposal-only revision with unchanged runtime code.
- Strict validation of the revised change passes with no issues. The existing
  current-specification baseline remains 19 failing specifications with 96
  requirement-length warnings; that unrelated tree has not been rewritten.
- Runtime code, ordinary geometry-clean success rules, DICOM attributes,
  protected data, external workspaces, and unrelated untracked files were not
  changed. This active change is not promoted or archived while revised
  approval, implementation, and required validation remain incomplete.
- Changed documents in this revision: `proposal.md`, `design.md`, `tasks.md`,
  `specs/research-geometry-recovery-acceptance/spec.md`,
  `specs/phits-segment-runtime/spec.md`, `specs/phits-segment-retry/spec.md`,
  and `specs/guided-gui-workflow/spec.md`, all under this active change.
- Post-revision validation: `openspec validate
  add-research-geometry-recovery-acceptance --strict` passed with CLI 1.15.0
  and zero issues; `python -m compileall src` passed;
  `python tools/verify_public_tree.py` passed (459 tracked files);
  `git diff --check` passed with existing line-ending notices only;
  `git diff --stat` and `git status --short` were inspected. The inherited
  tracked prototype diff remains four files, 35 insertions and 20 deletions;
  this active proposal directory remains untracked. The existing status
  warning for an inaccessible old test-temp directory was not investigated
  or altered.
- A structural review checked all 20 proposed requirements (nine acceptance,
  four runtime, two retry, five GUI), including exact current requirement
  headers for MODIFIED deltas. All seven documents passed UTF-8, whitespace,
  and absolute-path checks. No new tests were added for this documentation
  revision, and no external-workspace acceptance has been attempted.

## Approved implementation started: 2026-10-27

- The human approved implementing the complete revised proposal with synthetic
  data and fake runners only. This resolves revised-proposal approval; it does
  not authorize real tools, real workspaces, DICOM changes, or historical
  evidence rewrites.
- `run_segments.py` and `segment_retry.py` now preserve geometry-failed staging
  independently of platform cleanup behavior. A versioned `retained_staging`
  field binds the directory, segment, producing execution ID, pre-execution
  input hashes, retained file hashes and sizes, and required-output presence.
  A changed staged input cannot produce a valid binding. Failure status and
  the existing prohibition on tally publication remain unchanged.
- The same modules now refuse PHITS execution and retry when any artifact
  exists at the fixed research-receipt path, before preflight, staging,
  execution-summary mutation, or child launch. The check repeats under
  execution ownership to close the check/acquire interval.
- Added `tests/test_research_geometry_recovery_evidence.py`: 11 synthetic
  tests for retained invocation identity and byte evidence, missing-output
  recording, staged-input mismatch, and mutation-free refusal of ordinary,
  retry, preflight, and planning paths for valid-JSON and malformed receipts.
- Initial focused validation found 30 failures caused by checking a receipt
  below a not-yet-existing `analysis` directory (84 passed, one skipped).
  Inner-loop correction attempt 1 preserves the fresh-workspace path without
  creating that directory. Rerunning the exact four-file focused suite passed:
  114 passed, one skipped. No guard or test assertion was weakened.
- Focused command: virtual-environment Python with `-m pytest -q
  -p no:cacheprovider --basetemp <fresh short OS temporary directory>
  --tb=short tests/test_research_geometry_recovery_evidence.py
  tests/test_run_segments.py tests/test_segment_retry.py
  tests/test_phits_geometry_diagnostics.py`.
- `python -m compileall src`, `python tools/verify_public_tree.py` (459 tracked
  files), strict OpenSpec change validation, and `git diff --check` passed.
  A full synthetic pytest run has been started for the new runtime diff.
- Acceptance and GUI continuation are not complete. The existing geometry
  parser and reviewed fixtures cover the three aggregate counters, but not
  the region-pair distribution needed by the approved receipt contract.
  Public PHITS documentation was consulted for diagnostic meanings; it did
  not provide a confirmed parser fixture for this task. Reference:
  https://phits.jaea.go.jp/manual/PHITS-en/chapters/input-output.html#summary-output-file-phits-out
- The repository rule against guessing a specification, test fixture, or
  reference blocks inventing a PHITS region-pair syntax and testing only that
  invention. A human-confirmed sample with the supported output format and
  entirely fictional values is requested at
  `tests/fixtures/phits_geometry_recovery_summary.synthetic.txt`, including
  the region-pair and final-batch fields. No real PHITS output was opened.
- Pending that reference, the receipt validator, preview/apply protocol,
  downstream audit propagation, GUI confirmation, documentation replacement,
  and remaining acceptance tests stay incomplete. The inherited prototype
  has not been represented as a working implementation. No specification
  promotion, archive, commit, or pull request has been made.


## Implementation and synthetic verification resumed: 2026-10-27

This section supersedes earlier waiting-for-format and prototype-only status.
The human supplied an example with a `region1 region2 count` table and final
`bat[...] ncas = ...` line and authorized continuing from that example. The
tracked fixture uses newly invented numeric values. Its layout has not been
independently checked against an original nonzero PHITS output. Unknown or
ambiguous layouts fail closed. No original records are edited or retrofitted.

The human separately authorized reading named backed-up external workspaces.
One was inspected read-only under the existing execution lease and output
guard; its available records had zero recovering counts. Those observations
were insufficient as a nonzero format reference. No external result, path,
identifier, or copied output was added to this repository. The later supplied
example, not real output contents, informed the synthetic parser fixture.
No real tool was run, no external file was changed, and the ongoing GUI/PHITS
calculation was not controlled or modified.

Implemented:

- Complete positive recovering distribution and final-batch parsing, zero lost
  and unrecovered counts, all ordinary companion-success and geometry gates.
- Prospective invocation-bound staging verification with no candidate discovery,
  read-only preview digest, acknowledgement and reason, lease, new-only exact
  derived output publication, receipt last, portable v2 receipt and verify-only.
- Shared downstream validation and matching research audit markers in all four
  downstream summaries; ordinary validation order and messages are preserved.
- Mutation-free PHITS execution/retry refusal for any fixed-path receipt.
- GUI selection, full review, reason, cancel-safe explicit confirmation,
  asynchronous evidence checks, generation-bound callbacks, research notice,
  persistent failed PHITS presentation, and explicit re-read.
- Updated user guide and English/Japanese manual troubleshooting. No evidence
  editing, hash rewriting, or overwrite-checkbox acceptance is supported.

Validation history (do not erase earlier failures):

- The full suite after the earlier ordinary-path corrections passed with
  1583 passed, 15 skipped, one existing duplicate-ZIP-member warning.
- New parser/receipt focused tests: 67 passed. The first broader run then had
  2 failures and 236 passes because receipt serialization used Windows CRLF;
  correction attempt 1 explicitly accepts complete canonical LF or CRLF
  serialization, rejecting mixed or otherwise modified serialization. The
  same broader suite then passed: 238 passed.
- GUI/model focused validation: 172 passed, one skipped. A prospective synthetic
  fake-runner flow passed all four downstream stages through RTDOSE execution,
  with identical receipt markers and byte-identical original evidence.
- A new lock-contention test initially tried to read the Windows lock file
  while another thread owned it (46 passed, one failed). Correction attempt 1
  moved the initial snapshot before lock acquisition. The same suite passed:
  47 passed. The product lock and all assertions remain enforced.
- Expanded regression validation found 7 failures and 505 passes, two skips:
  an early new ordinary Sumtally gate displaced existing MU/output/hash error
  messages. Correction attempt 1 restored existing validation order and keeps
  the shared authority gate before staging or launch. The same suite with
  added tampering tests passed: 521 passed, three skipped.
- The next full suite found 15 failures, 1628 passes, 16 skips and the existing
  ZIP warning. All failures were isolated nested-callback tests missing the
  newly required workspace closure variable. Their synthetic closure now
  supplies that variable and receipt/cache state; no expected result changed.
- Added hidden-Tk integration in its own subprocess with isolated defaults,
  fake inputs and a Python audit hook forbidding external execution. It checks
  event-loop responsiveness during a blocked evidence read, acceptance, No,
  closed reason entry, and empty reason. Initial validation: 42 passed and one
  failure caused by the test reading the Windows lock file. Correction 1
  excludes the mutable lock from immutable-evidence assertions. Its next run
  reached independent verification while a GUI readiness worker still held
  the lease (42 passed, one failure). Correction 2 joins the tracked workers
  before independent verification; results are recorded below.

The final full suite, OpenSpec promotion/archive, and final checks are pending
at this checkpoint. No merge, release, DICOM attribute change, physics change,
or re-acceptance of a historical external workspace is included.


## Final integration verification in progress: 2026-10-27

- The GUI callback fixture correction passed all original expected results.
  The hidden-Tk lock synchronization correction passed on its second bounded
  correction: the identical two-file suite finished with 43 passed.
- The following full suite passed with 1647 passed, 16 skipped and one existing
  duplicate-ZIP-member warning. It includes all four affirmative downstream
  stages and receipt-tampering rejection at each of the four stage boundaries.
- Final review reproduced one receipt-contract defect: an absolute path in the
  tool-version field could pass if its non-secret content checksum was also
  recomputed. A focused synthetic regression failed before the fix. Review
  correction round 1 restricts this field to version-number syntax. The same
  regression passed (one test); a full suite on the final source is running.
  This is a schema check, not a claim that an unsigned receipt is unforgeable.
- Compilation, standard indexed-tree audit, strict active-change validation,
  and whitespace checks pass. The scoped working-tree snapshot audit included
  all new files at its checkpoint: 25 scoped files, 472 combined entries,
  zero issues. No unrelated untracked path was read for that audit.
- The existing canonical strict baseline is unchanged before promotion:
  22 specifications, three passed and 19 failed due to the previously recorded
  requirement-length warnings. These are explicitly recorded baseline findings,
  not represented as a new all-green canonical validation result.


## Final source validation: 2026-10-27

- Final full synthetic suite: 1648 passed, 16 skipped, one existing
  duplicate-ZIP-member warning in 262.10 seconds. No real tool was launched.
- `python -m compileall src`, standard public-tree audit (459 indexed files),
  strict active-change validation, and `git diff --check` passed.
- CLI module `--help` passed and exposes preview, apply, and verify-only.
- Before this change is archived, archived-task validation already has one
  unrelated failure: `2026-08-07-add-windows-offline-installer` has 24 of 25
  tasks checked. The other 39 existing archives pass. That historical archive
  is not modified or falsely marked complete.
- Acceptance criteria and runtime checks are complete. Only the required
  specification promotion, archive operation and resulting-tree verification
  remain at this checkpoint.


## Promotion, archive and stopping outcome: 2026-10-27

- OpenSpec CLI 1.15.0 archived the change into
  `2026-10-27-add-research-geometry-recovery-acceptance`, updating all four
  capabilities: 14 added requirements and six modified requirements.
- The CLI-created Purpose placeholder in the new capability produced one new
  strict warning. A bounded documentation correction replaced it with the
  approved capability's concrete purpose. The identical individual strict
  validation then passed with no issues.
- Strict validation of the archived deltas through the installed OpenSpec
  Validator API passed: zero errors, warnings or information findings. The
  CLI does not accept a path-qualified archived change name, so its normal
  archive-task command is also checked independently below.
- Canonical strict validation after promotion: 23 specifications, four passed,
  19 failed, exactly the same 96 baseline requirement-length warnings. The new
  capability passes individually. No new strict finding remains in this diff.
- The completed archive checklist is validated separately from the unchanged
  historical offline-installer archive with its one pre-existing open task.
- Implementation and synthetic acceptance criteria are complete. No optional
  refactor, new follow-up work item, or additional review round is started.
  Source and tests are left reviewable on the existing feature branch;
  no commit, push, pull request, merge or release has been performed.
- Real-tool compatibility, original nonzero-output format verification, Linux
  execution of this test suite, and historical-workspace re-acceptance remain
  unverified. The Windows symlink test is skipped without link privileges;
  the existing cross-platform guards and corresponding tests remain intact.


Final post-archive checks:

- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: passed, 459 indexed files.
- Scoped current-file snapshot audit: passed, 30 changed/new files and 474
  combined entries, zero issues; UTF-8 and trailing whitespace checked.
- `git diff --check`: passed (line-ending notices only).
- `git diff --stat`: 15 tracked files, 668 insertions and 51 deletions; this
  excludes the 15 new task-scoped files. The report above also lists new files.
- `git status --short`: inspected. The unrelated configuration/screenshots and
  an existing inaccessible old test-temp warning are preserved untouched.
- Archived strict delta validation: passed with zero findings using the
  installed CLI's Validator API. The path-qualified name is unsupported by
  the CLI's single-change command.
- Canonical strict validation: 23 items, four pass, the same 19 baseline
  failures from 96 length warnings; the new capability passes individually.
- Archived-task strict validation: this change passes with zero incomplete
  tasks; globally 40 of 41 archives pass, with only the previously recorded
  historical offline-installer archive failing.
- The active change directory is absent. No runtime or test changes followed
  the final 1648-pass full suite; subsequent edits were specification/archive
  cleanup and these reports only.


## Authorized GitHub review phase: 2026-10-27

The human approved publication as a draft PR, explicitly requested the GitHub
plugin and `@codex review`, and authorized fixing verified in-scope defects
without renewed human approval until review reports no remaining defects.
This supersedes the earlier local-only stopping checkpoint and the default
six-round cap for this requested review loop. It does not authorize real-tool
execution, real-data writes, physics/DICOM changes, scope expansion or merging.
The existing branch and PR will be used throughout; unrelated local files are
excluded. Review findings and corrections will be recorded with their evidence
and validation results.
