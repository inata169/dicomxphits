# Design: PLAN Course-Dose Fraction Scaling

## Context

The current absolute-dose chain has two already accepted multiplicative steps:

1. PHITS applies the calibrated `totfact_per_MU`, producing segment dose per MU.
2. Sumtally applies each active `segment_mu` once and produces
   `sum(segment_mu * segment_dose_per_mu)` in `GY`.

`BeamMeterset` describes the selected Fraction Group delivery. Repeating that
delivery for `NumberOfFractionsPlanned = N` gives the PLAN course dose:

```text
dose_per_fraction = sum(segment_mu * segment_dose_per_mu)
course_dose       = dose_per_fraction * N
```

The current adapter validates Fraction Group beam references and metersets, but
it accepts more than one Fraction Group, does not collect
`NumberOfFractionsPlanned`, forces PHITS2DICOM factor `1.0`, and then assigns
`DoseSummationType = PLAN`. That is the direct dose-semantics defect.

## Goals

- Make numerical dose and DICOM `PLAN` semantics agree for a supported
  single-Fraction-Group fixed-field 3D-CRT plan.
- Apply both active treatment MU and the planned fraction count exactly once.
- Bind the fraction decision to the same frozen RT Plan already used for beam,
  geometry, and plan-reference validation.
- Fail closed before external conversion when fraction evidence is not safe.
- Preserve upstream PHITS and Sumtally results for a fraction-only correction.
- Keep coordinate correction a pure stored-voxel permutation.

## Non-Goals

- Supporting multiple Fraction Groups, partial courses, delivered-fraction
  tracking, adaptive accumulation, brachytherapy, IMRT, VMAT, or clinical dose
  reconstruction.
- Recomputing or changing BeamMeterset, segment MU, calibration, normalization,
  Monte Carlo histories, source geometry, gantry geometry, or tally values.
- Scaling an existing final DICOM file in place.
- Using a TPS comparison or GPR result to choose a numerical factor.
- Running real external tools or reading real DICOM during automated work.

## Decisions

### 1. The public PLAN path accepts exactly one Fraction Group

The frozen RT Plan must contain exactly one `FractionGroupSequence` item. Its
`FractionGroupNumber` and `NumberOfFractionsPlanned` must each parse as a
positive integer, and the referenced treatment and accepted non-treatment beams
must continue to pass the existing meterset and manifest coverage gates.

Missing, empty, zero, negative, fractional, non-finite, duplicate, or multiple
Fraction Group evidence fails before PHITS2DICOM is launched. The adapter does
not guess a default of one fraction.

### 2. Sumtally remains the one-fraction dose boundary

The existing Sumtally equation and files remain unchanged:

```text
sum(segment_mu * segment_dose_per_mu)
```

The active treatment MU has already been applied exactly once at that boundary.
The Sumtally conversion hint's public-model base factor remains `1.0`; it is not
rewritten to pretend that the upstream tally is already course-scaled.

RTDOSE preparation will describe the input explicitly as one-fraction physical
dose rather than complete PLAN course dose. This clarification changes
provenance semantics, not the Sumtally numerical bytes.

### 3. RTDOSE conversion applies the course factor once

After validating the Sumtally contract and frozen plan, RTDOSE Prepare computes:

```text
base_factor                  = 1.0
planned_fraction_count       = NumberOfFractionsPlanned
effective_phits2dicom_factor = base_factor * planned_fraction_count
```

The effective factor is written to the guarded `phits2dicom.inp`. Scaling at
conversion is preferred to editing final `PixelData` because the converter owns
the DICOM stored-value and `DoseGridScaling` representation. Subsequent plan
reference synchronization must not change dose fields, and coordinate
correction must only permute the converter's already course-scaled stored
values.

`NumberOfFractionsPlanned = 1` retains effective factor `1.0` and produces the
same numerical dose as the current accepted single-fraction behavior.

### 4. Fraction provenance is content-bound and versioned

