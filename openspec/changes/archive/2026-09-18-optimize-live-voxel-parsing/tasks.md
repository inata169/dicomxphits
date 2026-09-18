# Tasks

## Proposal stage

- [x] Read repository rules, current live-observation specification, parser
      callers and existing synthetic investigation evidence.
- [x] Confirm no active overlapping OpenSpec change.
- [x] Prepare proposal, design and scenario-based requirement delta.
- [x] Update the proposal to cover simplification of the complete observation
      attempt, as requested by the human; implementation was approved subsequently.
- [x] Validate this proposal and specification tree; record public checks.
- [x] Obtain human approval of this concrete proposal before runtime changes.

## Implementation after approval

- [x] Inspect/instrument the complete synthetic sample path for actual duplicate
      work and copies; record the validation obligations that must remain.
- [x] Simplify justified within-attempt read/hash, decode/parse, metadata and
      record construction work; document the before/after mapping without
      changing cross-attempt caching, scheduling, publication or GUI behavior.
- [x] Verify combined read/hash equivalence if changed, including prefix reads,
      replacement/truncation, unsafe paths and unchanged size/mtime with changed
      bytes; retain shared-reader consumer behavior and independent batch/error
      failures and ages. Do not remove checks at distinct freshness boundaries.
- [x] Add explicit live-only numeric dispatch while retaining shared defaults;
      use imported helpers rather than dynamic source replacement.
- [x] Implement bounded tokenization/conversion with complete grammar, cell
      count, finite/range and structural/pair checks and existing deadline.
- [x] Differential-test canonical and fallback spellings, signs/negative zero,
      D/d, underflow/overflow, NaN/Inf, malformed/truncated tokens, ASCII
      substitutions, whitespace and exact 64/65-character boundaries.
- [x] Test tokens crossing scan/chunk boundaries, extra/missing cells, invalid
      remote cells, long whitespace, expired deadlines and bounded scratch
      allocations on differently shaped authored pages.
- [x] Cover full live batch/history pairs, mesh/role/seed/source-weight/runtime
      mismatch, zero Isocenter values and all current fresh-output boundaries.
- [x] Verify shared post-completion consumers retain their scalar path and
      existing acceptance; confirm no physics/input/coordinate changes.
- [x] Verify two-successive-snapshot confirmation, unchanged timestamps,
      timeout/staleness, replacement/truncation and retired-generation reset
      using authored fixtures and mock worker/publication tests.
- [x] Measure five declared complete integrated samples using the design
      protocol; record every result, provisional median criterion and limits.
      The user explicitly approved concurrent seven-thread load in place of waiting.
- [x] Run focused tests, compileall, full pytest, public-tree audit and Git
      diff/status checks; retain all observed failures and resolutions.
- [x] Record real execution/GUI checks as not performed unless separately
      authorized; no existing user calculation GUI may be manipulated.
- [x] Promote accepted delta, archive only after acceptance/required checks,
      and validate the resulting specification tree.
- [x] Prepare the reviewable implementation diff and local PR description.
      PR publication is not performed; no merge or tag modification is authorized.

## Current stopping state

Implementation and required synthetic acceptance are complete. The user approved
measurement during reported seven-thread PHITS load. Stop optimization, promote
the delta and archive. A local PR description is prepared; no remote PR is
published by this closeout.

## Initial proposal validation on 2026-09-18

- `openspec.cmd validate optimize-live-voxel-parsing --strict --no-interactive`:
  passed. The PowerShell shim was blocked by execution policy; the installed
  command shim worked without changing policy or installing anything.
- `openspec.cmd validate --all --strict --no-interactive`: 20 passed, 0 failed.
- Four new Markdown files: UTF-8, final newline, trailing whitespace and absence
  of machine-specific absolute paths checked directly; passed.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <new-external-temp-directory> --tb=short`:
  1310 passed, 14 skipped in 312.04 seconds. Used the repository virtual
  environment and reviewed permission for a new short outside-public-tree
  temporary directory. The placeholder above omits the local absolute path.
- `python tools/verify_public_tree.py`: passed for 357 tracked files. The four
  new untracked proposal files were separately inspected as described above.
- `git diff --check` and `git diff --stat`: no tracked changes. Status contains
  this new proposal directory and the eight preserved untracked handoffs.

Only proposed requirements were added. Runtime and current accepted public
specifications are unchanged. No production optimization, new performance run,
real-data/tool verification, GUI operation, stage, commit, push or PR was made
for this proposal. Feature branch: `docs/optimize-live-voxel-parsing`.

## Broader proposal update validation on 2026-09-18

The human requested simplification of the complete observation attempt and
approved updating this proposal. All four proposal documents were revised;
runtime implementation approval remains pending.

- `openspec.cmd validate --all --strict --no-interactive`: 20 passed, 0 failed.
- UTF-8, final-newline, trailing-whitespace and local-path checks: passed for
  all four revised documents.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <new-external-temp-directory> --tb=short`:
  1310 passed, 14 skipped in 313.84 seconds, using the same virtual-environment
  and approved external temporary-directory approach as the initial checks.
- `python tools/verify_public_tree.py`: passed, 357 tracked files.
- `git diff --check`, `git diff --stat`, and `git status --short`: no tracked
  changes; the proposal directory and eight existing handoffs remain untracked.

Stop at the updated, validated proposal. No accepted specification was promoted
and no archive was created because implementation and approval are pending.
No runtime changes, performance reruns, real calculation/GUI operations,
stage, commit, push or new PR occurred.

## Approved implementation validation on 2026-09-18

The human explicitly approved the updated implementation proposal. Changes:
`src/dicomxphits/phits_observation.py`,
`src/dicomxphits/phits_observation_format.py`,
`tests/test_live_numeric_optimization.py`,
`tools/benchmark_live_observation.py`, and this change's status/design documents.

