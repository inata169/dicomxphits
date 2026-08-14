## 1. Approval Gate

- [x] 1.1 Obtain explicit human yes/no approval of this proposal before changing
  runtime code, test expectations, public dose semantics, or documentation.

## 2. Fraction Evidence and Course-Dose Contract

- [x] 2.1 Require exactly one frozen RT Plan Fraction Group and a positive
  integer `NumberOfFractionsPlanned`.
- [x] 2.2 Bind the Fraction Group number, planned fraction count, frozen-plan
  content, one-fraction input dose state, base factor, effective factor,
  equation, and contract version in RTDOSE preparation evidence.
- [x] 2.3 Revalidate the frozen plan, fraction evidence, prepared input digest,
  and course-dose contract before external RTDOSE execution.
- [x] 2.4 Reject legacy or stale completion/recovery evidence that lacks the
  current course-dose contract and direct it to RTDOSE Prepare regeneration.

## 3. RTDOSE Course Scaling

- [x] 3.1 Preserve the approved public-model base factor `1.0`, Sumtally bytes,
  `sumfactor`, MU weighting, calibration, and PHITS outputs.
- [x] 3.2 Pass `1.0 * NumberOfFractionsPlanned` as the guarded effective
  PHITS2DICOM factor exactly once.
- [x] 3.3 Keep plan-reference synchronization dose-preserving and coordinate
  correction a pure stored-voxel permutation; do not scale final PixelData.
- [x] 3.4 Record sufficient final semantic evidence to distinguish a complete
  course-dose RTDOSE from a legacy one-fraction PLAN-labeled output.

## 4. Synthetic Tests

- [x] 4.1 Prove one planned fraction keeps effective factor `1.0` and existing
  numerical behavior.
- [x] 4.2 Prove representative multiple-fraction counts produce
  `dose_per_fraction * NumberOfFractionsPlanned` with synthetic DICOM and a fake
  converter.
- [x] 4.3 Prove MU, Sumtally normalization, upstream PHITS/Sumtally bytes,
  coordinates, and geometry are unchanged.
- [x] 4.4 Reject missing, empty, zero, negative, non-integral, non-finite,
  multiple, changed, and stale fraction evidence before external execution.
- [x] 4.5 Prove final synchronization/correction preserves the course-scaled
  physical dose and recovery rejects legacy provenance.

## 5. Documentation and Validation

- [x] 5.1 Document the one-fraction Sumtally boundary, PLAN course-dose equation,
  factor stages, fail-closed rules, and required RTDOSE regeneration.
- [x] 5.2 Run focused synthetic tests without real DICOM or external dose tools.
- [x] 5.3 Run the full public checks, OpenSpec strict validation, and diff/status
  inspection.
- [x] 5.4 Confirm no change to gantry geometry, DICOM coordinates, MU,
  normalization, calibration, PHITS/Sumtally numerical outputs, tags, the
  unapproved coordinate-output proposal, or unrelated branches.
- [x] 5.5 Stop before any real PHITS, Sumtally, PHITS2DICOM, GPR, or real-DICOM
  execution and request separate explicit human approval if such validation is
  later needed.