RTDOSE Prepare and Run evidence will bind at least:

- one Fraction Group number;
- positive integer planned fraction count;
- one-fraction input dose state and unit `GY`;
- public-model base factor `1.0`;
- effective PHITS2DICOM factor;
- the course-dose equation and contract version;
- frozen RT Plan identity and SHA-256 binding;
- prepared converter-input SHA-256.

RTDOSE Run revalidates the current frozen plan and requires the evidence and
prepared converter input to agree before external execution. A changed fraction
count therefore invalidates preparation even if UIDs remain unchanged.

Final semantic validation and workspace recovery require the new course-dose
contract version. A legacy successful summary or RTDOSE without that evidence is
not accepted as current completion and must be regenerated from RTDOSE Prepare.

### 5. Recalculation starts at the earliest changed numerical stage

For this fraction-only correction, PHITS segment and Sumtally numerical outputs
are unchanged and may be reused after their existing hashes and normalization
evidence pass. RTDOSE Prepare and Run must be repeated because the converter
factor and final physical dose change.

The independent gantry-direction correction changes PHITS transport. A plan
that needs both corrections must therefore be regenerated beginning with PHITS,
then Sumtally and RTDOSE. No final-DICOM-only manipulation can repair the gantry
transport direction.

## Alternatives Rejected

### Multiply Sumtally `sumfactor` by the fraction count

This would mix course repetition with the already proven active-MU
normalization, require unnecessary Sumtally regeneration, and make it harder to
prove that MU and fraction count are each applied once.

### Multiply final DICOM PixelData after conversion

This would create a second dose-changing post-processing stage, require custom
stored-value overflow and `DoseGridScaling` handling, and conflict with the
coordinate correction's dose-preservation contract.

### Continue writing `PLAN` while documenting one-fraction values

This preserves the mismatch rather than restoring the documented full-plan
contract.

### Default a missing fraction count to one

This could silently underdose the represented course. Missing or ambiguous
evidence must fail closed.

## Risks and Mitigations

- **Risk: MU is applied twice.** Keep the upstream base factor `1.0`, leave
  Sumtally unchanged, record distinct MU and fraction stages, and test their
  independent equations.
- **Risk: fraction count is applied twice.** Require one versioned course-dose
  factor in prepared and execution evidence and reject stale or inconsistent
  summaries.
- **Risk: multiple Fraction Groups have different schedules.** Reject them as
  unsupported rather than aggregating or selecting implicitly.
- **Risk: final stored values overflow.** Let PHITS2DICOM own DICOM numerical
  representation during conversion; do not multiply stored pixels afterward.
- **Risk: old one-fraction PLAN output appears complete.** Require current
  course-dose provenance in final validation and recovery.
- **Risk: dose correction is mistaken for geometry validation.** Keep the
  changes and evidence independent; synthetic dose tests make no claim about
  real nonzero-gantry transport.

## Synthetic Validation Strategy

- Prove one fraction selects effective factor `1.0` and preserves the existing
  expected physical dose.
- Prove representative multiple-fraction counts produce exactly
  `dose_per_fraction * N` with a fake converter and synthetic DICOM.
- Prove Sumtally files, `sumfactor`, active segment MU, calibration, and upstream
  dose bytes are unchanged.
- Reject absent, empty, zero, negative, fractional, non-finite, and multiple
  Fraction Group/count evidence before fake external execution.
- Change `NumberOfFractionsPlanned` after Prepare and prove Run rejects the stale
  plan/input binding before fake external execution.
- Prove plan-reference synchronization and coordinate correction preserve the
  course-scaled physical dose and geometry.
- Reject legacy preparation, execution, and recovery evidence that lacks the
  current course-dose contract.
- Run only repository synthetic tests, OpenSpec strict validation, public-tree
  verification, and diff checks. Real PHITS, Sumtally, PHITS2DICOM, GPR, and real
  DICOM remain outside this change until separate explicit human approval.
