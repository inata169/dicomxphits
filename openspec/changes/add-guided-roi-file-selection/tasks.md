# Implementation checklist

## Proposal and approval

- [x] Reproduce the read-only source-member control and ambiguous labels.
- [x] Draft the canonical suggestion and manual-override contract.
- [x] Obtain primary-user approval for automatic unique suggestions.

## Implementation after approval

- [x] Add source-member pickers and editable controls.
- [x] Add unique canonical suggestions and explicit ambiguity state.
- [x] Preserve external DICOM selection and ROI validation boundaries.
- [x] Add the Japanese usage guide and update English guidance.

## Validation and completion

- [x] Run focused synthetic selection and GUI tests.
- [x] Run full public checks and inspect the final diff.
- [ ] Promote accepted deltas and archive when all required decisions are met.

## Validation record (2026-10-08)

- The primary user approved unique, editable canonical suggestions on
  2026-10-08.
- Synthetic focused GUI tests passed. The full suite passed with 1494 tests,
  15 skips, and one intentional duplicate-ZIP-member warning.
- `python -m compileall src`, independent tool `py_compile`,
  `python tools/verify_public_tree.py`, and Git diff checks passed. The public
  tree audit checked 429 staged files. The OpenSpec CLI is unavailable;
  the four change documents received a manual structural review.
- All seven explicitly selected ZIPs were inspected read only. Unique
  canonical suggestions supplied each required sphere input; the independent
  validator accepted each selected combination. No local results or
  identifiers were saved in this repository.
- The primary user authorized PR publication on 2026-10-08. Final validation,
  publication, and the completion archive are now in progress.
