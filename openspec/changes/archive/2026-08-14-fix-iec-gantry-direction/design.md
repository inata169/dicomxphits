# Design: IEC-Consistent Gantry Direction

## Context

The public HFS, couch-zero workflow uses PHITS fixed coordinates in
centimetres, anchored at the RT Plan isocenter, and the accepted mapping to
DICOM LPS patient coordinates in millimetres:

```text
M(x, y, z) = 10 * (-x, z, y)
P_DICOM(p) = I_DICOM + M(p)
```

Let `g` be the DICOM Gantry Angle in radians and let `S` be the positive
source-axis distance in centimetres. The local accelerator model has its
source at `(0, 0, -S)` and its beam directed along local `+Z`.

## Root Cause Derivation

### Current source and patient-coordinate result

The runtime currently constructs:

```text
d_current_PHITS = (-sin(g), 0, cos(g))
q_current_PHITS = -S * d_current_PHITS
                = (S sin(g), 0, -S cos(g))
```

The ray is internally centered because
`q_current_PHITS + S * d_current_PHITS = (0, 0, 0)`. Applying the accepted
PHITS-to-DICOM vector mapping gives:

```text
d_current_LPS = (+sin(g), cos(g), 0)
q_current_LPS = 10 * (-S sin(g), -S cos(g), 0)
```

The current `tr3` matrix has the same sign convention. Under the PHITS
transform convention used by the generated `trcl=3` accelerator universe, it
maps local `+Z` to `d_current_PHITS` and local `(0, 0, -S)` to
`q_current_PHITS`. Source and accelerator are therefore mutually aligned, but
the aligned pair rotates opposite to IEC gantry angle in patient coordinates.

### Historical compatibility evidence

The authorized read-only research OpenSpec contains two facts that must be
kept distinct from the current coordinate proof:

- the `-sin(g)` Source/transform pair was deliberately preserved after a prior
  gantry-90 transport and downstream comparison; and
- the historical maintained RTDOSE array permutation was
  `source.transpose(1, 0, 2)`, with no final IEC-X-to-DICOM-X reversal.

The current public repository subsequently made that reversal explicit with
`source.transpose(1, 0, 2)[:, :, ::-1]`. Thus the earlier end-to-end comparison
tested a different combined coordinate pipeline and cannot settle the sign of
the current one. The evidence supports, but does not by itself prove, the
migration explanation that `-sin(g)` was an old downstream-parity compensation
which is now applied in addition to the final X reversal. In contrast, the
current mismatch is proven directly by composing the runtime vectors with the
accepted public mapping `M`.

This proposal therefore uses patient-coordinate anchors as the oracle rather
than either legacy renderer parity or the earlier downstream comparison. It
does not reinterpret, delete, or claim to reproduce the historical evidence.

### Required IEC/DICOM result

IEC 61217 defines gantry zero with the source along positive IEC Fixed Z and
gantry 90 degrees with the source along positive IEC Fixed X. For the public
HFS, couch-zero mapping, the required patient-coordinate source and beam-axis
vectors are:

```text
q_required_LPS = 10 * (S sin(g), -S cos(g), 0)
d_required_LPS = (-sin(g), cos(g), 0)
```

The corresponding PHITS vectors are:

```text
q_required_PHITS = (-S sin(g), 0, -S cos(g))
d_required_PHITS = (+sin(g), 0, cos(g))
```

They preserve the central-axis invariant
`q_required_PHITS + S * d_required_PHITS = 0`.

## Patient-Coordinate Anchors

For the built-in `S = 100 cm` source distance, all source offsets below are
relative to the DICOM isocenter and are shown in millimetres.

| Gantry | Required source LPS offset | Required beam direction LPS |
| ---: | ---: | ---: |
| 0 degrees | `(0, -1000, 0)` | `(0, +1, 0)` |
| 90 degrees | `(+1000, 0, 0)` | `(-1, 0, 0)` |
| 180 degrees | `(0, +1000, 0)` | `(0, -1, 0)` |
| 270 degrees | `(-1000, 0, 0)` | `(+1, 0, 0)` |
| 45 degrees | `(+1000/sqrt(2), -1000/sqrt(2), 0)` | `(-1/sqrt(2), +1/sqrt(2), 0)` |
| 315 degrees | `(-1000/sqrt(2), -1000/sqrt(2), 0)` | `(+1/sqrt(2), +1/sqrt(2), 0)` |

