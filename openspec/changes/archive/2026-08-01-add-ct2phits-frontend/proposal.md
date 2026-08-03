# Add CT2PHITS Frontend Stage

## Why

Converting a DICOM CT series into validated CT2PHITS DATfiles previously
required a fragile manual Windows procedure. The public workflow needs a
standalone, auditable stage that prepares the external workspace, uses the
verified RT-PHITS batch path, validates every generated file, and hands the
result to the existing workspace-preparation boundary.

## What Changes

- Add CT-series selection and fail-closed DICOM inspection.
- Create a new external CT2PHITS workspace, manifest, and OpenSpec-compatible
  `ct2phits.inp`.
- Invoke `RTphits_win.bat` on Windows with timeout, return-code, log, and stale
  output handling.
- Inventory all nine CT2PHITS outputs and record non-empty file sizes,
  timestamps, and SHA-256 values.
- Validate the eight downstream raw DATfiles and reuse the existing coordinate
  transformation preparation to produce the six workspace assets, including
  `CTtrans.inp`.
- Add a standalone CLI, synthetic/mock tests, and Windows plus Dev Container
  verification documentation.
- Adopt OpenSpec change management for this and future capability work.

## Impact

- Affected capability: `ct2phits-frontend`
- Affected runtime: `src/dicomxphits/run_ct2phits.py`, the existing CT2PHITS
  DATfiles handoff, and the package CLI table
- Affected tests: focused frontend adapter tests and the full public suite
- Affected documentation: workflow, development, and CLI usage documentation
- External dependency: a human-supplied RT-PHITS installation; no distribution
  files are added to the repository

## Approval History

The original implementation request explicitly prohibited creating a new
OpenSpec change, so implementation and mock validation preceded this document.
On 2026-08-01, the human maintainer explicitly approved adding OpenSpec change
management and recording this still-unmerged feature as an active change.

## Completion

The implementation, focused and full Windows mock validation, public-boundary
audit, and an explicitly authorized non-patient phantom smoke test completed on
2026-08-01. Draft PR 3 was created with the GitHub plugin on 2026-08-01. The
human maintainer approved promotion and archive on 2026-08-01. The deferred
workplace Dev Container cross-validation later completed on 2026-08-03 for
pull requests #1 through #9, as recorded in
`docs/dev-container-validation-2026-08-03.md`.
