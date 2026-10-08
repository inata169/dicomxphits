# Implementation checklist

## 1. Proposal

- [x] Inspect repository rules, current specifications, and relevant parsers.
- [x] Record the approved radius/sampling-volume distinction.
- [x] Draft the independent analysis contract and synthetic acceptance cases.
- [x] Validate the proposal structure and review material ambiguities.
- [x] Obtain explicit human approval of the implementation proposal.

## 2. Independent reader and regions (after approval)

- [x] Add `tools/phits_roi_stats.py` for Python 3.12 and NumPy, without an
  installed dicomxphits package or GUI dependency.
- [x] Implement explicit directory/ZIP member selection, bounded safe reads,
  immutable provenance, dose/error pairing, and saved normalization checks.
- [x] Support selected retained pairs without recovery writes or discovery.
- [x] Decode native grid coordinates, sphere membership, sampling counts,
  analytic/sampling/native volumes, and same-grid non-DICOM Structure masks.

## 3. Statistics and reports (after approval)

- [x] Implement the defined cGy dose summaries and separate voxel r.err and
  absolute-standard-error summaries, with explicit populations and statuses.
- [x] Implement console output, explicit multi-case batch input, and guarded
  new-only CSV/JSON reports with spreadsheet-safe strings and provenance.
- [x] Add `docs/phits-roi-statistics.md` with synthetic usage examples,
  output definitions, compatible formats, and known limits.

## 4. Validation (after approval)

- [x] Add focused synthetic tests in `tests/test_phits_roi_stats.py` covering
  both supported source layouts, pairing/normalization failures, axis order,
  zero/one/many selected cells, region boundaries and offsets, Structure
  geometry mismatch, statistical formulas, zero-error handling, and exports.
- [x] Check the radius-0.25-cm examples: sampling Points 81 and volume
  0.081 cm3; aligned 2 mm Grid Points 7; offset 3 mm Grid Points 2.
- [x] Run the focused tests and `python -m py_compile tools/phits_roi_stats.py`.
- [x] Run `python -m compileall src`.
- [x] Run `python -m pytest -q -p no:cacheprovider`.
- [x] Run `python tools/verify_public_tree.py`.
- [x] Run `git diff --check`, `git diff --stat`, and `git status --short`.
- [x] Confirm input identity and an authorized output destination before any
  local phantom report. Record the requested case results outside the public
  repository, or obtain an explicit deferral for unavailable cases/masks.
  Do not call synthetic compatibility an actual v1.1.1-output validation.

## 5. Completion (after approval)

- [x] Produce a reviewable pull request within the authorized external-write
  scope; never merge or publish a release automatically.
- [x] Record acceptance results and any explicitly deferred real-data checks.
- [x] Promote accepted deltas to `openspec/specs/standalone-phits-roi-statistics/`.
- [x] Archive this completed change under its completion date and validate
  the resulting specification tree.
- [x] Report changed files, checks, unverified items, and stopping outcome.

The change remains active while approval, implementation, or required checks
are outstanding. Planning-stage checks do not mark implementation tasks done.

## Implementation validation record (2026-10-08)

- Approved in the implementation request on 2026-10-08.
- Synthetic focused tests: 10 passed. They cover saved and retained pair
  selection, parsing, axis order, geometry examples, Structure mask, partial
  and empty results, pairing and digest failures, batch input, exports, and
  rejection of hard-linked input files.
- `python -m py_compile tools/phits_roi_stats.py`: passed.
- `python -m compileall src`: passed.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`: 1484 passed,
  15 skipped, with one expected duplicate-ZIP-member warning from a rejection
  test (138.54 seconds). The default Python remains unsuitable for pytest
  because NumPy and pydicom are absent; the existing `.venv` is used.
- `python tools/verify_public_tree.py`: passed with all seven intended files
  staged (417 tracked files checked).
- Three explicitly selected local phantom ZIPs were read only. Each retained
  dose matched its selected official dose and terminal digest, and each case
  produced a two-cell central-sphere result. Values were returned in chat,
  the authorized report destination, without creating a local report file.
  No actual Structure mask was supplied, so actual Chamber Structure values
  remain unverified. No actual v1.1.1 saved output was supplied.
- Four additional explicitly selected local phantom ZIPs were read only and
  returned central-sphere results in chat. An independent scalar coordinate
  check confirmed the observed one- versus two-cell native populations.
  A synthetic bug check exposed acceptance of a hard-linked input; the
  script now rejects it, and the focused and full suites pass. No local
  result or identifier was added to the repository.
- OpenSpec CLI is unavailable. Manual structural review passed for the active
  four-document change, including nine added requirements and scenarios.
- `git diff --check` and `git diff --cached --check`: passed. Staged diff
  contains seven intended files; pre-existing untracked files are untouched.
- Pull-request external write remains subject to a separate human decision;
  no remote write has been attempted.

## Planning-stage validation record (2026-10-08)

- OpenSpec CLI is not installed. Manual structural review plus a read-only
  Python check passed for all four UTF-8 documents, the required proposal
  headings, nine added requirements, and their WHEN/THEN scenarios.
  This is not a strict OpenSpec CLI validation result.
- An independent read-only review found no required plan correction.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider`: collection failed with 30
  errors because the default interpreter lacks NumPy and pydicom.
- The existing `.venv` interpreter has the dependencies, but sandboxed runs
  failed on test temporary-directory access. The initial and fresh-local-
  temporary-directory full runs were interrupted after repeated setup
  errors; focused diagnostics confirmed the permission error. No test or
  runtime code was changed to bypass it.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`, run with
  approved execution permissions: 1474 passed, 15 skipped in 143.10 seconds.
- `python tools/verify_public_tree.py`: passed, including the four staged
  proposal documents (414 tracked files).
- `git diff --check` and `git diff --cached --check`: passed.
- `git diff --stat`, `git diff --cached --stat`, and `git status --short`:
  only the four new proposal documents are staged; pre-existing untracked
  files are preserved.

Runtime implementation, the future script's focused tests, real-output
analysis, and actual v1.1.1-output compatibility remain unverified. No accepted
specification was changed. The proposal remains active and unarchived pending
human approval; no commit or pull request has been created at this stage.

## Final validation and publication (2026-10-08)

- PR #90 is open as a draft; external publication was authorized by the user.
- Full pytest: 1495 passed, 15 skipped, one intentional duplicate-member warning.
- Focused GUI tests: 11 passed. Compilation, public-tree audit, and Git
  whitespace checks passed. Native Computer Use validation is recorded in
  `docs/phits-roi-gui-validation.md`.
- OpenSpec CLI 1.14.1 validates all three ROI changes in strict mode. Existing
  unrelated specs have strict warnings; their contracts were not modified.
- Real Structure values and actual saved newer-format output remain unverified
  where the required inputs were unavailable; no real results were tracked.
- Accepted deltas were promoted with the OpenSpec CLI and archived on
  2026-10-08. Both resulting ROI specifications pass strict CLI validation.
  Earlier planning and intermediate records above describe their historical
  state and are superseded by this final record.
