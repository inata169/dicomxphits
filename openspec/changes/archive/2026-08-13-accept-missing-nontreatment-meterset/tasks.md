# Tasks

## 1. Approval

- [x] 1.1 Obtain explicit human approval before changing runtime behavior.

## 2. Regression and implementation

- [x] 2.1 Add a synthetic regression reproducing a referenced non-treatment
  beam with an absent `BeamMeterset`, skipped zero-MU manifest evidence, and a
  successful RTDOSE Prepare result.
- [x] 2.2 Add rejection coverage for a missing treatment-beam meterset and for
  malformed, negative, non-finite, active, or manifest-inconsistent
  non-treatment evidence.
- [x] 2.3 Implement the narrow missing non-treatment meterset interpretation
  and record its use in full-plan evidence.

## 3. Validation and completion

- [x] 3.1 Run the focused RTDOSE and manifest-construction tests (72 passed).
- [x] 3.2 Run compilation, the complete pytest suite (713 passed, 28 skipped),
  public-tree verification (182 tracked files), strict OpenSpec validation
  (9 passed), and Git diff/status checks.
- [x] 3.3 Record real phits2dicom and real DICOM rerun as unverified; neither
  external execution was requested or run.
- [x] 3.4 Promote the accepted delta, archive this completed change, and
  validate the resulting OpenSpec tree.
