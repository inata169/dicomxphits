# Accept Missing Non-Treatment Beam Meterset

## Why

The existing full-plan workflow can represent a fraction-group-referenced
non-treatment beam as a skipped manifest segment with zero segment MU. Manifest
construction already records a missing `BeamMeterset` for such a beam as
warning-backed `0.0 MU`, allowing PHITS segment execution and Sumtally to
complete without including that beam in treatment dose. RTDOSE Prepare later
requires the same optional non-treatment `BeamMeterset` to be present and
finite, so it rejects evidence that the earlier stages accepted.

The stages need one fail-closed interpretation for this narrow compatibility
case. Treatment-eligible beams must retain the existing finite positive
`BeamMeterset` requirement.

## What Changes

- Treat an absent or empty `BeamMeterset` as effective `0.0 MU` only for a
  fraction-group-referenced beam whose `TreatmentDeliveryType` is not
  treatment-eligible.
- Require the canonical manifest to represent that beam only as skipped
  evidence with zero beam meterset and zero segment MU before RTDOSE provenance
  accepts the compatibility interpretation.
- Record which skipped non-treatment beam numbers used the missing-meterset
  compatibility interpretation.
- Continue to reject missing or non-positive treatment-beam metersets,
  non-empty malformed values, negative values, non-finite values, active
  non-treatment segments, and inconsistent manifest evidence.
- Keep the effective missing meterset at zero so it contributes nothing to
  PHITS, Sumtally weights, `sumfactor`, or dose normalization.

## Impact

- Affected capability: `rtdose-dicom-semantics`
- Affected runtime: frozen RT Plan full-plan evidence validation used by
  RTDOSE Prepare and Run
- Affected tests: synthetic skipped non-treatment beam provenance tests
- Unchanged boundaries: treatment-beam MU requirements, active treatment dose,
  Sumtally normalization, factor `1.0`, DICOM coordinates and dose meaning,
  public physics, fixed-field 3D-CRT scope, and clinical claims

## Approval Status

The primary user approved this proposal on 2026-08-13. Implementation,
synthetic validation, specification promotion, and archive cleanup are within
that approved scope. Real phits2dicom and real DICOM reruns remain unverified
and were not authorized by this approval.
