# RTDOSE Full-Plan Reference Design

## Context

The accepted public workflow constructs a `full_plan` segment manifest, runs
all active segments, and aggregates them into one all-active-segments Sumtally
output. `phits2dicom` needs a user-supplied RT Dose template, but fields in that
template do not prove which plan produced the calculated dose. The current
adapter corrects absolute-dose labeling and coordinates after conversion while
leaving the template's dose summation and referenced-plan hierarchy untouched.

The guided GUI already retains the frozen RT Plan selected by the accepted
CT2PHITS handoff. The 3D-CRT workspace manifest also records the plan UID,
workflow mode, included segments, and MU coverage. These are the appropriate
inputs for a fail-closed semantic check; the template is not.

## Goals and Non-Goals

### Goals

- Make the final RT Dose identify the frozen RT Plan that actually generated
  the workspace.
- Describe the all-active-segments result as a plan-level dose only when the
  adapter can prove complete plan coverage.
- Reject stale or partial template references before reporting RTDOSE success.
- Allow existing segment PHITS outputs to be reused without segment
  recalculation.
- Preserve dose values, dose units, geometry, coordinates, and normalization.

### Non-Goals

- Change PHITS, Sumtally, calibration, MU, dose factors, or pixel values.
- Add per-beam, per-fraction, selected-beam, IMRT, or VMAT RT Dose output.
- Infer missing plan coverage or repair an incomplete segment manifest.
- Claim clinical validity, commissioning, patient QA, or vendor compatibility.
- Execute real DICOM or licensed external tools during automated validation.

## Decisions

### Treat the Frozen RT Plan as Authoritative

RTDOSE Prepare will require an explicit frozen RT Plan input. The GUI will pass
the same visible path already used for 3D-CRT workspace preparation. The
adapter will validate RT Plan modality/SOP identity and compare its SOP Instance
UID with the manifest's recorded plan UID. The prepare summary will carry only
the identity and coverage evidence needed by RTDOSE Run.

This makes the template an image-layout input rather than an authority for dose
provenance. It also supports already calculated workspaces: the expensive PHITS
and Sumtally stages do not need to be repeated.

### Prove Full-Plan Coverage Before Labeling PLAN

The adapter will require `workflow_mode = full_plan` and compare the active
manifest delivery against the treatment beams referenced by the frozen RT
Plan's fraction groups. Missing, extra, skipped, or ambiguous plan delivery will
fail before conversion. Existing strict manifest and MU checks remain in force.

Sumtally Generate records a canonical SHA-256 of the complete segment manifest.
Sumtally Run validates and carries the same digest, and RTDOSE Prepare requires
the Generate, Run, and current-manifest values to match. This prevents a dose
calculated from one manifest from being relabeled for a later replacement
manifest. A legacy workspace without this evidence regenerates and reruns only
Sumtally before RTDOSE conversion; its segment PHITS outputs remain reusable.

Generate also records SHA-256 values for the generated PHITS wrapper and
`sumtally.inp`. Run accepts only the recorded wrapper path, validates both
files immediately before external execution, and carries their digests into
the execution evidence consumed by RTDOSE. This prevents a custom, copied, or
edited Sumtally input from inheriting unrelated manifest evidence.

Run snapshots the expected Sumtally output before and after external execution,
requires that invocation to update it, and records the resulting SHA-256.
RTDOSE Prepare verifies the Run digest before applying its required IPP title
patch, then records the patched digest for RTDOSE Run to verify immediately
before conversion.

When that gate passes, the all-active-segments result represents the entire RT
Plan delivery and will use `DoseSummationType = PLAN`. This change does not add
support for generating a BEAM or FRACTION dose.

### Synchronize Converted Output, Then Validate the Final File

After `phits2dicom` creates a new output, the adapter will replace the raw
output's dose-summation metadata with:

- `DoseSummationType = PLAN`;
- one `ReferencedRTPlanSequence` item whose SOP Class and SOP Instance UIDs
  match the frozen RT Plan; and
- no template-derived `ReferencedFractionGroupSequence` or
  `ReferencedBeamSequence` describing a partial delivery.

Coordinate correction will then carry the synchronized metadata into the
documented `.fixed.dcm` output. RTDOSE Run will reopen that final file and
verify the plan reference, summation type, Frame of Reference, absolute dose
units, and existing stored-value preservation invariant before reporting
success.

### Keep DICOM Value and Geometry Changes Out of Scope

The synchronizer will not modify `PixelData`, `DoseGridScaling`, `DoseUnits`,
grid dimensions, image orientation/position, frame offsets, or the Frame of
Reference. Tests will snapshot those attributes and physical pixel values
around the metadata update.

## Risks and Mitigations

- A legacy workspace may not contain enough coverage evidence. Fail with a
  focused preparation error and require workspace preparation to be rerun; do
  not guess.
- A template may contain deeply nested stale references. Replace the complete
  plan-reference hierarchy rather than editing one nested UID.
- A plan can contain treatment and non-treatment beams. Derive required delivery
  from the RT Plan fraction-group references and the existing public manifest
  rules rather than counting every Beam Sequence item blindly.
- Metadata rewriting could alter dose or geometry. Assert pixel bytes/values,
  scaling, units, and coordinate invariants with synthetic datasets.

## Validation Strategy

- Use synthetic RT Plans, synthetic RT Dose files, temporary workspaces, and a
  fake `phits2dicom` runner only.
- Test replacement of a stale BEAM template hierarchy with the exact synthetic
  frozen-plan reference.
- Test failure for wrong plan UID, non-full-plan manifests, incomplete beam
  coverage, and invalid final output references.
- Test preservation of stored pixels, physical dose values, scaling, units,
  Frame of Reference, and coordinate-correction invariants.
- Run focused tests, the full public suite, public-tree audit, Git checks, and
  strict OpenSpec validation.

## Migration Plan

The RTDOSE Prepare CLI gains a required frozen RT Plan input, and the guided GUI
supplies its existing frozen RT Plan field. A workspace with manifest-digest
evidence reruns RTDOSE Prepare and RTDOSE Run only. A legacy workspace first
reruns Sumtally Generate and Sumtally Run. In both cases the expensive segment
PHITS calculations remain reusable.
