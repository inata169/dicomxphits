# Fix IEC Gantry Direction Tasks

## 1. Investigation and Approval

- [x] 1.1 Trace source position, source direction, `tr3`, central axis, and the
  PHITS-to-DICOM LPS mapping at cardinal and representative oblique angles.
- [x] 1.2 Record the confirmed root cause and bounded correction contract in
  this proposal and delta specification.
- [x] 1.3 Obtain explicit human approval before changing runtime code, test
  expectations, public physics, DICOM behavior, or provenance behavior.

## 2. Synthetic Coordinate Contract

- [x] 2.1 Add independent PHITS and DICOM LPS vector helpers or fixtures for
  gantry 0, 90, 180, 270, 45, and 315 degrees.
- [x] 2.2 Prove source distance, unit direction, and central-axis intersection
  at isocenter for every anchor angle.
- [x] 2.3 Prove `tr3` maps the local accelerator beam axis and upstream source
  point to the same global position and direction as the rendered source.
- [x] 2.4 Prove gantry-zero rendered geometry remains byte-for-byte unchanged
  within the intended source-and-transform scope.

## 3. Bounded Runtime and Provenance Correction

- [x] 3.1 Correct the source lateral sine sign and source position without
  changing source distance, spectrum, aperture, dose factor, or couch scope.
- [x] 3.2 Correct the paired `tr3` sine signs so the accelerator geometry stays
  aligned with the source and isocenter central axis.
- [x] 3.3 Add corrected gantry-geometry provenance and fail closed when old
  nonzero or ambiguous transport evidence is selected for reuse.
- [x] 3.4 Preserve all-zero-gantry evidence only when its unchanged geometry is
  unambiguously proven.

## 4. Boundaries and Documentation

- [x] 4.1 Document that affected nonzero-gantry cases require regenerated
  segment inputs, PHITS, Sumtally, and RTDOSE results.
- [x] 4.2 Confirm no final-DICOM-only mirror or RTDOSE affine workaround is
  introduced.
- [x] 4.3 Confirm PLAN/fraction dose semantics, physical dose values, MU,
  normalization, factors, and public source/aperture physics remain unchanged.
- [x] 4.4 Keep real PHITS, Sumtally, phits2dicom, GPR, and real DICOM validation
  pending a later explicit human approval.

## 5. Validation and Completion

- [x] 5.1 Run focused synthetic source, transform, workspace, and recovery
  tests.
- [x] 5.2 Run source compilation, the full public pytest suite, public-tree
  verification, and Git diff/status checks.
- [x] 5.3 Run strict OpenSpec validation and inspect the complete diff.
- [x] 5.4 After all approved acceptance criteria pass, promote the delta,
  archive the change, and validate the resulting specification tree.
