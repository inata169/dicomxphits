# Design: Prevent CT and Accelerator Geometry Overlap

## Context

The generated PHITS geometry contains a CT wrapper filled by the CT voxel
universe and a separately transformed accelerator cell. Their current cell
definitions do not establish an exclusion relationship. If their spatial
regions intersect, material ownership becomes ambiguous and PHITS may recover
particles across geometry boundaries. Because the execution adapter currently
uses process return code and expected-output existence as its primary success
test, a recovered calculation can be promoted downstream.

The intersection is not determined by transverse FOV alone. A nominally large
but centred CT may remain downstream of the head, while a smaller volume with a
shifted isocentre or a rotated beam can project upstream into it. The supported
solution therefore has to work in transformed three-dimensional geometry and
cannot be a fixed `650 mm` threshold.

The existing public absolute-dose factor was accepted against a machine-config
digest and spectrum digest. It does not identify the CT/accelerator CSG
topology. Correcting that topology requires explicit factor provenance even
when a particular calibration phantom is geometrically disjoint and its
physical transport is expected to be unchanged.

## Goals

- Ensure exactly one intended owner for every point in the CT-wrapper and
  accelerator-envelope union.
- Preserve CT voxels and air outside the accelerator envelope.
- Detect and reject PHITS-reported geometry recovery or overlap.
- Invalidate pre-fix transported results through one current v5 contract.
- Avoid unnecessary numerical recalibration when reviewed evidence proves the
  reference calibration transport is unchanged.
- Keep automated repository validation synthetic and deterministic.

## Non-Goals

- Changing SAD/SSD interpretation or treatment-plan setup.
- Limiting or cropping CT FOV, moving the isocentre, or rewriting CT geometry.
- Narrowing the circumscribed source cone or changing jaw/MLC apertures.
- Changing accelerator dimensions, materials, spectrum, cutoffs, tallies, MU,
  Sumtally normalization, or RTDOSE semantics.
- Claiming that corrected overlapping calculations preserve their old dose.
- Clinical commissioning, vendor validation, or patient-specific QA.
- Executing external scientific tools or loading real workflow data as part of
  repository automation.

## Decisions

### 1. Compose cells with accelerator precedence

The CT-filled wrapper will exclude the complete transformed accelerator cell.
For the current renderer, the leading implementation candidate is the PHITS
cell-complement form:

```text
1201 0 -98 #2 fill=4000
```

where cell `2` is the accelerator envelope. PHITS 3.36 defines `#` as the cell
complement operator, defines `TRCL` as the coordinate transform applied to a
cell, and includes an official example in which one cell complements other
cells carrying `TRCL`. The implementation therefore references the complete
cell `2`, not a duplicate list of its untransformed surfaces. Tests prove the
reference remains attached to the transformed accelerator envelope for every
supported angle.

Accelerator precedence applies only to the intersection. The CT wrapper keeps
its current bounds, fill universe, voxel lattice, coordinate mapping, and
material assignment everywhere else. The outside-air construction remains
unchanged except where needed to preserve a single, unambiguous owner.

This general composition is preferred to a FOV cutoff because it is based on
the actual regions and remains valid for centred, displaced, and rotated
volumes.

### 2. Preserve the beam model and aperture construction

The change will not modify the source cone, because its current role is to
circumscribe the supported jaw/MLC aperture rather than define the final field
edge. It will not alter SAD, source position, accelerator transform, jaw or MLC
positions, materials, transport parameters, tally geometry, or dose/MU
normalization.

For a geometry with an empty CT/accelerator intersection, old and corrected
CSG must describe the same material regions traversed by all histories. Tests
will compare parsed geometry and sampled region ownership independently of
rendered-text differences. Overlapping geometry is not subject to a
byte-equivalence or dose-equivalence promise.

### 3. Validate the complete transformed relationship

Preparation and tests will reason over the full CT wrapper and transformed
accelerator envelope. They will not branch on a single nominal FOV or one
patient axis. Synthetic cases include:

- a compact, centred, non-overlapping volume;
- a large volume that remains non-overlapping;
- a displaced volume that overlaps despite an otherwise ordinary FOV;
- nonzero gantry angles and representative collimator angles; and
- boundary-touching and small-overlap cases.

Boundary contact must be represented without a positive-volume double owner.
Numerical tolerances, if required by a geometric preflight, are validation
tolerances only and must not move a PHITS surface or create an artificial gap.

### 4. Make geometry-clean PHITS diagnostics part of success

The segment adapter will parse the staged `phits.out` companion before copying
or accepting the segment result. Success requires:

- process return code zero;
- all currently required output files;
- one recognized, unambiguous geometry-diagnostic summary for the supported
  PHITS output format; and
- zero reported `Number of lost particles`, `Number of geometry recovering`,
  and `Number of unrecovered errors` counts from the PHITS Category-I summary.

A missing or ambiguous required diagnostic summary fails closed. A nonzero
count fails even if a tally exists. The execution summary records the parsed
counts and diagnostic status, without promoting invalid results to Sumtally.
Parsing will target documented summary fields and bounded numeric values; it
will not fail merely because an unrelated log line contains a word such as
`overlap`.

Synthetic representative `phits.out` fixtures and fake runners will cover
clean, nonzero, missing, malformed, duplicate, and contradictory summaries.
Compatibility with the supported real PHITS output must be confirmed only
under separate external-execution approval.

### 5. Advance one combined geometry contract to v5

The current combined contract will advance from
`dicomxphits_iec_gantry_mlcx_collimator_geometry_v4` to a v5 identity that also
states CT/accelerator topology safety. Every newly prepared segment and
workspace records v5 consistently.

