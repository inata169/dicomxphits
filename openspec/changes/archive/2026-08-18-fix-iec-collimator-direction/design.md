# Design: IEC-Consistent Collimator Direction

## Context

The public head-first-supine, couch-zero workflow already defines a corrected
IEC gantry central axis and a fixed PHITS-to-DICOM LPS vector mapping:

```text
M(x, y, z) = (-x, z, y)
```

The DICOM `BeamLimitingDeviceAngle` is carried into each active segment as
`collimator_angle_deg`. The runtime then assigns that value to `c10` in the
PHITS accelerator `tr2` transform. No defect was found in reading, retaining,
or reporting the DICOM angle.

Let `c` be that DICOM angle in radians. At gantry zero and couch zero, define
the zero-collimator DICOM LPS beam-limiting axes as:

```text
X0_LPS = (+1, 0, 0)
Y0_LPS = (0, 0, +1)
```

The central beam direction is along patient `+Y`. The collimator rotates the
two beam-limiting axes about that central axis.

## Root Cause Derivation

With gantry and couch zero, the current `tr2` rotation block reduces to:

```text
T_current(c) = [[ cos(c),  sin(c), 0],
                [-sin(c),  cos(c), 0],
                [      0,       0, 1]]
```

Composed with the accepted PHITS-to-DICOM LPS mapping and the accelerator's
zero-angle local axes, the current patient-coordinate axes are:

```text
X_current_LPS(c) = ( cos(c), 0, -sin(c))
Y_current_LPS(c) = ( sin(c), 0,  cos(c))
```

They are the required axes evaluated at `-c`. The required positive DICOM
collimator rotation is:

```text
X_required_LPS(c) = ( cos(c), 0,  sin(c))
Y_required_LPS(c) = (-sin(c), 0,  cos(c))
```

Therefore the bounded correction is equivalent to applying `-c` only inside
the PHITS `tr2` collimator rotation. It does not negate the DICOM value stored
in the manifest, and it does not alter the gantry `tr3` transform.

## Patient-Coordinate Anchors

At fixed gantry zero and couch zero, synthetic tests will use these independent
DICOM LPS anchors:

| Collimator | Required MLCX axis | Required MLCY axis |
| ---: | ---: | ---: |
| 0 degrees | `(+1, 0, 0)` | `(0, 0, +1)` |
| 30 degrees | `(+sqrt(3)/2, 0, +1/2)` | `(-1/2, 0, +sqrt(3)/2)` |
| 90 degrees | `(0, 0, +1)` | `(-1, 0, 0)` |
| 180 degrees | `(-1, 0, 0)` | `(0, 0, -1)` |
| 270 degrees | `(0, 0, -1)` | `(+1, 0, 0)` |

The axes must remain unit length, mutually perpendicular, and perpendicular
to the unchanged central beam direction. A synthetic asymmetric aperture will
anchor feature orientation as well as the unlabeled axis pair, preventing a
coherent sign reversal from satisfying the test.

## Decisions

### 1. Correct only the PHITS application sign

The DICOM angle remains unchanged in state, interpolation, segment manifests,
summaries, and user-facing evidence. Only the collimator rotation applied in
`tr2` changes sign. This keeps the recorded plan meaning auditable and avoids
introducing an opposite-sign private angle convention.

### 2. Keep gantry, MLCX, and central-axis corrections intact

The current v3 contract already contains the corrected IEC gantry direction
and MLCX patient-axis interpretation. The collimator correction must compose
with those contracts without changing source position, source direction,
`tr3`, leaf values, jaw values, or isocenter.

### 3. Use independent patient-coordinate and feature anchors

Renderer substrings are serialization checks, not the coordinate oracle.
Tests will independently calculate the required DICOM LPS axes, transform
synthetic accelerator basis vectors, and compare an asymmetric feature's
orientation at positive and negative angles.

### 4. Advance combined geometry provenance

