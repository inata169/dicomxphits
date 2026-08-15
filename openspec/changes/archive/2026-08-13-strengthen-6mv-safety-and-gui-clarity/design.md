# Design: Strengthen 6 MV Safety and GUI Clarity

## Scope Boundary

This change makes the already fixed public 6 MV research model explicit and
rejects RT Plans that cannot be proven compatible with it. It does not change
the spectrum or create a new beam model. GUI sizing and provenance text are
bounded presentation changes in the existing shared layout.

## Public Model Identity

The implementation will define the public model identity once in the package
module that owns the public spectrum contract, or in one adjacent package
identity object imported by that module. The model identity will provide at
least:

- a stable model identifier;
- display name `Elekta Precise 6 MV public research model`;
- radiation type `PHOTON`;
- nominal energy `6.0` MV; and
- a display statement that the nominal energy is fixed.

GUI text, validation, and evidence serialization will consume this identity.
No energy selection state or alternative model will be introduced.

## Validation Placement and Atomicity

The common validator will operate on the loaded RT Plan and the treatment-beam
selection established by the public manifest construction path. Workspace
preparation will call it before writing the segment manifest, PHITS spectrum,
or any per-segment PHITS input. Both GUI and CLI workspace generation already
enter that common preparation path, so the GUI will not own or bypass this
guard.

The validator will return immutable, JSON-serializable evidence for successful
plans. Manifest construction will add that evidence before the manifest is
written. The public workspace-preparation summary will copy the same semantic
evidence. Existing schemas remain backward-compatible because only new fields
are added.

If validation fails, the existing new-workspace contract and guarded staging
behavior will be used to avoid leaving PHITS inputs. The error will state that
PHITS input generation did not occur. Synthetic tests will assert the absence
of the spectrum and segment `.inp` outputs, not only the exception text.

## Treatment-Beam Selection

Validation applies to every beam that contributes an active segment to the
public workspace. Beams already proven by the existing manifest contract to be
skipped non-treatment or zero-MU entries do not become supported treatment
beams and do not affect the 6 MV evidence set. Existing strict fixed-field
3D-CRT and field-size gates remain authoritative and unchanged.

## DICOM Energy State

For each included treatment beam:

1. `RadiationType` must normalize to DICOM CS value `PHOTON`.
2. Control point zero must contain `NominalBeamEnergy`.
3. Each explicit value must parse as a finite, positive number equal to
   `6.0` MV.
4. A later control point may omit the attribute and inherit the immediately
   preceding effective value.
5. Any explicit later value different from the previous effective value is an
   unsupported within-beam energy change; a value other than `6.0` is also an
   unsupported model mismatch.
6. All included beams must therefore resolve to the same supported 6 MV photon
   model.

No tolerance is introduced around nominal 6 MV. This is a discrete DICOM
model-compatibility check rather than a measurement comparison.

Controlled errors will use public-safe beam identity already available from
the RT Plan: Beam Number and Beam Name where present. Invalid values will be
represented safely rather than interpolated through an uncontrolled traceback.

## Evidence Shape

The manifest and public workspace-preparation summary will each expose an
additive `public_beam_model` object containing:

- model identifier and display name;
- supported radiation type and nominal energy in MV;
- fixed-model status;
- validation status; and
- one entry per included treatment beam with Beam Number, optional Beam Name,
  radiation type, effective nominal energy, and whether later control points
  used inheritance.

The exact existing schema version strings will remain unchanged unless an
existing schema rule requires an additive-version marker; no existing field is
removed or reinterpreted.

## Primary Fluence Mode Boundary

A repository search found no current validation of
`PrimaryFluenceModeSequence` or a corresponding fluence-mode field. This
change will confirm that result during implementation and report it. It will
not infer a 6 MV versus 6 MV FFF contract or add FFF support without a separate
human-approved specification decision. Existing validation, if found through
deeper call-path inspection, will be preserved unchanged.

## Shared GUI Presentation

The fixed-model identity will be placed in the existing shared header or an
adjacent common read-only region so CT2PHITS, Workspace, PHITS, Sumtally, and
RTDOSE pages all show it. The repository URL and author will use the same
shared region and remain static text; no implicit browser, network, or update
check will be added.

Only the `ScrolledText` height or immediately necessary shared-row sizing will
change for the Activity log. Vertical scrolling and `output.see(tk.END)` will
remain. Automated tests will verify shared construction and configuration;
visual acceptance at 1360 x 820 and 1120 x 720 remains a documented Windows
manual check if accurate rendering is unavailable in the development
environment.

## Unchanged Contracts

The implementation must not change public photon spectrum bytes, source or
collimator geometry, MLC and jaw behavior, machine configuration, field-size
guard, PHITS histories or transport settings, dose factors, MU or Sumtally
normalization, RTDOSE conversion, DICOM coordinates, supported delivery
techniques, or clinical claims.