Any v4, v3, older, missing, mixed, or ambiguous provenance is stale for v5
PHITS reuse. This applies even to zero-angle or analytically non-overlapping
workspaces because old PHITS output lacks both the corrected topology and the
mandatory geometry-clean diagnostic evidence. Recovery requires fresh v5
preparation and PHITS, Sumtally, and RTDOSE execution; final-DICOM rewriting is
not a repair.

### 6. Extend absolute-dose calibration identity without presuming a new factor

The approved factor identity will include the current transport-topology
contract in addition to machine configuration, spectrum, and calibration
evidence. A factor whose evidence does not bind v5 is stale for new absolute
dose preparation.

This proposal does not mandate a new numerical 10 x 10 cm2 calibration. The
existing numerical factor may be reaccepted for v5 if separately reviewed
evidence establishes all of the following:

1. the reference calibration CT and accelerator regions are disjoint;
2. the corrected complement does not change material ownership along any
   transported history in that reference geometry;
3. source, aperture, physics, tally, MU, and normalization inputs are
   unchanged; and
4. any externally generated comparison evidence was produced only after
   explicit authorization and is recorded without protected data.

If those conditions are not accepted, the software must not guess that the
factor is unchanged. It keeps absolute-dose preparation fail-closed until a
human accepts suitable v5 calibration evidence or a newly derived factor.

On 2026-08-31, the primary user reviewed the repository-safe non-overlap and
transport-equivalence evidence and explicitly reaccepted the unchanged
`8.7608E+11 source/MU` factor for v5. This decision did not authorize or rely
on an external PHITS dose comparison. The implementation records the original
factor acceptance and this topology reacceptance as separate provenance.

### 7. Keep real-data and external-tool validation outside automation

Repository tests use synthetic DICOM-like fixtures, analytical transforms,
rendered-input inspection, representative bounded PHITS text, and fake or mock
runners. They do not load facility data or execute PHITS, RT-PHITS, Sumtally,
phits2dicom, or GPR.

A later real-tool smoke test should compare one known non-overlapping
calibration geometry and one previously overlapping large-volume geometry, but
only after a separate explicit human approval. The former tests invariance;
the latter confirms the intended correction and is not expected to reproduce
the old dose.

## Alternatives Rejected

- **Reject or crop CTs above a fixed FOV.** FOV alone does not determine the
  transformed intersection and cropping changes the represented patient or
  phantom volume.
- **Move the CT or accelerator.** This changes DICOM or treatment geometry and
  masks the ownership defect.
- **Narrow the source cone.** This can clip valid apertures and does not repair
  overlapping material cells.
- **Accept PHITS return code zero as success.** Geometry recovery can coexist
  with a zero return code and an output file.
- **Keep v4 results when angle or FOV appears safe.** Old transport lacks v5
  topology and diagnostic evidence; conditional reuse would be hard to audit.
- **Force a new calibration factor immediately.** A non-overlapping reference
  geometry may be transport-equivalent. Reacceptance should depend on evidence,
  not an assumed numerical change or assumed invariance.

## Validation Strategy

1. Assert emitted CT-wrapper CSG excludes the complete transformed accelerator
   cell and preserves all other cell definitions.
2. Sample synthetic region ownership for centred, displaced, large,
   boundary-touching, and rotated cases.
3. Prove non-overlapping old/new geometry is semantically equivalent and that
   overlapping old geometry is rejected by the new ownership invariant.
4. Exercise geometry-diagnostic parsing and segment failure with synthetic
   clean, nonzero, missing, malformed, and contradictory `phits.out` content.
5. Prove every v4-or-older workspace is stale for v5 reuse and that complete
   recalculation is required without angle/FOV exceptions.
6. Prove absolute-dose preparation rejects calibration evidence not bound to
   v5 and accepts only an explicitly approved v5 binding.
7. Run focused tests and the full public validation suite without real data or
   external scientific execution.

## Risks and Mitigations

- **Cell complement is applied in the wrong coordinate system.** Verify the
  referenced transformed cell and use independent sampled-point assertions.
- **A complement creates a void or double-owned boundary.** Cover touching and
  epsilon-separated synthetic points without moving physical surfaces.
- **Diagnostic parsing is version-fragile.** Support only reviewed formats,
  require an unambiguous summary, record parsed evidence, and fail closed.
- **Old results are mixed with corrected geometry.** Advance one combined v5
  contract and reject all earlier provenance for transport reuse.
- **A valid calibration factor is discarded unnecessarily.** Provide an
  evidence-based reacceptance route for proven non-overlapping calibration
  geometry while keeping the numeric value under human control.
- **A corrected overlapping case is described as unchanged.** State explicitly
  that its field and dose may change and require fresh transport.

## Rollback

Before implementation acceptance, rollback is deletion of this active proposal
only. After implementation, rollback requires reverting the renderer,
diagnostic gate, v5 provenance, calibration binding, tests, and documentation
together. A rollback must not relabel v5 results as v4 or restore reuse of
transport evidence rejected for geometry errors.

## Official PHITS References

- [PHITS 3.36 Cell section](https://phits.jaea.go.jp/manual/PHITS-en/chapters/sections/cell/cell.html)
  for intersection, union, cell complement, and `TRCL` semantics.
- [PHITS 3.36 Summary output](https://phits.jaea.go.jp/manual/PHITS-en/chapters/input-output.html#summary-output-file-phits-out)
  for the three Category-I geometry counters.
