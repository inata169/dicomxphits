# CT2PHITS Frontend Tasks

## 1. Specification and Safety

- [x] 1.1 Confirm the prerequisite development-loop foundation is merged.
- [x] 1.2 Review the CT2PHITS procedure, coordinate-fix specification, existing
  DATfiles implementation, CLI structure, and related tests.
- [x] 1.3 Confirm that automated testing uses only synthetic DICOM and fake or
  mock runners.
- [x] 1.4 Record the approved OpenSpec contract and external-tool boundaries.

## 2. Implementation

- [x] 2.1 Add CT-series selection and inspection.
- [x] 2.2 Create a new external workspace, manifest, and `ct2phits.inp`.
- [x] 2.3 Add the Windows `RTphits_win.bat` execution adapter and execution
  summary.
- [x] 2.4 Validate freshness, presence, size, and SHA-256 for all nine generated
  files.
- [x] 2.5 Hand the eight raw DATfiles to existing validation and asset
  preparation code.
- [x] 2.6 Register and document the standalone CLI.

## 3. Automated Validation

- [x] 3.1 Cover success and handoff behavior with synthetic DICOM and a fake
  runner.
- [x] 3.2 Cover non-Windows refusal, missing batch, non-zero return code,
  timeout, stale or invalid output, and existing workspace refusal.
- [x] 3.3 Run focused frontend and related DATfiles/workspace tests.
- [x] 3.4 Run full pytest, compileall, public-tree audit, and Git diff checks on
  Windows.
- [x] 3.5 Document the later Dev Container cross-check without claiming it has
  already run.

## 4. Human-Directed Validation and Handoff

- [x] 4.1 Run the optional real RT-PHITS smoke test only after explicit human
  authorization with a designated non-patient phantom outside the repository.
- [ ] 4.2 Repeat pytest, compileall, and the public-tree audit in the workplace
  Dev Container. Deferred as a non-blocking workplace cross-check; Linux
  validation is not claimed.
- [x] 4.3 Open a Draft PR when GitHub tooling or connectivity is available.
  Draft PR 3 was created with the GitHub plugin on 2026-08-01.
- [x] 4.4 At task completion, promote the accepted delta specification and move
  this change to `openspec/changes/archive/YYYY-MM-DD-add-ct2phits-frontend/`.
  A post-merge documentation audit found that the archived delta still lacked
  seven review-accepted scenarios already present in the current specification
  from the same squash merge. The archive was synchronized without changing the
  current contract; both forms now contain seven requirements and 25 scenarios.
  OpenSpec CLI `1.6.0` later passed strict validation of the current
  specification and an isolated active-change copy of this archive, with zero
  failures.