- Focused command: `python -m pytest -q -p no:cacheprovider tests/test_live_numeric_optimization.py tests/test_phits_live_observation.py tests/test_generated_live_observation.py --basetemp <new-external-temp-directory> --tb=short`.
  First run: 141 passed, 6 setup/teardown errors in 13.13 seconds. Generated
  test names embedded large strings and exceeded Windows' 32767-character
  environment-variable limit for `PYTEST_CURRENT_TEST`. A diagnostic run
  confirmed this traceback. One correction assigned short parameter IDs;
  inputs and assertions were unchanged. Rerun: 144 passed in 11.60 seconds.
- `python tools/benchmark_live_observation.py --check-only --output-directory <new-synthetic-directory>`:
  small full pair matched bitwise and integrated two-sample confirmation passed.
  This is not the five-attempt performance acceptance run.
- `python -m compileall src tools/benchmark_live_observation.py`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <new-external-temp-directory> --tb=short`:
  **1390 passed, 14 skipped in 331.44 seconds**.
- `python tools/verify_public_tree.py`: passed for 357 tracked files; new
  authored sources/proposal files separately inspected and syntax/format checked.
- `openspec.cmd validate --all --strict --no-interactive`: 20 passed, 0 failed.
- `git diff --check`: passed. `git diff --stat` and `git status --short` reviewed;
  only the intended tracked sources changed, and eight untracked handoffs remain.

Full-sample timing is deferred pending the user's confirmation of a suitable
load condition, as required by the approved design. No speed acceptance or
real-GUI display claim is made. No original simulation GUI/process or real
calculation data was inspected or manipulated. No new external tool run,
commit, push, PR, tag change, or merge occurred. The current public specification
is not promoted yet; keep this change active until integrated timing acceptance
and remaining closeout work are complete. DICOM/physics/calculation settings and
the existing guards are unchanged; runtime changes affect observation only.

## Concurrent-load acceptance and closeout on 2026-09-18

The user explicitly authorized measurement while the reported seven-thread
PHITS calculation continued, replacing the prior idle-load wait. No GUI or
process state was inspected; concurrency is user-reported, not independently
instrumented. No pytest ran concurrently with these five attempts.

Command: `python tools/benchmark_live_observation.py --output-directory <new-synthetic-directory> --load-note <user-reported-seven-thread-load>`.
Python 3.12.10, NumPy 2.5.2, authored 101-cubed pair of 10385592 and 10385390
bytes; freshly written files with OS cache not flushed. All five complete
synchronous observation attempts validated the pair within the unchanged limit.

| Attempt | Seconds | Full pair validated |
| --- | ---: | --- |
| 1 | 1.816762 | yes |
| 2 | 1.852946 | yes |
| 3 | 1.676579 | yes |
| 4 | 1.757654 | yes |
| 5 | 1.742179 | yes |

Median 1.757654 seconds, mean 1.769224, maximum 1.852946; zero timeouts.
The authored 12.34 percent value was accepted on attempt 2, its timestamp did
not refresh on unchanged data, and its state became stale after five seconds.
The approved provisional performance and functional conditions passed.
This is not evidence for eight-thread load, arbitrary machines, real-file
latency, GUI rendering or PHITS runtime acceleration.

The preceding full suite (1390 passed, 14 skipped) applies to the unchanged
runtime/test code measured here; it was not repeated solely for this benchmark
and documentation closeout. Compilation, public-tree audit, OpenSpec strict
validation and Git checks were repeated. The four accepted requirements were
promoted into the current live-observation specification. Archived requirement
bodies are checked against the promoted specification. Public physics/DICOM
meaning and execution guards remain unchanged. Eight handoffs and ignored local
benchmark evidence are preserved. No real output was staged or copied into the
public documents. No commit, push, remote PR, merge, or tag change was made.

Closeout check detail: OpenSpec archive succeeded and strict validation of the
resulting tree passed all 19 current specifications. All four archived added
requirement bodies match the promoted specification. The archive command left
an extra blank line at the current specification's EOF; `git diff --check`
reported it, and one whitespace-only correction removed it. The repeated check
passed. Compilation and public-tree audit also passed.

## Authorized PR review closeout on 2026-09-18

The user subsequently authorized PR publication, review-driven fixes, merge
after passing, and branch deletion, including dependency PR #77. PR #78 includes
the dependency's exact decimal metadata fixes. Integrated full validation before
the benchmark correction: 1398 passed, 14 skipped in 318.05 seconds.

Review identified that benchmark acceptance omitted the independent batch
channel. Qualifying attempts now require a successfully parsed authored batch
count as well as the full pair; confirmation requires both expected values and
successful candidate reasons within the limit. Four regressions cover valid,
malformed, wrong-count and rejected-after-confirmation batch records.
Focused numeric/benchmark tests: 84 passed. The initial sandboxed invocation
had 75 passes and 9 temporary-directory permission errors; the approved
external-temporary-directory invocation passed without changing assertions.

Five final integrated attempts with user-reported seven-thread load were
1.896476, 1.878213, 1.781215, 1.716034 and 2.012893 seconds. Median 1.878213,
mean 1.856966; the last attempt timed out and is not a completed parse.
Four full pairs and all five batch candidates validated; both authored values
were confirmed. The approved median acceptance passed, including the failed
attempt in timing statistics. No concurrent pytest ran during measurement.
GUI/process state and eight-thread performance remain unverified.
Compilation, 363-file public-tree audit, 19-specification strict validation
and diff checks passed. Final-head CI and full-suite results are recorded in
the PR closeout; no physics, DICOM meaning or execution guards changed.
