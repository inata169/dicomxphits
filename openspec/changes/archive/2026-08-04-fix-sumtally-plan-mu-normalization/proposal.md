# Correct Sumtally Plan-MU Normalization

## Why

A human-operated Windows end-to-end test with a designated non-patient
phantom showed that the coordinate-corrected RTDOSE was placed consistently
with the reference volume after the separate isocenter-translation correction,
but its dose amplitude remained approximately one active-treatment-MU total
too small. Increasing `maxcas` or `maxbch` can reduce Monte Carlo uncertainty
but cannot correct this deterministic scale loss.

The public workflow generates Sumtally with `isumtally = 2`, active-segment MU
as each file's weight, and `sumfactor = 1.0`. PHITS defines `isumtally = 2` as a
weighted average whose file weights are normalized by their sum and whose
absolute scale is set by `sumfactor`. Because each active treatment-segment
tally already has the approved `totfact_per_MU` applied and therefore
represents dose per MU, `sumfactor = 1.0` produces an MU-weighted average
rather than the required sum of treatment-segment dose contributions.

The current documented `sumfactor = 1.0` contract therefore conflicts with
the public workflow's stated full-plan absolute-dose semantics and with the
external tool's documented equation.

## What Changes

- Define the exact treatment-dose Sumtally equation for `isumtally = 2` with
  active `segment_mu` weights and per-MU segment tallies.
- Set `sumfactor` to the validated sum of active treatment-segment MU so the
  Sumtally result is `sum(segment_mu * segment_dose_per_mu)` rather than a
  normalized weighted average.
- Exclude DICOM `TreatmentDeliveryType = SETUP` and other validated skipped
  non-treatment beams from PHITS segments, Sumtally weights, and `sumfactor`.
  Preserve their finite nonnegative BeamMeterset only as plan provenance.
- Require every difference between the active treatment-segment MU sum and the
  complete plan, included, and normalization MU totals to be explained exactly
  by validated skipped non-treatment beam evidence with zero segment MU.
- Record the factor, units, active and skipped MU evidence, equation, and
  resulting dose state in Sumtally and RTDOSE provenance.
- Reject legacy Sumtally evidence generated with the incorrect factor and
  require Sumtally Generate, Sumtally Run, RTDOSE Prepare, and RTDOSE Run to be
  repeated. Existing digest-bound segment PHITS outputs remain reusable.
- Keep RTDOSE conversion `factor = 1.0` so active treatment MU is not applied
  twice.
- Keep GPR comparison free of evaluation-dose rescaling; disagreement remains
  visible after the corrected absolute-dose pipeline is exercised.
- Validate the behavior with synthetic tallies and fake external-tool runners
  before requesting any separately approved non-patient external execution.

## Impact

- Affected capability: `rtdose-dicom-semantics`
- Likely affected runtime after approval:
  `sumtally_inputs.py`, `prepare_sumtally.py`, `prepare_rtdose.py`, and GUI
  stale-stage recovery or messaging
- Likely affected tests: synthetic multi-segment MU summation, skipped SETUP
  evidence, inconsistent MU rejection, legacy-factor rejection, RTDOSE
  no-double-scaling, and manual-smoke workflow tests
- Affected documentation: Sumtally normalization, RTDOSE absolute-dose
  semantics, and safe rerun guidance
- Unchanged boundaries: approved `totfact_per_MU`, source spectrum, accelerator
  model, PHITS transport, segment geometry, `maxcas`, `maxbch`, OpenMP,
  coordinate mapping, DICOM identity policy, external GPR implementation, and
  education-and-research-only claims

## Approval Status

The human approved creation of this proposal and then approved the clarified
contract that `sumfactor` includes active treatment-segment MU only, while
validated skipped SETUP beam evidence remains outside PHITS and Sumtally dose
calculation. The human approved repository runtime implementation, synthetic
tests, and documentation on a dedicated feature branch. External Sumtally,
RTDOSE, GPR, or additional PHITS execution and specification promotion remain
unapproved until separate human decisions.
