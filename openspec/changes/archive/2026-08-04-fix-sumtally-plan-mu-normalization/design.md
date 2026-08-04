# Design: Sumtally Plan-MU Normalization

## Context

The public fixed-field 3D-CRT workflow produces one PHITS tally per active
treatment segment. The approved public source calibration is applied in each
segment input as `totfact_per_MU`, so each active segment result represents
dose per MU for that segment geometry.

Sumtally combines those results with:

```text
isumtally = 2
weight_j = active_segment_mu_j
```

The PHITS Sumtally contract for this mode is:

```text
X = F * sum((weight_j / sum(weight)) * X_j)
```

where `F` is `sumfactor`. The current `F = 1.0` therefore returns an
MU-weighted average. The required treatment dose is:

```text
TreatmentDose = sum(active_segment_mu_j * segment_dose_per_mu_j)
```

These equations are equal only when:

```text
F = sum(active_segment_mu_j)
```

The external-tool equation is documented in the official PHITS User's Manual
3.36, “General format of tally sections,” under the Sumtally subsection:
<https://phits.jaea.go.jp/manual/PHITS-en/chapters/tally-format.html>.

DICOM `TreatmentDeliveryType = SETUP` identifies a beam for setup imaging or
measurement positions where no treatment beam is applied. The public manifest
keeps such a beam as skipped, zero-segment-MU provenance. Its finite
nonnegative BeamMeterset remains part of the complete referenced-plan totals
but is not a treatment dose contribution.

## Goals

- Restore absolute treatment-dose summation without changing segment PHITS
  physics or rerunning transport unnecessarily.
- Bind the applied treatment MU scale to validated manifest evidence.
- Preserve skipped SETUP provenance without adding it to treatment dose.
- Prevent both omission and double application of active treatment MU.
- Preserve fail-closed provenance across Sumtally and RTDOSE stages.

## Non-Goals

- Recalibrate the approved public machine model or `totfact_per_MU`.
- Treat a SETUP or other skipped non-treatment beam as a PHITS segment.
- Tune Monte Carlo histories, uncertainty, or convergence criteria.
- Change RTDOSE coordinates, voxel ordering, DICOM plan references, or dose
  units.
- Add an evaluation-dose scale factor to GPR comparison.
- Claim clinical, vendor, facility, or universal machine-dose agreement.

## Decisions

### 1. Sumtally performs the only active-treatment-MU multiplication

For active treatment segments `j`, generation will use each finite positive
`segment_mu_j` as the Sumtally file weight and use their validated sum as
`sumfactor`. The resulting tally is the absolute treatment-dose sum under the
approved public reference-model calibration.

RTDOSE conversion remains `factor = 1.0`. It must not apply Beam MU or an MU
total again.

### 2. Skipped non-treatment beams remain provenance only

A DICOM SETUP or other accepted non-treatment beam may remain in the canonical
manifest only with a skip reason, finite nonnegative BeamMeterset, and zero
segment MU. It contributes no PHITS input, Sumtally file weight, or
`sumfactor`.

The manifest's complete plan, included, and dose-normalization MU totals remain
bound to all fraction-group referenced beams under the accepted existing
contract. The difference between each complete total and the active
treatment-segment MU sum must be explained by the BeamMeterset sum of validated
skipped non-treatment beams. Any unexplained, negative, non-finite, or
inconsistent difference fails before Sumtally generation.

### 3. Normalization evidence fails closed

The generated and execution summaries will bind at least:

- active treatment-segment MU sum and unit;
- skipped non-treatment beam numbers, BeamMetersets, and zero segment-MU sum;
- complete plan, included, and dose-normalization MU totals;
- the reconciliation between active and skipped evidence;
- `isumtally`, weight field, and `sumfactor`;
- the explicit summation equation and output dose state; and
- the canonical manifest and generated-input digests already required by the
  public workflow.

### 4. Incorrect legacy Sumtally results are not migrated by rescaling

A legacy Sumtally output generated with `isumtally = 2`, active `segment_mu`
weights, and `sumfactor = 1.0` does not prove the required treatment-dose sum.
RTDOSE Prepare must reject that evidence. The supported recovery is to reuse
unchanged, digest-bound active-segment PHITS outputs and rerun Sumtally Generate
and Sumtally Run, followed by RTDOSE Prepare and RTDOSE Run.

The adapter will not multiply an existing DICOM or tally file after the fact,
because that would bypass Sumtally uncertainty propagation and provenance.

### 5. Statistical precision remains independent of dose scale

`maxcas` and `maxbch` control Monte Carlo precision. They do not enter the
active-treatment-MU normalization equation and must not change the expected
mean dose scale. A later, separately approved calculation may increase
histories only after the deterministic normalization correction is validated.

### 6. External comparison remains unscaled

Synthetic tests will establish the algebra and stage contracts. Any real
non-patient Sumtally, RTDOSE, or GPR execution requires separate explicit human
approval. GPR must use the generated dose without an evaluation scale factor,
so remaining machine-model or statistical disagreement is observable.

## Risks and Mitigations

- **Risk: active treatment MU is applied twice.** Keep phits2dicom
  `factor = 1.0`, record the single application stage, and test that RTDOSE
  preserves Sumtally dose values.
- **Risk: SETUP BeamMeterset is mistaken for treatment MU.** Require skipped
  non-treatment classification and zero segment MU, and exclude that evidence
  from Sumtally inputs and `sumfactor`.
- **Risk: a stale legacy result appears completed.** Bind the normalization
  contract and generated-input digest into execution evidence and require a
  new Sumtally Run before RTDOSE acceptance.
- **Risk: a factor change hides a calibration problem.** Derive the factor only
  from canonical active segment MU and do not introduce empirical or
  GPR-derived scaling.
- **Risk: higher histories are mistaken for a scale correction.** Keep runtime
  precision controls outside the normalization formula and document the
  distinction.

## Validation Strategy

- Use synthetic active segment tallies with unequal MU and analytically known
  output to prove the PHITS `isumtally = 2` equation.
- Prove `sumfactor` equals the active treatment-segment MU sum.
- Prove positive or zero BeamMeterset on a validated skipped SETUP beam does
  not change the factor and exactly reconciles the complete MU totals.
- Mutate active, skipped, and complete MU evidence independently and require
  fail-closed behavior.
- Reject legacy generation and execution summaries that bind the incorrect
  factor.
- Verify RTDOSE conversion remains factor one and preserves physical dose
  values without a second MU multiplication.
- Run only fake external-tool runners in automated validation.
- Request separate approval before reusing designated non-patient PHITS
  segment outputs for Sumtally, RTDOSE, and unscaled GPR validation.