Newly prepared workspaces will carry
`dicomxphits_iec_gantry_mlcx_collimator_geometry_v4`. A v3 workspace was
prepared after the gantry and MLCX fixes but before the collimator fix. All v3
and older PHITS evidence will be rejected for reuse regardless of the recorded
collimator angle. Recovery requires newly prepared v4 segment inputs and PHITS
and downstream recalculation.

At exactly zero collimator angle, changing the rotation sign would produce the
same `tr2` geometry. This mathematical special case will not become a recovery
exception. Treating v4 as the single reuse boundary is easier for a human to
understand and audit, avoids angle-dependent trust in a version known to
contain the defect, and fails closed when legacy evidence is incomplete. No
final-DICOM-only operation can upgrade pre-v4 evidence to v4.

### 5. Preserve dose, DICOM-output, and physics contracts

This correction does not change the final tally-to-DICOM mapping, RTDOSE
affine, DICOM identifiers, dose scaling, physical dose, MU, normalization,
source spectrum, jaws, leaf values, or treatment scope. It changes only the
orientation in which existing beam-limiting geometry is transported.

### 6. Separate repository validation from external validation

Automated validation uses only mathematical fixtures, synthetic plans,
temporary workspaces, and fake or mock runners. External PHITS, Sumtally,
phits2dicom, GPR, DICOM, and calculation results are not read or copied into
the repository. Any post-implementation external comparison is performed by
the human under a separate explicit authorization.

## Rejected Alternatives

- **Negate the manifest angle.** This would make recorded provenance disagree
  with the DICOM RT Plan and hide the runtime convention error.
- **Mirror or rotate final RTDOSE.** This cannot correct particle transport
  through beam-limiting geometry with the wrong orientation.
- **Retain v3 only at collimator zero.** The transform is invariant at exactly
  zero, but an angle-dependent exception makes a known-bug version harder to
  understand and audit. The selected contract rejects all pre-v4 evidence.
- **Change MLC leaf or jaw values.** Their values are not the diagnosed source
  of this rotation-direction defect.

## Validation Strategy

1. Unit-test independent DICOM LPS MLCX and MLCY axes at collimator 0, 30, 90,
   180, and 270 degrees.
2. Prove axis length, orthogonality, central-axis perpendicularity, and
   positive-versus-negative asymmetric-feature orientation.
3. Prove collimator-zero rendered `tr2` geometry remains unchanged.
4. Prove DICOM angle values remain unchanged through state, interpolation,
   manifest, and reporting paths.
5. Prove v4 evidence is current and every v3, older, missing, or ambiguous
   geometry contract fails closed regardless of recorded collimator angle.
6. Run focused synthetic geometry and recovery tests, the complete public
   validation suite, and strict OpenSpec validation.
7. Do not run or load external PHITS, Sumtally, phits2dicom, GPR, real DICOM,
   or calculation results without later explicit human approval.

## Risks and Mitigations

- **The sign is changed twice.** Preserve manifest values and change only the
  `tr2` application, with end-to-end synthetic patient-axis anchors.
- **Axis labels can hide a reversed asymmetric shape.** Anchor a labeled
  asymmetric feature, not only an orthonormal basis.
- **Zero or 180 degrees mask the defect.** Require positive non-cardinal and
  quarter-turn anchors.
- **The gantry or MLCX fix regresses.** Retain their independent anchors and
  assert the source and `tr3` are unchanged.
- **Old transport is reused.** Bind v4 provenance and reject all pre-v4,
  missing, or ambiguous geometry evidence without an angle exception.
- **Dose or output mapping is bundled accidentally.** Treat those files and
  behaviors as explicit non-goals and inspect the implementation diff.

## Rollback

Before acceptance, rollback is a normal revert of the focused runtime,
provenance, tests, and documentation changes. It must not modify external
workspaces or reinterpret any pre-v4 PHITS result as corrected.