The current implementation matches the 0- and 180-degree rows but swaps the
lateral sign in the other rows.

## Decisions

### 1. Correct source and accelerator rotation together

The source direction and source center must use the required PHITS vectors
above. The `tr3` sine terms must be changed as one atomic geometry correction
so the transform maps local `+Z` to `d_required_PHITS` and the local upstream
source point to `q_required_PHITS`.

A partial source-only or transform-only correction would make particles and
beam-shaping geometry inconsistent and is not acceptable.

### 2. Test physical relationships, not rendered substrings alone

Synthetic tests will independently calculate the expected PHITS and DICOM
vectors. For cardinal and oblique angles they must prove:

- the source is `S` upstream from isocenter;
- the source direction is a unit vector toward isocenter;
- the source ray intersects isocenter;
- `tr3` maps the local beam axis and upstream source point onto the same
  global vectors; and
- the accepted `M(x, y, z)` mapping produces the required DICOM LPS anchors.

Rendered-input assertions may remain as serialization checks, but they are not
the coordinate oracle.

### 3. Preserve gantry zero exactly

Because `sin(0) = 0`, the correction must leave gantry-zero source position,
direction, accelerator transform, source spectrum, aperture geometry, and
other rendered runtime content unchanged.

### 4. Invalidate affected prior transport evidence

The corrected geometry must have explicit provenance. A nonzero-gantry PHITS
result produced by the old convention traversed the CT voxel phantom from the
wrong side and cannot be repaired downstream. Such evidence must fail closed
and require regenerated segment inputs, PHITS execution, Sumtally, and RTDOSE.

An all-zero-gantry workspace may remain reusable only if repository evidence
unambiguously proves that its rendered transport geometry is identical under
the corrected contract. Ambiguous or mixed-angle legacy evidence fails closed.

### 5. Keep RTDOSE placement and dose semantics unchanged

The accepted mapping `P_DICOM = I + 10 * (-x, z, y)` remains the patient-space
meaning of the PHITS tally. The final RTDOSE array and affine correction are
not an alternative place to reverse the transported distribution.

PLAN-versus-fraction dose remains a separate dose-semantics decision. This
change does not alter stored values, dose scaling, MU, normalization, source
calibration, or the phits2dicom factor.

### 6. Separate synthetic validation from external validation

Repository validation uses only mathematical and synthetic fixtures. After an
approved implementation, any real PHITS recalculation and comparison must be
separately and explicitly approved by the human and kept outside the
repository's protected-data boundary.

## Validation Strategy

1. Unit-test the independent vector and transform relationships at 0, 90, 180,
   270, 45, and 315 degrees.
2. Render synthetic segment inputs and verify their source and `tr3` values
   against independently calculated anchors.
3. Prove gantry-zero rendered geometry is unchanged.
4. Prove old nonzero or ambiguous geometry provenance cannot be reused as
   corrected PHITS evidence.
5. Run focused synthetic geometry and recovery tests, then the complete public
   validation suite and strict OpenSpec validation.
6. Do not run real PHITS, Sumtally, phits2dicom, GPR, or real DICOM without a
   later explicit human approval.

## Risks and Mitigations

- **Only the source sign is corrected.** Require transform-vector equality in
  tests and change the source and `tr3` atomically.
- **String tests preserve another coherent but wrong convention.** Use DICOM
  LPS patient-coordinate anchors as the independent oracle.
- **Gantry zero masks the defect.** Require 90/270-degree and oblique tests.
- **Old transport is reused after the runtime fix.** Bind a corrected geometry
  version and fail closed for affected or ambiguous prior evidence.
- **A DICOM-only mirror appears to improve comparison.** Keep final RTDOSE
  mapping unchanged and require PHITS recalculation for affected cases.
- **Dose scaling work is accidentally bundled.** Keep PLAN/fraction, MU,
  normalization, factors, and stored values explicit non-goals.

## Rollback

Before acceptance, rollback is a normal revert of the focused runtime,
provenance, tests, and documentation changes. It must not rewrite external
workspaces or reinterpret old nonzero-gantry PHITS results as corrected.
