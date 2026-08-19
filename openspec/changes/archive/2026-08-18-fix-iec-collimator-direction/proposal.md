# Fix IEC Collimator Direction

## Why

The generated PHITS accelerator `tr2` transform applies the DICOM Beam
Limiting Device Angle with the opposite rotation sign from the patient-axis
collimator convention expected by the public fixed-field workflow. At gantry
zero, the current positive-angle transform produces DICOM LPS beam-limiting
axes equivalent to applying the negative DICOM collimator angle.

Existing synthetic renderer tests preserve that same sign convention, so
they pass while asserting the reversed result. A human-operated external
non-patient comparison using a fixed gantry and asymmetric aperture has now
independently exposed the reversal. The external workspace and calculation
artifacts remain outside the repository and are not inputs to automated
validation or this proposal.

The manifest correctly preserves the DICOM collimator angle. The bounded
defect is the sign used when that angle is applied to PHITS accelerator
geometry. A final-RTDOSE mirror or relabel cannot repair particles already
transported through incorrectly rotated beam-limiting geometry.

## What Changes

- Preserve the DICOM Beam Limiting Device Angle in manifests, summaries, and
  public reporting without negating or relabeling it.
- Apply that angle to the PHITS accelerator `tr2` transform with the
  IEC/DICOM-consistent collimator rotation sign.
- Keep the corrected gantry source and `tr3` convention, the MLCX patient-axis
  convention, and the central beam axis unchanged.
- Add independent synthetic patient-coordinate anchors at collimator 0, 30,
  90, 180, and 270 degrees, including an asymmetric aperture whose orientation
  distinguishes positive from negative rotation.
- Prove collimator zero remains unchanged and prove the beam-limiting axes
  remain orthonormal and perpendicular to the central beam axis.
- Advance the combined beam-geometry provenance from the current v3 contract
  to a v4 contract that includes the corrected collimator direction.
- Reject all PHITS transport evidence produced under the v3 or older geometry
  contracts, regardless of recorded collimator angle. Recovery requires newly
  prepared v4 inputs followed by PHITS, Sumtally, and RTDOSE recalculation.
- Do not use an angle-dependent legacy exception. Although zero-angle `tr2`
  geometry is mathematically invariant to the sign correction, the complete
  v4 provenance contract is the single human-operable reuse boundary.
- Keep the final PHITS-to-DICOM LPS tally mapping and RTDOSE voxel mapping
  unchanged. Do not attempt a downstream-only mirror, affine rewrite, or
  DICOM relabel as repair.
- Keep gantry direction, MLC leaf positions, jaws, source spectrum, transport
  physics, dose values, MU, normalization, PLAN/fraction semantics, treatment
  scope, and clinical claims outside this change.
- Use only mathematical and synthetic repository evidence for automated
  validation. Any external PHITS or DICOM revalidation remains a separate
  human-controlled action requiring explicit approval.

## Impact

- Modified capability: `iec-gantry-geometry`
- Modified capability: `portable-workspace-recovery`
- Likely affected runtime after separate implementation approval:
  `src/dicomxphits/prepare_ct_calibration.py` and
  `src/dicomxphits/gantry_geometry.py`
- Likely affected tests: rendered accelerator transforms, independent DICOM
  LPS beam-limiting-axis anchors, asymmetric-aperture orientation, geometry
  provenance, and stale-workspace rejection
- Affected documentation after implementation: public beam-geometry contract
  and the recalculation boundary for affected legacy results
- Unchanged boundaries: stored DICOM angles, gantry source and `tr3`, MLC leaf
  values, final RTDOSE axes and affine, physical and stored dose, MU,
  normalization, source and aperture physics, public treatment scope, and
  external comparison criteria

## Approval Status

The primary user approved this bounded runtime and test implementation on
2026-08-18. The primary user subsequently reported completion of the separately
controlled external non-patient comparison on 2026-08-18. This archived
proposal does not duplicate or independently assess that comparison outcome;
the durable human-reported acceptance boundary remains in
`docs/project-status.md`. No external path, dataset identifier, image,
numerical result, DICOM, workspace, or calculation artifact was read or
imported into the repository.
