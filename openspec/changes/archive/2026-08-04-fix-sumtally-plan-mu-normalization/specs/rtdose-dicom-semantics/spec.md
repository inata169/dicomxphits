## ADDED Requirements

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
