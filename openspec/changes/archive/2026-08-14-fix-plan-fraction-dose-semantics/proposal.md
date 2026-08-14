# Change: Restore PLAN Course-Dose Fraction Scaling

## Why

The accepted full-plan workflow applies the approved public-model
`totfact_per_MU` in each PHITS segment and applies the active treatment MU once
in Sumtally. That result therefore represents one delivery of the selected
Fraction Group. The RTDOSE adapter does not read or apply the selected Fraction
Group's `NumberOfFractionsPlanned`, but it synchronizes the output to
`DoseSummationType = PLAN`.

For a supported plan with more than one planned fraction, the current numerical
dose can therefore remain a one-fraction dose while the DICOM object claims a
complete PLAN dose. The missing factor is independent of the IEC gantry
direction correction and does not explain or repair spatial distribution
errors.

## What Changes

- Require exactly one unambiguous `FractionGroupSequence` item for the public
  fixed-field 3D-CRT PLAN-dose path.
- Require that Fraction Group to contain a finite positive integer
  `NumberOfFractionsPlanned` and bind its group number and fraction count to the
  frozen RT Plan evidence.
- Define the Sumtally output as one-fraction physical dose in `GY`, after
  `totfact_per_MU` and active treatment MU have each been applied once.
- Compute course dose during RTDOSE conversion as
  `dose_per_fraction * NumberOfFractionsPlanned`.
- Keep the upstream public-model conversion base factor at `1.0`, and pass the
  planned fraction count as the effective PHITS2DICOM factor exactly once.
- Record the input dose state, base factor, fraction count, effective factor,
  equation, frozen-plan binding, and course-dose contract version in RTDOSE
  preparation and execution evidence.
- Reject missing, empty, zero, negative, non-integral, ambiguous, stale, or
  changed fraction evidence before external conversion or acceptance of a
  completed PLAN RTDOSE.
- Require legacy RTDOSE results that lack the new course-dose provenance to be
  regenerated from RTDOSE Prepare and Run. Existing bound PHITS segment and
  Sumtally results remain reusable for this dose-only correction.
- Add synthetic tests for one and multiple fractions, invalid and changed
  evidence, single application of MU and fraction count, recovery gating, and
  preservation by coordinate correction.

## Boundaries

- Do not change the approved public calibration, `totfact_per_MU`, segment MU,
  BeamMeterset interpretation, Sumtally weights, `sumfactor`, normalization, PHITS
  source or accelerator physics, tally meshes, DICOM coordinates, voxel
  placement, or gantry geometry.
- Do not multiply the already converted final DICOM PixelData as an undocumented
  post-processing repair. Course scaling belongs in the guarded RTDOSE converter
  input so the converter emits a correctly scaled DICOM dose representation.
- Do not introduce TPS-, plan-, machine-, or phantom-specific empirical factors.
- Do not combine PLAN-versus-fraction dose with coordinate-output choices or any
  other unapproved OpenSpec change.
- Automated validation uses only synthetic DICOM and fake external runners. Real
  PHITS, Sumtally, PHITS2DICOM, GPR, or real DICOM execution and inspection remain
  prohibited until separate explicit human approval.

## Impact

- Affected specification: `rtdose-dicom-semantics`
- Expected implementation areas after approval:
  - `src/dicomxphits/rtdose_plan_references.py`
  - `src/dicomxphits/prepare_rtdose.py`
  - RTDOSE completion/recovery provenance gates
  - focused synthetic RTDOSE and workflow tests
  - public workflow documentation
- Existing outputs:
  - gantry-direction corrections still require PHITS recalculation as already
    specified by the independent IEC gantry change;
  - fraction-only correction does not alter PHITS or Sumtally bytes and requires
    regeneration beginning at RTDOSE Prepare;
  - a final result containing both corrections must be regenerated from the
    earliest changed stage, which is PHITS for a nonzero-gantry plan.
