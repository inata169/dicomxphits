# Fix IEC Collimator Direction Tasks

## 1. Investigation and Approval

- [x] 1.1 Trace the DICOM Beam Limiting Device Angle from RT Plan state through
  the segment manifest to the PHITS accelerator `tr2` transform.
- [x] 1.2 Derive the current and required DICOM LPS beam-limiting axes and
  record the bounded correction in this proposal and delta specification.
- [x] 1.3 Obtain explicit human approval before changing runtime code, tests,
  normative specifications, provenance behavior, or external workspaces.

## 2. Synthetic Collimator Contract

- [x] 2.1 Add independent DICOM LPS MLCX and MLCY axis fixtures for
  collimator 0, 30, 90, 180, and 270 degrees at fixed gantry and couch zero.
- [x] 2.2 Prove the transformed axes are unit length, mutually perpendicular,
  and perpendicular to the unchanged central beam axis.
- [x] 2.3 Add a labeled asymmetric-aperture fixture that distinguishes
  positive DICOM collimator rotation from the negative rotation.
- [x] 2.4 Prove collimator-zero rendered geometry remains unchanged.

## 3. Bounded Runtime and Provenance Correction

- [x] 3.1 Reverse only the collimator angle application sign in accelerator
  `tr2`, preserving the DICOM angle stored in state, manifests, and summaries.
- [x] 3.2 Prove source geometry, gantry `tr3`, MLC leaf positions, jaws,
  isocenter, and final tally-to-DICOM mapping remain unchanged.
- [x] 3.3 Add the combined
  `dicomxphits_iec_gantry_mlcx_collimator_geometry_v4` provenance contract.
- [x] 3.4 Reject every v3 or older geometry contract before PHITS reuse,
  Sumtally, or RTDOSE generation, regardless of recorded collimator angle.
- [x] 3.5 Reject missing, mixed, or ambiguous geometry provenance and require
  newly prepared v4 inputs followed by complete downstream recalculation.

## 4. Boundaries and Documentation

- [x] 4.1 Document that every pre-v4 case requires regenerated segment inputs
  and rerun PHITS, Sumtally, and RTDOSE without an angle-based exception.
- [x] 4.2 Confirm no final-DICOM mirror, affine rewrite, angle relabel, MLC leaf
  rewrite, or jaw rewrite is introduced.
- [x] 4.3 Confirm gantry geometry, dose values, MU, normalization,
  PLAN/fraction semantics, source physics, and treatment scope are unchanged.
- [x] 4.4 Keep external PHITS, Sumtally, phits2dicom, GPR, DICOM, and
  calculation-result validation outside repository automation and subject to
  separate explicit human approval.

## 5. Validation and Completion

- [x] 5.1 Run focused synthetic transform, renderer, provenance, and recovery
  tests.
- [x] 5.2 Run source compilation, the full public pytest suite, public-tree
  verification, and Git diff/status checks. The focused change tests pass; the
  full suite retains the same 45 environment-dependent failures recorded
  before implementation, with no new failing test.
- [x] 5.3 Run strict OpenSpec validation and inspect the complete diff.
- [x] 5.4 After approved implementation and repository checks, obtain the
  separately authorized human external comparison outcome.
- [x] 5.5 After all approved acceptance criteria pass, promote the delta,
  archive the change, and validate the resulting specification tree.
