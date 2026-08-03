# Tasks

## 1. Standard Windows tool resolution

- [x] 1.1 Select `bin/phits335_win_openmp.exe` in the PHITS 3.35 standard
  profile and fail visibly when it is absent.
- [x] 1.2 Select the exact Windows `phits2dicom_win.exe` candidate without
  treating Linux and macOS binaries as eligible.
- [x] 1.3 Add synthetic standard/custom profile tests.

## 2. Workspace runtime contract

- [x] 2.1 Add shared positive-integer defaults and validation for `maxcas`,
  `maxbch`, and OpenMP threads.
- [x] 2.2 Add workspace-preparation CLI options and propagate them to every
  generated segment input.
- [x] 2.3 Preserve `$OMP = N`, map it to `OMP_NUM_THREADS=N` at direct
  execution, and record all effective values in preparation summaries.
- [x] 2.4 Add focused renderer, CLI, summary, and segment-runner tests.

## 3. Guided GUI

- [x] 3.1 Add clearly labelled runtime controls to the Workspace page with
  defaults `1000000`, `10`, and `8`.
- [x] 3.2 Validate values before starting workspace preparation and pass them
  through the accepted CLI.
- [x] 3.3 Persist only valid local runtime preferences with backward-compatible
  fallback defaults.
- [x] 3.4 Add synthetic GUI validation, command, and settings tests.

## 4. Documentation and validation

- [x] 4.1 Document the Windows OpenMP default, `$OMP` syntax, setting meanings,
  new-workspace-only behavior, and custom-layout escape hatch.
- [x] 4.2 Run focused tests and the full public validation suite.
- [x] 4.3 Inspect the final diff for runtime/spec alignment and confirm that no
  external PHITS or real DICOM execution occurred.
- [x] 4.4 Promote accepted deltas, archive this change, and validate the final
  OpenSpec tree after all acceptance criteria are met.
