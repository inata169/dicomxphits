## ADDED Requirements

### Requirement: Missing Non-Treatment Beam Meterset Compatibility

The public RTDOSE adapter SHALL interpret an absent or empty `BeamMeterset` as
effective `0.0 MU` only when the referenced RT Plan beam is not
treatment-eligible and the canonical manifest represents that beam exclusively
as skipped evidence with zero beam meterset and zero segment MU. The adapter
SHALL record every beam number for which it uses this compatibility
interpretation. The effective zero meterset MUST NOT contribute to PHITS,
Sumtally weights, `sumfactor`, treatment dose, or dose normalization.

The adapter MUST continue to require a finite positive `BeamMeterset` for every
treatment-eligible referenced beam. It MUST reject a non-empty malformed,
negative, or non-finite non-treatment value, an active non-treatment segment,
or manifest evidence that does not match the effective zero meterset.

#### Scenario: Referenced setup beam omits BeamMeterset

- **WHEN** a referenced setup or other non-treatment beam has no
  `BeamMeterset`, and the canonical manifest retains it only as skipped zero-MU
  evidence
- **THEN** RTDOSE provenance records the missing value as effective `0.0 MU`
  and continues without adding a treatment-dose contribution

#### Scenario: Treatment beam omits BeamMeterset

- **WHEN** a treatment-eligible referenced beam has no finite positive
  `BeamMeterset`
- **THEN** RTDOSE Prepare fails before external conversion

#### Scenario: Non-treatment meterset evidence is unsafe

- **WHEN** a referenced non-treatment beam has a malformed, negative, or
  non-finite non-empty meterset, is active, or lacks matching skipped zero-MU
  manifest evidence
- **THEN** RTDOSE Prepare fails before external conversion
