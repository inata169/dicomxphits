# Design: Evidence-Bound RTDOSE Isocenter Translation

## Context

The public voxel-phantom workflow establishes a relationship between three
spaces:

1. DICOM patient coordinates from the frozen RT Plan and CT series.
2. PHITS fixed coordinates, with the plan isocenter used as the treatment
   geometry anchor.
3. The sampled PHITS tally mesh, whose bin centers need not share the CT
   dimensions or the CT first-slice origin.

The current RTDOSE adapter patches a CT reference slice position into the dose
title before `phits2dicom`. The converter emits an axial RTDOSE using that
position, and the maintained coordinate correction transposes the voxel array
while preserving the converter output's physical center. This correctly
preserves a supplied affine, but it cannot correct an affine whose translation
was never derived from the PHITS tally and RT Plan.

Prior project-authored research records also show that a target-center
relocation was historically an explicit coordinate-correction input for a
bounded reproduction. That evidence supports restoring an attributable target
placement mechanism, but it does not justify hard-coding one phantom-specific
center as a public default.

## Goals

- Make the frozen RT Plan isocenter and actual PHITS tally grid authoritative
  inputs to final RTDOSE patient-coordinate placement.
- Prove the complete output voxel affine, not only orientation, spacing, or
  preservation of a converter-provided center.
- Separate converter-compatibility metadata from accepted final geometry
  evidence.
- Fail closed before a wrong translation can be presented as Completed.
- Preserve dose values and all unrelated physics and DICOM semantics.

## Non-Goals

- Tuning a translation to maximize GPR.
- Changing GPR-comparing, its criteria, interpolation, or shift search.
- Changing Sumtally weights, MU normalization, PHITS2DICOM dose factor, or
  absolute-dose calibration.
- Changing PHITS tally bounds, source, CT voxel construction, accelerator
  geometry, or particle transport.
- Supporting arbitrary patient orientation or oblique RTDOSE geometry beyond
  the documented public HFS axial contract.
- Embedding external DICOM, calculation output, identifiers, or personal paths
  in the repository.

## Decisions

### 1. Model coordinate placement as a voxel affine

The accepted output geometry is defined by the patient-coordinate location of
voxel centers. For every supported output index, the implementation must be
able to relate the voxel to one PHITS tally-bin center and then map that point
through the reviewed PHITS/IEC-to-DICOM transform anchored by the frozen RT
Plan isocenter.

The implementation must use named quantities for:

- frozen-plan isocenter in DICOM millimetres;
- tally axis bounds, bin counts, and bin-center spacing in PHITS centimetres;
- PHITS/IEC-to-DICOM axis mapping and sign convention;
- source and output array-axis permutations; and
- DICOM row, column, and frame direction vectors.

It must not infer translation from array dimensions alone or from a CT slice
position.

The approved public affine uses each recorded PHITS tally minimum and maximum
as bin edges. For axis `a` with finite edges `a_min < a_max` in centimetres
and positive integer bin count `n_a`, the spacing and bin centres are:

```text
delta_a = (a_max - a_min) / n_a
a_i     = a_min + (i + 0.5) * delta_a
```

Let `I = (I_x, I_y, I_z)` be the frozen-plan isocenter in DICOM patient
millimetres and let `p = (x, y, z)` be a PHITS/IEC fixed-coordinate tally-bin
centre in centimetres. The approved PHITS/IEC-to-DICOM patient mapping is:

```text
P_DICOM_mm(p) = I + 10 * (-x, z, y)
```

For an output array indexed as `(frame, row, column) = (f, r, c)`, the exact
bin association is:

```text
x = x_(n_x - 1 - c)
y = y_f
z = z_r
V(f, r, c) = P_DICOM_mm(x, y, z)
```

The resulting supported axial DICOM geometry has shape `(n_y, n_z, n_x)`,
`ImageOrientationPatient = [1, 0, 0, 0, 1, 0]`, `PixelSpacing =
[10 * delta_z, 10 * delta_x]`, relative `GridFrameOffsetVector[f] =
10 * f * delta_y`, and `ImagePositionPatient = V(0, 0, 0)`. The reversed
PHITS `x` index is the approved negative IEC-X to positive DICOM-X sign; the
`y` and `z` associations implement the approved IEC-to-DICOM axis swap.

Final affine validation uses zero relative tolerance and an absolute tolerance
of `1e-6` millimetres for each DICOM Cartesian component. The coordinate
summary records the maximum absolute component residual across the validated
first, centre, edge, and final voxels.

### 2. Treat the CT reference position as converter compatibility only

If `phits2dicom` requires an `ImagePositionPatient` title and a CT reference,
the existing patch may remain as a converter input adapter. Its summary must
state that the value is not authoritative final dose placement.

After conversion, the coordinate correction derives the final output affine
from reviewed geometry evidence. Preserving the raw converter center is valid
only when that center independently matches the derived target within the
specified tolerance.

The compatibility adapter must not patch accepted Sumtally or PHITS results in
place. It stages private converter copies and records source hashes before and
after Prepare. Run revalidates both the unchanged sources and staged inputs.

