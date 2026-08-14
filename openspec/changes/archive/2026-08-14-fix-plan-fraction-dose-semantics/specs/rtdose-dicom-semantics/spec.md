## MODIFIED Requirements

### Requirement: Absolute Active-Treatment-MU Sumtally Normalization

For the public fixed-field 3D-CRT absolute-dose workflow, every active treatment-segment PHITS tally SHALL represent dose per MU through the already
approved `totfact_per_MU` source calibration. When Sumtally uses
`isumtally = 2` with active `segment_mu` as each file weight, Sumtally Generate
SHALL set `sumfactor` to the finite positive sum of all active treatment-segment
MU so the result equals
`sum(active_segment_mu * segment_dose_per_mu)`. It MUST NOT use
`sumfactor = 1.0` for that contract and MUST NOT describe the normalized
weighted average as an absolute treatment dose.

That Sumtally result SHALL represent one delivery of the single accepted
Fraction Group in `GY`. A DICOM SETUP or other accepted non-treatment beam SHALL
remain excluded from PHITS and Sumtally only when the canonical manifest
preserves it as skipped evidence with a finite nonnegative `BeamMeterset`, or an
absent or empty value accepted as effective `0.0 MU`, and zero segment MU. Its
effective BeamMeterset MUST NOT contribute to Sumtally file weights or
`sumfactor`.

The canonical manifest's complete plan, included, and dose-normalization MU
totals SHALL remain bound to every beam referenced by the single accepted
Fraction Group under the existing public contract. For each complete total, the
difference from the active treatment-segment MU sum MUST equal the BeamMeterset
sum of validated skipped non-treatment beams. Sumtally Generate MUST fail before
accepting its generated inputs when active or skipped MU evidence is missing,
non-finite, invalid, or does not reconcile those totals.

Sumtally Generate and Run SHALL record and bind the active MU sum and unit,
skipped non-treatment MU evidence, complete accepted MU totals,
reconciliation, `isumtally`, weight field, `sumfactor`, exact summation rule,
one-fraction output dose state, canonical manifest digest, and generated-input
digests. RTDOSE conversion SHALL keep the active-MU public-model base factor at
`1.0`, MUST NOT apply segment, beam, or plan MU a second time, and SHALL derive
its effective conversion factor only as
`1.0 * NumberOfFractionsPlanned` under the separate PLAN course-dose
requirement.

#### Scenario: Unequal active treatment-segment MU forms the fraction dose sum

- **WHEN** active treatment-segment tallies have unequal positive segment MU
  and each tally represents dose per MU under the approved public calibration
- **THEN** Sumtally uses the active segment MU as relative weights and their
  sum as `sumfactor`, producing one Fraction Group delivery as the sum of every
  active segment's MU-scaled dose contribution

#### Scenario: SETUP beam remains outside treatment dose

- **WHEN** a SETUP beam is validated as skipped non-treatment evidence with a
  finite nonnegative `BeamMeterset`, or an absent or empty value accepted as
  effective `0.0 MU`, and zero segment MU
- **THEN** its BeamMeterset remains in complete plan provenance but contributes
  no PHITS segment, Sumtally weight, or `sumfactor`

#### Scenario: Active and skipped MU reconcile complete totals

- **WHEN** the active treatment-segment MU sum plus the validated skipped
  non-treatment BeamMeterset sum equals every accepted complete MU total
- **THEN** Sumtally Generate records the reconciliation and uses only the
  active treatment-segment MU sum as `sumfactor`

#### Scenario: MU evidence is inconsistent

- **WHEN** active or skipped MU evidence is invalid, a skipped beam has nonzero
  segment MU, or the accepted complete MU totals cannot be reconciled
- **THEN** Sumtally Generate fails before its output can be accepted as a
  one-fraction absolute treatment dose

#### Scenario: RTDOSE consumes corrected Sumtally dose

- **WHEN** RTDOSE Prepare receives digest-bound Sumtally evidence proving the
  corrected active-treatment-MU summation contract and validates
  `NumberOfFractionsPlanned = N`
- **THEN** the active-MU base factor remains `1.0`
- **AND** phits2dicom uses effective factor `N` to produce course dose without
  another MU multiplication

## ADDED Requirements

### Requirement: PLAN Course Dose Shall Apply the Planned Fraction Count Once

The public fixed-field 3D-CRT RTDOSE adapter SHALL treat the accepted Sumtally
result as one Fraction Group delivery in `GY`, after the approved public-model
`totfact_per_MU` and active treatment segment MU have each been applied once.
For `NumberOfFractionsPlanned = N`, the adapter SHALL produce PLAN course dose as
`dose_per_fraction * N` and SHALL apply `N` exactly once as the effective
PHITS2DICOM conversion factor.

The upstream public-model base factor SHALL remain `1.0`. The change MUST NOT
alter BeamMeterset interpretation, segment MU, Sumtally weights, `sumfactor`,
normalization, calibration, PHITS or Sumtally numerical output, geometry, or
coordinates. Plan-reference synchronization and coordinate correction MUST
preserve the already course-scaled physical dose. The workflow MUST NOT repair
the omission by multiplying an already converted final DICOM PixelData array.

#### Scenario: One planned fraction preserves existing numerical dose

- **GIVEN** the single supported Fraction Group has
  `NumberOfFractionsPlanned = 1`
- **WHEN** RTDOSE Prepare builds the guarded converter input
- **THEN** the effective PHITS2DICOM factor is `1.0`
- **AND** the course dose equals the one-fraction Sumtally physical dose

#### Scenario: Multiple planned fractions produce course dose

