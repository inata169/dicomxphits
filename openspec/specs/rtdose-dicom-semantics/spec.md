# rtdose-dicom-semantics Specification

## Purpose

Define the fail-closed provenance, frozen-plan reference, semantic validation,
and dose/geometry preservation requirements for accepting the documented
full-plan RTDOSE output in the fixed-field 3D-CRT research workflow.
## Requirements
### Requirement: Full-Plan Dose Summation Gate

The public RTDOSE adapter SHALL assign `DoseSummationType = PLAN` only when the
frozen RT Plan and prepared segment manifest prove that the all-active-segments
Sumtally result covers the complete accepted `full_plan` delivery. The adapter
MUST fail closed before accepting an RT Dose when the plan identity, workflow
mode, treatment-beam coverage, or existing strict manifest evidence is missing,
ambiguous, or inconsistent.
The adapter SHALL also require the canonical segment-manifest SHA-256 and the
SHA-256 values of the generated Sumtally wrapper and `sumtally.inp` recorded by
Sumtally Generate and Sumtally Run to match before it accepts PLAN semantics.
Sumtally Run SHALL execute only the wrapper path recorded by Sumtally Generate
and SHALL fail before external execution when either generated input changed.
Sumtally Generate SHALL record the path and SHA-256 of every active segment
output and every recursively resolved `infl` file consumed by that wrapper.
Sumtally Run SHALL fail before external execution when that dependency set or
any recorded dependency digest changed.
Sumtally Run SHALL accept success only when that invocation creates the expected
dose output or changes its SHA-256, and SHALL record the resulting SHA-256.
Timestamp or metadata-only changes SHALL NOT count as an output update. RTDOSE
Prepare SHALL verify that
digest before modifying the output for conversion, and RTDOSE Run SHALL verify
the post-Prepare digest before conversion.
Referenced beams whose delivery type is not treatment-eligible SHALL be
excluded from active treatment coverage only when the manifest represents each
one as skipped with zero segment MU and a matching finite nonnegative beam
meterset. The adapter SHALL keep the manifest plan, included, and normalization
MU totals bound to the complete fraction-group referenced beam total.
Workspace preparation and Sumtally generation SHALL apply the same nonnegative
exception to those skipped non-treatment beams while retaining the positive-MU
requirement for every treatment-eligible beam.
The adapter SHALL bind the frozen RT Plan by its full-file SHA-256 recorded in
the adjacent completed CT2PHITS workspace manifest. When that legacy evidence
is absent, it SHALL reconstruct segments from the RT Plan and recorded sampling
contract and require exact segment-geometry equality. RTDOSE Prepare SHALL also
record the generated `phits2dicom.inp` SHA-256, and RTDOSE Run SHALL verify it
before launching the converter. RTDOSE Prepare SHALL record the path and
SHA-256 of every file referenced by that converter input, and RTDOSE Run SHALL
revalidate every recorded file immediately before launching the converter.
RTDOSE Run SHALL synchronize plan references only when the converter creates
the expected RTDOSE or changes its SHA-256; timestamp-only changes to a stale
output SHALL fail before synchronization.

#### Scenario: Complete accepted plan delivery

- **WHEN** the frozen RT Plan matches the manifest and every treatment beam
  referenced by its fraction groups is covered by the accepted full-plan
  manifest
- **THEN** the converted RT Dose is labeled `DoseSummationType = PLAN`

#### Scenario: Referenced setup beam is skipped

- **WHEN** a fraction group references a `SETUP` or other non-treatment beam
  that the manifest retains only as skipped zero-segment-MU evidence, while all
  treatment-eligible beams have complete active coverage
- **THEN** the non-treatment beam is excluded from treatment coverage without
  changing the manifest's full referenced-beam normalization MU

#### Scenario: Referenced setup beam has zero meterset

- **WHEN** a referenced non-treatment beam has finite zero beam meterset and is
  retained only as skipped zero-segment-MU evidence
- **THEN** the adapter accepts that non-treatment evidence while continuing to
  require positive meterset for every treatment-eligible beam

#### Scenario: Non-treatment beam is active or missing skip evidence

- **WHEN** a referenced non-treatment beam is active, has positive segment MU,
  has a mismatched beam meterset, or lacks its skipped manifest evidence
- **THEN** the adapter fails before accepting PLAN-dose provenance

#### Scenario: Incomplete or inconsistent delivery

- **WHEN** the manifest is not `full_plan`, identifies another plan, or does not
  prove complete treatment-beam coverage
- **THEN** the adapter fails without accepting or labeling a plan-level RT Dose

#### Scenario: Manifest changed after Sumtally calculation

- **WHEN** the current segment manifest digest differs from the digest recorded
  by Sumtally Generate or Sumtally Run
- **THEN** RTDOSE preparation fails and requires Sumtally inputs and execution
  to be regenerated before PLAN semantics can be accepted

#### Scenario: Generated Sumtally input changed or replaced

- **WHEN** the requested Sumtally wrapper is not the path recorded by Generate,
  or the recorded wrapper or `sumtally.inp` content no longer matches its
  generated SHA-256