For workspaces processed by the historical in-place IPP title patch, a bounded
migration may reconstruct the pre-patch Sumtally bytes from the hash-bound
segment T-Deposit title sequence. Recovery is accepted only when one
deterministic candidate, including the historical LF/CRLF normalization
possibilities, exactly reproduces the Sumtally Run SHA-256. The recovered bytes
are written only to the private staged copy. Failure to reproduce that digest
is an integrity failure, not a request to weaken or replace the evidence.


### 3. Bind geometry evidence across stages

Workspace preparation already records the frozen RT Plan and CT coordinate
relationship. The implementation must additionally bind the exact tally mesh
used by every accepted segment and Sumtally result. RTDOSE Prepare records the
hashes and normalized geometry values consumed by the placement calculation;
RTDOSE Run revalidates them before conversion and again before accepting the
final file.

If active segment tallies do not share one supported mesh and coordinate
contract, Sumtally or RTDOSE acceptance fails rather than selecting one mesh by
convenience.

### 4. Keep explicit target relocation attributable

The normal path uses the approved plan-and-tally affine rule. A target override
is allowed only when all three patient-coordinate values are finite and a
non-empty reason is supplied. The summary records both the rule-derived target
and the requested target, the translation between them, and the reason.

No historical phantom-specific target is a package default. A bounded manual
reproduction may reuse previously reviewed scalar coordinate evidence only
after separate human approval and without adding its DICOM or result files to
the repository.

### 5. Validate final placement before Completed

RTDOSE Run reopens the corrected output and independently reconstructs the
first, center, edge, and final voxel coordinates from DICOM tags. It compares
them with the expected mapped tally coordinates and records the maximum
patient-coordinate residual.

Missing evidence, unsupported orientation, stale hashes, a mismatched affine,
or a residual above the approved numerical tolerance is a stage failure. The
GUI uses that failed stage result and must not show RTDOSE Completed.

### 6. Preserve dose and non-coordinate semantics

The coordinate operation may permute stored voxel indices and update only the
coordinate and dimension fields required by that mapping. It must not
numerically modify stored dose values or `DoseGridScaling`, and it must not
change units, MU, normalization, dose factor, plan references, Frame of
Reference, or PHITS/Sumtally evidence.

## Approved Coordinate Decision

On 2026-08-04, the qualified human approved documenting the exact public
coordinate contract above: tally minima and maxima are bin edges, the inverse
fixed-coordinate mapping is `I + 10 * (-x, z, y)`, the output index association
is `(y, z, reversed x)`, and the componentwise absolute tolerance is `1e-6`
millimetres with zero relative tolerance. The human subsequently approved the
full repository implementation on a dedicated feature branch, including
runtime code, synthetic/mock tests, and documentation. The human later
separately approved coordinate-only RTDOSE Prepare/Run and research comparison
for one designated non-patient phantom while reusing its existing PHITS and
Sumtally results. PHITS/Sumtally recalculation, Factor/MU/normalization work,
additional external data, and promotion or archival remain outside that
limited approval.

The contract is derived from the existing reviewed DICOM-to-IEC transform and
independently bound plan-and-tally geometry. It does not encode a target chosen
to improve GPR and does not define a phantom-specific target centre.

## Validation Strategy

1. Add synthetic RT Plan and tally provenance with a nonzero isocenter,
   asymmetric bounds, unequal dimensions, and unequal axis spacings.
2. Calculate expected first, center, edge, and final voxel positions
   independently of the implementation.
3. Prove exact voxel permutation and DICOM `PixelSpacing`,
   `GridFrameOffsetVector`, `ImageOrientationPatient`, and
   `ImagePositionPatient` values.
4. Prove the CT reference position cannot become final placement evidence.
5. Prove explicit override validation and provenance without defining a
   package default.
6. Prove missing, inconsistent, or stale plan/tally/transform evidence fails
   before Completed.
7. Prove stored values, scaling, units, MU/normalization evidence, plan
   references, and Frame of Reference remain unchanged.
8. Run focused synthetic tests, then the complete public validation suite.
9. Reprocess an existing designated non-patient phantom only after separate
   approval; reuse existing PHITS and Sumtally results when the approved
   validation plan permits it.

## Risks and Mitigations

- **A centered synthetic fixture hides a translation bug.** Use nonzero
  isocenters and asymmetric tally bounds.
- **An isotropic grid hides an axis or spacing swap.** Use unequal dimensions
  and all three spacings.
- **A historical target becomes an undocumented universal constant.** Require
  explicit reasoned overrides and keep no package default.
- **Converter behavior is mistaken for coordinate authority.** Label CT input
  metadata as compatibility-only and validate the final affine independently.
- **Coordinate repair changes dose or normalization.** Hash and compare stored
  values and explicitly exclude dose-factor and MU work from this change.
- **A GPR improvement masks an incorrect transform.** Use independent affine
  expectations as the primary correctness oracle.

## Rollback

Before acceptance, rollback is a normal revert of the focused coordinate
implementation and specification delta. It must not modify existing external
workspaces, PHITS/Sumtally outputs, or historical evidence.
