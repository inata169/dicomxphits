# Fix RTDOSE Isocenter Translation Tasks

## 1. Approval and Coordinate Contract

- [x] 1.1 Obtain explicit human approval of this proposal before runtime or
  test implementation.
- [x] 1.2 Obtain the qualified-human decision for the exact public
  PHITS-tally-bin-centre to DICOM-patient affine and numerical tolerance.
- [x] 1.3 Pin a focused feature branch and confirm no unrelated proposal or
  runtime change is included.

## 2. Synthetic Geometry Evidence

- [x] 2.1 Add synthetic frozen-plan and tally-geometry fixtures with nonzero
  isocenters, asymmetric bounds, unequal dimensions, and anisotropic spacing.
- [x] 2.2 Prove the exact tally-index to output-index permutation independently
  of maintained implementation output.
- [x] 2.3 Prove first, center, edge, and final voxel patient coordinates from
  independent expected affine values.
- [x] 2.4 Add rejection tests for missing, stale, inconsistent, or unsupported
  plan, tally, transform, and DICOM geometry evidence.

## 3. Evidence-Bound Placement Implementation

- [x] 3.1 Record and bind the exact PHITS tally geometry needed by RTDOSE
  placement without changing generated PHITS inputs.
- [x] 3.2 Restore coordinate correction support for a plan-and-tally-derived
  target geometry.
- [x] 3.3 Keep CT reference `ImagePositionPatient` explicitly classified as
  converter-compatibility metadata rather than final placement evidence.
- [x] 3.4 Support only finite, explicitly reasoned target overrides and record
  complete override provenance.
- [x] 3.5 Record source, expected, and output affines, translation, rule
  version, geometry hashes, and coordinate residuals.
- [x] 3.6 Preserve stored dose values, `DoseGridScaling`, units, MU,
  normalization, plan references, and Frame of Reference.
- [x] 3.7 Preserve upstream Sumtally and companion PHITS outputs by patching
  only RTDOSE-private copies, with exact-hash migration for the historical
  in-place IPP title patch.

## 4. RTDOSE and GUI Fail-Closed Integration

- [x] 4.1 Revalidate plan, tally, transform, and placement evidence before
  conversion and final acceptance.
- [x] 4.2 Fail RTDOSE Run when the final voxel affine does not match the
  expected mapped tally geometry within the approved tolerance.
- [x] 4.3 Prove the GUI does not show RTDOSE Completed after a coordinate
  placement validation failure.
- [x] 4.4 Preserve existing Not run and Prepared behavior when coordinate
  evidence is valid and execution has not completed.

## 5. Documentation and Proportional Manual Validation

- [x] 5.1 Update RTDOSE coordinate and Windows manual-test documentation
  without adding external paths, DICOM identifiers, or calculation results.
- [x] 5.2 Obtain separate approval before reprocessing any existing designated
  non-patient phantom evidence.
- [ ] 5.3 Reuse existing PHITS and Sumtally results for coordinate-only manual
  validation unless a separately approved change requires recalculation.
- [x] 5.4 Record remaining dose-normalization work as outside this coordinate
  change without changing its factor or MU semantics.

## 6. Validation and Completion

- [x] 6.1 Run focused coordinate, RTDOSE, and GUI synthetic/mock tests.
- [x] 6.2 Run source compilation, the full public pytest suite, public-tree
  verification, and Git diff/status checks.
- [x] 6.3 Run strict OpenSpec validation and inspect the complete proposal
  diff.
- [ ] 6.4 After all approved criteria pass, promote the delta, archive the
  change, and validate the resulting specification tree before completion.