- **THEN** Sumtally Run fails before external execution and no execution digest
  is accepted as PLAN-dose provenance

#### Scenario: Sumtally execution dependency changed or replaced

- **WHEN** an active segment output or a direct or transitive wrapper `infl`
  dependency no longer matches its Sumtally Generate SHA-256
- **THEN** Sumtally Run fails before external execution and records no accepted
  PLAN-dose provenance

#### Scenario: Sumtally output is stale or replaced

- **WHEN** Sumtally Run leaves the expected output bytes unchanged, including
  merely changing its timestamp, or its recorded output is replaced before
  RTDOSE Prepare or after preparation
- **THEN** the current stage fails before accepting or converting that output
  as PLAN-dose provenance

### Requirement: Authoritative Frozen RT Plan Reference

The public RTDOSE adapter SHALL derive dose provenance from the frozen RT Plan
used for workspace preparation and MUST NOT treat the user-supplied RT Dose
template as authoritative provenance. A plan-level output SHALL contain exactly
one `ReferencedRTPlanSequence` item whose Referenced SOP Class UID and
Referenced SOP Instance UID match that frozen RT Plan. The adapter SHALL remove
template-derived fraction-group and beam reference sequences that describe a
partial delivery.

#### Scenario: Template contains stale beam references

- **WHEN** `phits2dicom` produces an RT Dose retaining a BEAM summation type or
  references copied from a different template plan
- **THEN** the adapter replaces the hierarchy with PLAN semantics and exactly
  one reference to the frozen RT Plan

#### Scenario: Frozen plan identity cannot be established

- **WHEN** the explicit frozen RT Plan is absent, is not an RT Plan DICOM, or
  does not match the prepared manifest
- **THEN** RTDOSE preparation fails before external conversion starts

#### Scenario: Frozen plan content changed without changing identity

- **WHEN** RT Plan content no longer matches its CT2PHITS SHA-256, or its
  reconstructed segment geometry differs despite retaining the same UIDs and
  metersets
- **THEN** RTDOSE preparation fails before PLAN provenance is accepted

#### Scenario: Converter input changed after preparation

- **WHEN** the generated `phits2dicom.inp` no longer matches the SHA-256
  recorded by RTDOSE Prepare
- **THEN** RTDOSE Run fails before launching `phits2dicom`

#### Scenario: File referenced by converter input changed after preparation

- **WHEN** the workspace template, CT reference, prepared Sumtally dose, or
  companion `phits.out` no longer matches its RTDOSE Prepare SHA-256
- **THEN** RTDOSE Run fails before launching `phits2dicom`

#### Scenario: Converter merely touches a stale RTDOSE

- **WHEN** `phits2dicom` returns success but the expected RTDOSE SHA-256 is
  unchanged from its pre-execution value
- **THEN** RTDOSE Run fails before plan-reference synchronization and does not
  accept the stale file

### Requirement: Final RT Dose Semantic Validation

RTDOSE Run SHALL reopen the documented coordinate-corrected output and validate
its plan summation type and frozen-plan reference before reporting stage
success. A successful execution summary SHALL record the validated summation
type and referenced plan identity without using the template's original values
as evidence.

#### Scenario: Synchronized final output

- **WHEN** conversion, metadata synchronization, and coordinate correction all
  complete and the final output references the frozen plan exactly
- **THEN** RTDOSE Run reports success and records the final semantic-validation
  evidence

#### Scenario: Final output remains stale or malformed

- **WHEN** the final output lacks PLAN semantics, has zero or multiple plan
  references, or references another plan
- **THEN** RTDOSE Run reports failure and does not present the file as an
  accepted workflow result

### Requirement: Dose and Geometry Preservation

Full-plan reference synchronization SHALL NOT change `PixelData`, physical dose
values, `DoseGridScaling`, `DoseUnits`, grid dimensions, coordinate-correction
results, `FrameOfReferenceUID`, MU normalization, or approved public dose-factor
semantics. The change SHALL remain within the documented fixed-field 3D-CRT,
non-patient research workflow.

#### Scenario: Metadata is synchronized

- **WHEN** stale template provenance is replaced with the frozen RT Plan
  reference
- **THEN** stored dose values, physical dose values, scaling, units, geometry,
  coordinates, Frame of Reference, and normalization remain unchanged

### Requirement: Synthetic Validation Boundary

Automated validation of full-plan RT Dose semantics SHALL use synthetic DICOM,
temporary workspaces, and fake or mock external-tool runners. It MUST NOT run
real PHITS, Sumtally, phits2dicom, GPR-comparing, or real DICOM workflows.

#### Scenario: Automated provenance test

- **WHEN** stale-reference replacement or fail-closed validation is tested
- **THEN** only synthetic identifiers and a fake conversion runner are used

### Requirement: Absolute Active-Treatment-MU Sumtally Normalization

