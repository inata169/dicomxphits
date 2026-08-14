## ADDED Requirements

### Requirement: Single Fixed Public Beam Model Identity

The public rectangular 3D-CRT workflow SHALL define one package-owned identity
for its Elekta Precise nominal 6 MV photon public research model. The identity
SHALL state that its nominal energy is fixed and MUST be reused by model
validation, serialized evidence, and GUI presentation. The workflow MUST NOT
present this identity as a monoenergetic 6 MeV photon source, an energy
selection, or support for a 10 MV model.

#### Scenario: Public model identity is consumed

- **WHEN** the GUI presents the model or workspace preparation validates and
  records it
- **THEN** each consumer obtains the same fixed photon, nominal 6 MV public
  research-model identity without independently hard-coding a different model
  name or supported energy

### Requirement: Fail-Closed Included-Beam Compatibility

Before writing a public spectrum or any segment PHITS input, the common public
workspace-preparation path SHALL validate every treatment beam included in the
workspace. Each included beam MUST have DICOM `RadiationType` `PHOTON`, its
first control point MUST explicitly provide a finite positive numeric
`NominalBeamEnergy` equal to 6 MV, and every effective later-control-point
energy MUST remain 6 MV. This validation MUST apply to GUI and CLI workspace
generation and MUST NOT be implemented as a GUI-only gate.

#### Scenario: One supported beam

- **WHEN** one included treatment beam is photon radiation and all effective
  control-point nominal energies are 6 MV
- **THEN** compatibility validation succeeds before the unchanged public PHITS
  inputs are generated

#### Scenario: Multiple supported beams

- **WHEN** every included treatment beam is photon radiation and every
  effective nominal energy is 6 MV
- **THEN** compatibility validation succeeds for all beams

#### Scenario: Unsupported nominal energy

- **WHEN** an included beam has an effective nominal energy such as 10 MV
- **THEN** workspace preparation fails closed before writing the public
  spectrum or a segment PHITS input

#### Scenario: Mixed beam energies

- **WHEN** included beams contain both 6 MV and another nominal energy
- **THEN** workspace preparation rejects the plan before writing the public
  spectrum or a segment PHITS input

#### Scenario: Non-photon treatment beam

- **WHEN** an included treatment beam has a `RadiationType` other than
  `PHOTON` or lacks a provable photon radiation type
- **THEN** workspace preparation fails closed before writing the public
  spectrum or a segment PHITS input

### Requirement: DICOM Control-Point Energy Inheritance

The compatibility validator SHALL require `NominalBeamEnergy` on the first
control point of each included treatment beam. A later control point that
omits the attribute SHALL inherit the immediately preceding effective value.
An explicit later value MUST parse successfully and MUST equal both the prior
effective value and the supported 6 MV nominal energy.

#### Scenario: Later energy is omitted

- **WHEN** control point zero explicitly specifies valid 6 MV and a later
  control point omits `NominalBeamEnergy`
- **THEN** the later control point inherits 6 MV and validation succeeds

#### Scenario: First energy is missing

- **WHEN** control point zero lacks `NominalBeamEnergy`
- **THEN** the validator does not infer a default and rejects the beam before
  PHITS input generation

#### Scenario: Energy changes within one beam

- **WHEN** a later control point explicitly changes the effective nominal
  energy from 6 MV
- **THEN** the validator rejects the beam before PHITS input generation

#### Scenario: Invalid nominal energy value

- **WHEN** an explicit nominal energy is nonnumeric, NaN, infinite, zero, or
  negative
- **THEN** the validator rejects the beam before PHITS input generation

### Requirement: Controlled Compatibility Evidence and Failure

Successful workspace preparation SHALL add a backward-compatible
`public_beam_model` object to the segment manifest and public
workspace-preparation summary. It SHALL identify the fixed model, supported
radiation type and nominal energy, successful validation, and each included
beam's number, optional name, effective nominal energy, radiation type, and
use of control-point inheritance. A compatibility failure SHALL identify the
beam number and name when present, observed energy when safely representable,
the fixed 6 MV model, and the fact that PHITS input was not generated.

#### Scenario: Successful evidence

- **WHEN** all included treatment beams pass compatibility validation
- **THEN** both JSON artifacts record matching fixed-model and per-beam 6 MV
  evidence without removing or reinterpreting an existing field

#### Scenario: Beam-specific failure

- **WHEN** one included treatment beam fails radiation-type or energy
  validation
- **THEN** the controlled error identifies that beam, explains the fixed 6 MV
  compatibility requirement, and states that no PHITS input was generated

### Requirement: Existing 6 MV Physics Is Unchanged

For a valid supported 6 MV RT Plan, this compatibility guard MUST NOT alter the
public spectrum bytes, source geometry, MLC or jaw geometry, scaling,
materials, cutoff or transport settings, tally definitions,
`totfact_per_MU`, Sumtally normalization, RTDOSE conversion, DICOM meaning, or
coordinate behavior. The only accepted output difference from this guard is
the additive validation evidence in JSON artifacts and the separately
specified GUI presentation.

#### Scenario: Supported input regression comparison

- **WHEN** representative synthetic 6 MV workspace output before and after the
  guard is compared
- **THEN** the public spectrum and generated PHITS inputs are byte-equivalent
  and only the specified additive evidence and GUI presentation differ

### Requirement: Synthetic Beam-Model Validation Boundary

Automated compatibility tests SHALL use synthetic RT Plan datasets and fake or
mock external-tool boundaries. They MUST NOT use patient DICOM, private
fixtures, licensed external tools, or real PHITS calculation output.

#### Scenario: Automated compatibility matrix

- **WHEN** supported and unsupported radiation types, energies, and
  control-point inheritance are tested
- **THEN** synthetic datasets exercise the common validator without executing
  an external tool
