# Fix RTDOSE Isocenter Translation

## Why

A human-operated Windows end-to-end test with a designated non-patient
phantom completed CT2PHITS, workspace preparation, PHITS, Sumtally, and
RTDOSE conversion, but the final coordinate-corrected RTDOSE was displaced in
all three orthogonal views and could not be accepted by the external research
comparison. Read-only diagnosis found that RTDOSE Prepare writes the selected
CT reference slice's `ImagePositionPatient` into the PHITS dose metadata and
the coordinate correction then preserves the resulting source volume center.
The frozen RT Plan isocenter and the generated PHITS tally mesh geometry are
not used to establish the final patient-coordinate placement.

The CT reference slice position identifies one CT voxel; it is not the origin
of an independently sized PHITS dose grid. Treating it as authoritative dose
placement can therefore produce a valid-looking DICOM object with a wrong
translation while RTDOSE Run still reports success.

## What Changes

- Bind final RTDOSE placement to the frozen RT Plan, the recorded CT-to-PHITS
  coordinate transform, and the exact PHITS tally mesh geometry used to create
  the converted dose.
- Derive the final DICOM voxel affine and `ImagePositionPatient` from the
  reviewed PHITS/IEC-to-DICOM mapping instead of preserving a center inherited
  from the CT reference slice position.
- Keep any CT reference `ImagePositionPatient` required by `phits2dicom`
  explicitly classified as converter-compatibility input rather than final
  dose-placement evidence.
- Preserve accepted Sumtally and companion PHITS results byte-for-byte by
  applying converter-compatibility title patches only to RTDOSE-private copies.
  Permit recovery of a historical in-place IPP title patch only when its exact
  inverse reproduces the recorded Sumtally Run SHA-256; reject every other
  mismatch without rewriting the upstream result.
- Record the source geometry, frozen-plan isocenter, tally bounds and voxel
  centers, transform version, derived target geometry, translation, and final
  patient-coordinate checks in the coordinate summary.
- Fail closed before reporting RTDOSE Completed when the isocenter, tally
  geometry, coordinate transform, or resulting patient-coordinate placement
  is missing, ambiguous, stale, or inconsistent.
- Permit a case-specific target placement only as an explicit, finite,
  reasoned override with provenance; do not introduce a hidden universal
  target center.
- Validate the mapping with synthetic nonzero isocenters, asymmetric tally
  bounds, anisotropic spacing, and unequal dimensions so centered or isotropic
  fixtures cannot mask a translation or axis error.
- Preserve stored dose values, `DoseGridScaling`, units, MU and normalization
  semantics, PHITS results, and the fixed-field 3D-CRT research boundary.

## Impact

- Affected capability: `rtdose-dicom-semantics`
- Likely affected runtime after separate approval:
  `prepare_rtdose.py`, `fix_coordinates.py`, CT2PHITS/workspace geometry
  provenance, and RTDOSE stage validation
- Likely affected tests: synthetic RT Plan/tally affine mapping, explicit
  target override, stale or ambiguous geometry rejection, coordinate summary,
  and RTDOSE Completed-state gating
- Affected documentation: RTDOSE coordinate placement and Windows manual
  validation guidance
- Unchanged boundaries: PHITS transport and segment outputs, Sumtally
  weighting, public dose factor, MU normalization, source and accelerator
  physics, DICOM identity policy, external GPR implementation, and clinical
  claims

## Approval Status

The human approved creation of this proposal and, on 2026-08-04, approved
documenting the exact plan-and-tally coordinate rule and numerical tolerance
in the design and delta specification. The human then explicitly approved
implementation of the full proposal on a dedicated feature branch. That
approval covers repository runtime, synthetic/mock tests, and documentation.
The human later separately approved coordinate-only RTDOSE Prepare/Run and
research comparison for one already designated non-patient phantom, reusing
its existing PHITS and Sumtally results. That limited approval does not permit
PHITS or Sumtally recalculation, Factor/MU/normalization changes, additional
external data, or repository inclusion of paths, DICOM, tools, or results.
Dose-factor work and OpenSpec promotion or archival remain separate decisions.