For the public fixed-field 3D-CRT absolute-dose workflow, every active
treatment-segment PHITS tally SHALL represent dose per MU through the already
approved `totfact_per_MU` source calibration. When Sumtally uses
`isumtally = 2` with active `segment_mu` as each file weight, Sumtally Generate
SHALL set `sumfactor` to the finite positive sum of all active treatment-segment
MU so the result equals
`sum(active_segment_mu * segment_dose_per_mu)`. It MUST NOT use
`sumfactor = 1.0` for that contract and MUST NOT describe the normalized
weighted average as a full-plan absolute treatment dose.

A DICOM SETUP or other accepted non-treatment beam SHALL remain excluded from
PHITS and Sumtally only when the canonical manifest preserves it as skipped
evidence with finite nonnegative BeamMeterset and zero segment MU. Its
BeamMeterset MUST NOT contribute to Sumtally file weights or `sumfactor`.

The canonical manifest's complete plan, included, and dose-normalization MU
totals SHALL remain bound to every fraction-group referenced beam under the
existing public contract. For each complete total, the difference from the
active treatment-segment MU sum MUST equal the BeamMeterset sum of validated
skipped non-treatment beams. Sumtally Generate MUST fail before accepting its
generated inputs when active or skipped MU evidence is missing, non-finite,
invalid, or does not reconcile those totals.

Sumtally Generate and Run SHALL record and bind the active MU sum and unit,
skipped non-treatment MU evidence, complete accepted MU totals,
reconciliation, `isumtally`, weight field, `sumfactor`, exact summation rule,
output dose state, canonical manifest digest, and generated-input digests.
RTDOSE conversion SHALL keep `factor = 1.0` and MUST NOT apply segment, beam,
or plan MU a second time.

#### Scenario: Unequal active treatment-segment MU forms the dose sum

- **WHEN** active treatment-segment tallies have unequal positive segment MU
  and each tally represents dose per MU under the approved public calibration
- **THEN** Sumtally uses the active segment MU as relative weights and their
  sum as `sumfactor`, producing the sum of every active segment's MU-scaled
  dose contribution

#### Scenario: SETUP beam remains outside treatment dose

- **WHEN** a SETUP beam is validated as skipped non-treatment evidence with
  finite nonnegative BeamMeterset and zero segment MU
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
  full-plan absolute treatment dose

#### Scenario: RTDOSE consumes corrected Sumtally dose

- **WHEN** RTDOSE Prepare receives digest-bound Sumtally evidence proving the
  corrected active-treatment-MU summation contract
- **THEN** phits2dicom uses `factor = 1.0` and the final RTDOSE preserves that
  treatment dose without another MU multiplication

### Requirement: Incorrect Sumtally Normalization Is Stale Evidence

Sumtally or RTDOSE evidence generated with `isumtally = 2`, active
`segment_mu` weights, and a factor that does not reproduce the required active
treatment-dose sum SHALL NOT establish completed full-plan dose provenance.
The workflow SHALL require Sumtally Generate and Sumtally Run to be repeated
with the corrected contract, followed by RTDOSE Prepare and RTDOSE Run. It
SHALL permit unchanged, digest-bound active-segment PHITS outputs to be reused
and MUST NOT require PHITS transport solely because the prior Sumtally
normalization was incorrect.

The workflow MUST NOT repair legacy dose by empirically rescaling an existing
tally or DICOM output, and external GPR comparison MUST NOT supply a hidden
evaluation-dose scale factor.

The GUI SHALL report RTDOSE `Completed` only when the current successful
Prepare summary is bound to the current Sumtally Generate/Run evidence and the
successful RTDOSE Run summary records the exact current Prepare-summary digest.
A stale successful summary SHALL remain available for audit but MUST NOT enable
a stale Run action. Explicit downstream-overwrite permission SHALL enable a
fresh Prepare without requiring deletion of the stale summary.

#### Scenario: Legacy factor-one weighted average is selected

- **WHEN** existing Sumtally evidence records the normalized weighted-average
  contract instead of the required active treatment-dose sum
- **THEN** RTDOSE Prepare rejects it and directs regeneration from the existing
  validated active-segment PHITS outputs

#### Scenario: Existing active-segment outputs remain valid

- **WHEN** every active treatment-segment PHITS output and dependency still
  matches its accepted digest but only the Sumtally normalization contract is
  stale
- **THEN** the user can rerun Sumtally and downstream RTDOSE stages without
  rerunning segment transport

#### Scenario: Stale downstream summaries do not remain completed

- **WHEN** Sumtally is regenerated or RTDOSE Prepare is repeated after an older
  successful RTDOSE Run summary exists
- **THEN** the GUI derives `Not run` or `Prepared` from the current
  digest bindings, disables the stale Run action, and permits explicit
  downstream overwrite to create a fresh Prepare

#### Scenario: Monte Carlo history controls change

- **WHEN** `maxcas` or `maxbch` is increased to reduce statistical uncertainty
- **THEN** the active-treatment-MU normalization equation and expected mean
  dose scale remain unchanged

#### Scenario: Unscaled external comparison

- **WHEN** a separately approved research comparison evaluates the regenerated
  RTDOSE
- **THEN** the evaluation dose is compared without an empirical scale factor,
  leaving residual statistical or model disagreement visible
