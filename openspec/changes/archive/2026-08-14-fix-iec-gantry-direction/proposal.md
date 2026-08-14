# Fix IEC Gantry Direction

## Why

The generated PHITS source and accelerator transform use the DICOM RT Plan
gantry angle with the opposite lateral sign from the IEC 61217 gantry
convention used by DICOM. The current source direction is
`d_PHITS = (-sin(g), 0, cos(g))`. Under the accepted fixed-coordinate mapping
`d_DICOM_LPS = (-d_x, d_z, d_y)`, this becomes
`(+sin(g), cos(g), 0)` in patient coordinates.

For a head-first-supine patient with zero couch angle, the IEC/DICOM central
axis is instead `(-sin(g), cos(g), 0)`: at 90 degrees the source is on the
positive DICOM X side and the beam travels toward negative DICOM X. The
current implementation places the source on the negative DICOM X side and
transports toward positive DICOM X. The lateral component is therefore
mirrored for every non-cardinal-oblique angle and is fully reversed at 90 and
270 degrees. Gantry 0 and 180 degrees cannot expose this defect because their
lateral sine component is zero.

The current source position, source direction, and `tr3` matrix are internally
consistent with one another, but all three implement the same reversed gantry
rotation. Existing tests assert selected rendered strings at 90 degrees; they
do not anchor the source, central axis, and transformed accelerator geometry
in DICOM patient coordinates. A final-RTDOSE mirror cannot repair transport
that traversed the CT voxel phantom from the wrong side.

Authorized read-only research OpenSpec records explain why the reversed sign
survived migration: the `-sin(g)` Source/transform pair was preserved after a
prior gantry-90 transport and downstream comparison, while that historical
RTDOSE correction used `source.transpose(1, 0, 2)` without an IEC-X reversal.
The current public pipeline now uses
`source.transpose(1, 0, 2)[:, :, ::-1]` to implement the documented
PHITS-X-to-DICOM-X reversal. The old comparison therefore does not validate
the current combined source-plus-output convention. The most likely migration
root cause is that a source-side lateral parity compensation for the former
output mapping was retained after the output mapping gained its explicit X
reversal. This historical explanation is an inference; the patient-coordinate
sign mismatch above follows directly from the current published mapping and
does not depend on that inference.

## What Changes

- Apply the DICOM gantry angle with the IEC-consistent lateral sign to both the
  PHITS source and accelerator `tr3` transform.
- Keep the source position exactly one source-axis distance upstream of
  isocenter, make its direction point to isocenter, and make `tr3` map the
  accelerator's local beam axis onto that same direction.
- Add independent synthetic patient-coordinate anchor tests at gantry 0, 90,
  180, and 270 degrees and representative nonzero oblique angles.
- Prove gantry 0 output remains unchanged and prove source position,
  direction, `tr3`, and the isocenter central axis remain mutually consistent
  for every tested angle.
- Version or otherwise bind the corrected gantry-geometry contract so PHITS
  results produced with the old nonzero-angle convention are not accepted as
  corrected transport evidence. Affected cases require PHITS and downstream
  recalculation.
- Keep the accepted PHITS-to-DICOM LPS mapping and final RTDOSE voxel mapping
  unchanged. Do not attempt repair by mirroring only the final DICOM.
- Supersede historical renderer-parity expectations only where they conflict
  with the independent IEC/DICOM patient-coordinate anchors; do not treat the
  former gantry-90 downstream comparison as validation of the current combined
  pipeline.
- Keep PLAN-versus-fraction dose semantics, physical dose values, MU,
  normalization, public dose factors, field apertures, source spectrum, and
  other machine physics outside this change.
- Use only synthetic repository evidence for automated validation. Real PHITS,
  Sumtally, phits2dicom, GPR, or real DICOM validation remains a separate
  external action requiring explicit human approval.

## Impact

- New capability: `iec-gantry-geometry`
- Modified capability: `portable-workspace-recovery`
- Likely affected runtime after separate approval:
  `src/dicomxphits/prepare_ct_calibration.py` and the geometry provenance used
  to reject stale nonzero-gantry PHITS results
- Likely affected tests: generated source coordinates and direction,
  accelerator transform matrices, patient-coordinate cardinal and oblique
  anchors, gantry-zero compatibility, and stale-workspace rejection
- Affected documentation: public PHITS gantry-coordinate contract and the
  requirement to recalculate affected transport
- Unchanged boundaries: final RTDOSE axis mapping and affine, DICOM identity,
  tally-grid placement, stored and physical dose values, PLAN/fraction
  semantics, MU and normalization, public source spectrum and aperture model,
  external comparison criteria, and clinical claims

## Approval Status

Pending human approval. This proposal authorizes no runtime or test change and
no external execution. Implementation must not begin until the primary user
explicitly approves this bounded proposal.