- **GIVEN** the single supported Fraction Group has a positive integer
  `NumberOfFractionsPlanned = N`
- **WHEN** the accepted one-fraction Sumtally dose is converted to RTDOSE
- **THEN** the effective PHITS2DICOM factor is `N`
- **AND** every resulting physical dose value represents
  `dose_per_fraction * N`
- **AND** active treatment MU is not applied again

#### Scenario: Coordinate correction receives course-scaled dose

- **GIVEN** PHITS2DICOM has produced a course-scaled RTDOSE using the validated
  planned fraction count
- **WHEN** plan-reference synchronization and coordinate correction run
- **THEN** they preserve stored values, `DoseGridScaling`, and physical dose
  while changing only their documented metadata and voxel placement semantics
- **AND** no post-conversion fraction multiplication occurs

### Requirement: PLAN Fraction Evidence Shall Be Unambiguous and Content-Bound

The public PLAN-dose path SHALL require exactly one frozen RT Plan
`FractionGroupSequence` item with a positive integer `FractionGroupNumber`, a
positive integer `NumberOfFractionsPlanned`, and the complete accepted beam and
meterset coverage. It MUST fail closed before external RTDOSE conversion when
the Fraction Group or fraction count is missing, empty, zero, negative,
non-integral, non-finite, multiple, ambiguous, stale, or inconsistent.

RTDOSE Prepare and Run SHALL bind and validate the Fraction Group number,
planned fraction count, frozen RT Plan content, one-fraction input dose state,
base factor `1.0`, effective factor, course-dose equation, converter-input
digest, and a versioned course-dose contract. Run SHALL revalidate current
evidence before external execution. Final semantic validation and portable
workspace recovery SHALL reject legacy PLAN RTDOSE completion evidence that
lacks the current course-dose contract.

#### Scenario: Fraction evidence is complete

- **GIVEN** one frozen Fraction Group contains a positive integer planned
  fraction count and passes existing beam, MU, manifest, and plan-content gates
- **WHEN** RTDOSE preparation and execution validate the course-dose contract
- **THEN** the evidence records the group, count, factors, equation, plan
  binding, and current contract version
- **AND** the final output may be accepted as `DoseSummationType = PLAN`

#### Scenario: Planned fraction count is unusable

- **GIVEN** `NumberOfFractionsPlanned` is absent, empty, zero, negative,
  non-integral, or non-finite
- **WHEN** RTDOSE preparation is requested
- **THEN** the stage fails before PHITS2DICOM execution
- **AND** it does not assume a one-fraction default

#### Scenario: Fraction Group selection is ambiguous

- **GIVEN** the frozen RT Plan contains zero or more than one Fraction Group
- **WHEN** the public PLAN-dose gate is evaluated
- **THEN** the stage fails as unsupported before external conversion
- **AND** it does not merge or implicitly select Fraction Groups

#### Scenario: Fraction count changes after preparation

- **GIVEN** RTDOSE Prepare recorded one planned fraction count and converter
  input digest
- **WHEN** the frozen RT Plan fraction count or bound converter input differs at
  RTDOSE Run
- **THEN** Run fails before external execution
- **AND** new RTDOSE preparation is required

#### Scenario: Legacy PLAN output lacks course-dose provenance

- **GIVEN** an existing RTDOSE result is labeled `PLAN` but its successful
  evidence does not bind the current course-dose contract and fraction count
- **WHEN** final validation or workspace recovery evaluates it
- **THEN** it is not accepted as a completed current result
- **AND** regeneration begins at RTDOSE Prepare after existing PHITS and
  Sumtally bindings pass

### Requirement: Fraction-Only Correction Shall Preserve Upstream Dose Artifacts

When only PLAN course-dose fraction semantics change, the workflow SHALL permit
reuse of existing PHITS segment and Sumtally outputs only after their current
content hashes, geometry, normalization, calibration, MU, and frozen-plan
bindings pass. It SHALL require new RTDOSE Prepare and Run artifacts because the
effective conversion factor and final physical dose change.

The independent IEC gantry-direction correction remains a PHITS transport
change. A result requiring both corrections SHALL be regenerated from PHITS,
not repaired only in final DICOM processing.

#### Scenario: Only fraction semantics require correction

- **GIVEN** current PHITS and Sumtally evidence passes and no upstream physics or
  geometry contract changed
- **WHEN** a legacy one-fraction PLAN-labeled RTDOSE is corrected
- **THEN** PHITS and Sumtally numerical outputs remain unchanged
- **AND** regeneration starts at RTDOSE Prepare

#### Scenario: Gantry direction and fraction semantics both require correction

- **GIVEN** a nonzero-gantry result was produced under the stale gantry-direction
  contract and also lacks course-dose fraction scaling
- **WHEN** a corrected final result is requested
- **THEN** regeneration starts with PHITS and continues through Sumtally and
  RTDOSE
- **AND** neither defect is repaired by final-DICOM-only manipulation

### Requirement: Course-Dose Validation Shall Remain Synthetic Until Approved

Automated validation of PLAN fraction scaling SHALL use only synthetic DICOM,
temporary workspaces, and fake external runners. It MUST NOT run or inspect real
PHITS, Sumtally, PHITS2DICOM, GPR, or real DICOM data. Any real-tool or real-data
validation SHALL occur only after separate explicit human approval.

#### Scenario: Automated course-dose regression is executed

- **WHEN** repository validation tests PLAN fraction scaling
- **THEN** it uses analytically known synthetic dose values and fake tools
- **AND** it makes no clinical, commissioning, or real-physics validation claim
