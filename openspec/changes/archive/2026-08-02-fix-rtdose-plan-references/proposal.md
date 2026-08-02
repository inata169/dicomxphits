# Fix RTDOSE Full-Plan References

## Why

The public workflow converts the all-active-segments Sumtally result, but the
generated RT Dose can retain `DoseSummationType` and plan-reference sequences
from the user-supplied template. A successful conversion can therefore be
labeled as a beam dose and reference a different RT Plan or only part of the
delivery even though its pixel data represents the complete accepted
`full_plan` calculation. The execution stage currently does not validate this
semantic relationship before reporting success.

## What Changes

- Require RTDOSE preparation to receive the same frozen RT Plan used for the
  prepared 3D-CRT workspace and record its validated synthetic-safe identity
  evidence for the execution stage.
- Verify that the workspace manifest represents the accepted `full_plan`
  workflow and covers the treatment beams referenced by that RT Plan before
  assigning plan-level dose semantics.
- Set the converted RT Dose to `DoseSummationType = PLAN`, replace any stale
  template plan reference with exactly one reference to the frozen RT Plan,
  and remove template-derived fraction-group and beam references that would
  describe a partial delivery.
- Validate the final coordinate-corrected RT Dose after synchronization and
  fail the stage instead of reporting success when its summation type or RT Plan
  reference is missing, stale, or inconsistent.
- Preserve the calculated pixel data, dose scaling and units, coordinate
  correction, Frame of Reference, normalization, and public research-only
  boundaries.
- Add synthetic DICOM and fake-runner tests and document the full-plan RT Dose
  output contract and the required frozen RT Plan input.

## Impact

- Affected capability: new `rtdose-dicom-semantics` contract
- Affected runtime: RTDOSE preparation and execution adapters, plus the guided
  GUI command that supplies its already visible frozen RT Plan
- Affected tests: synthetic RT Plan/RT Dose preparation and execution tests and
  focused GUI command tests
- Affected documentation: RTDOSE adapter inputs, output selection, and semantic
  validation evidence
- Migration: existing segment PHITS outputs remain reusable. Workspaces created
  before manifest-digest evidence was added rerun Sumtally Generate, Sumtally
  Run, RTDOSE Prepare, and RTDOSE Run with the original frozen RT Plan; segment
  PHITS calculations do not need to be repeated
- Unchanged boundaries: PHITS and Sumtally results, pixel-dose values, DICOM
  geometry and coordinate correction, dose calibration, MU and normalization,
  fixed-field 3D-CRT scope, and non-clinical research status
