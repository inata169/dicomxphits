# RTDOSE Full-Plan Reference Tasks

## 1. Specification and Approval

- [x] 1.1 Inspect the generated-output evidence, current RTDOSE adapter,
  workspace manifest, GUI handoff, tests, and repository safety rules.
- [x] 1.2 Record the full-plan semantic correction and unchanged dose/geometry
  boundaries.
- [x] 1.3 Obtain human approval of the OpenSpec proposal before runtime changes.
  The human maintainer approved the proposed PLAN semantics and frozen-plan
  synchronization on 2026-08-02.

## 2. Implementation

- [x] 2.1 Add frozen RT Plan identity and full-plan coverage validation to
  RTDOSE preparation.
- [x] 2.2 Pass the visible frozen RT Plan from the guided GUI to RTDOSE Prepare.
- [x] 2.3 Synchronize the converted RT Dose to PLAN semantics and the exact
  frozen RT Plan reference before coordinate correction.
- [x] 2.4 Validate the final coordinate-corrected output and fail closed on
  stale or inconsistent references.
- [x] 2.5 Preserve pixel-dose, scaling, units, geometry, coordinates, Frame of
  Reference, normalization, and public safety boundaries.
- [x] 2.6 Update RTDOSE CLI and workflow documentation.

## 3. Validation

- [x] 3.1 Add synthetic tests for stale-template replacement and exact plan
  reference synchronization.
- [x] 3.2 Add synthetic failure tests for plan identity, workflow mode, delivery
  coverage, and final-output validation.
- [x] 3.3 Add preservation tests for dose values and DICOM geometry.
- [x] 3.4 Run focused RTDOSE and GUI tests. The RTDOSE, manual smoke,
  coordinate, and GUI selection passed `80` tests.
- [x] 3.5 Run `python -m compileall src`. Passed with the repository-local
  Python environment.
- [x] 3.6 Run `python -m pytest -q -p no:cacheprovider`. Passed all `474`
  synthetic/mock public tests.
- [x] 3.7 Run `python tools/verify_public_tree.py`. Passed with `97` staged
  public files checked.
- [x] 3.8 Run `git diff --check`, `git diff --stat`, and `git status --short`.
  The staged diff passed whitespace validation and contains only the approved
  RTDOSE semantic correction, tests, documentation, and OpenSpec records.

## 4. Completion

- [x] 4.1 Update the task checklist with exact validation evidence and any
  explicitly deferred non-blocking item.
- [x] 4.2 Promote the accepted delta into the current specification tree.
- [x] 4.3 Archive the completed change and validate the resulting OpenSpec tree.
  OpenSpec CLI archived the change as
  `2026-08-02-fix-rtdose-plan-references`; strict validation passed all three
  current specifications with zero failures.
- [x] 4.4 Create a reviewable pull request without merging it automatically.
  Draft pull request #8 was created on 2026-08-02:
  https://github.com/inata169/dicomxphits/pull/8

## 5. Final Review Correction

- [x] 5.1 Bind Sumtally Generate, Sumtally Run, and RTDOSE preparation to one
  canonical segment-manifest SHA-256.
- [x] 5.2 Align RTDOSE treatment-delivery eligibility with workspace
  preparation by accepting empty, `TREATMENT`, and `CONTINUATION` values.
- [x] 5.3 Add focused regression tests and rerun all required validation.
  Focused tests passed (100), the full public suite passed (478), compilation
  succeeded, and strict OpenSpec validation passed (3 specifications).

## 6. Approved Review Blocker Correction

- [x] 6.1 Bind Sumtally execution evidence to the exact generated wrapper path
  and to SHA-256 values for the wrapper and `sumtally.inp`.
- [x] 6.2 Reject custom or edited Sumtally inputs before external execution and
  require matching Generate/Run input evidence during RTDOSE preparation.
- [x] 6.3 Add focused regressions and rerun all required validation.
  Focused Sumtally/RTDOSE tests passed (50), the full public suite passed (482),
  compilation succeeded, the public-tree audit passed (97 tracked files), and
  strict OpenSpec validation passed (3 specifications).

## 7. Approved Sumtally Output Provenance Correction

- [x] 7.1 Require Sumtally Run to update its expected output and record the
  resulting SHA-256.
- [x] 7.2 Verify the Run output digest at RTDOSE Prepare and the post-Prepare
  digest at RTDOSE Run.
- [x] 7.3 Add stale/replaced-output regressions and rerun required validation.
  Focused Sumtally/RTDOSE/manual-smoke tests passed (58), the full public suite
  passed (485), compilation succeeded, the public-tree audit passed (97 tracked
  files), and strict OpenSpec validation passed (3 specifications).

## 8. Approved Non-Treatment Beam Validation Correction

- [x] 8.1 Derive active coverage from treatment-eligible referenced beams and
  permit other delivery types only as skipped zero-segment-MU evidence.
- [x] 8.2 Preserve and validate existing all-referenced-beam plan, included,
  and normalization MU totals without changing dose calculation.
- [x] 8.3 Add treatment-plus-SETUP regressions and rerun required validation.
  Focused workspace/Sumtally/RTDOSE tests passed (107), the full public suite
  passed (487), compilation succeeded, the public-tree audit passed (97 tracked
  files), and strict OpenSpec validation passed (3 specifications).
