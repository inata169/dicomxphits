# fixed-6mv-beam-model-safety Delta

## ADDED Requirements

### Requirement: Absolute Dose Factor Shall Bind Transport Topology

The approved public `totfact_per_MU` identity SHALL bind the current combined
transport-topology contract in addition to the machine configuration, public
spectrum, and calibration evidence. Absolute-dose workspace preparation MUST
fail closed when the factor evidence is missing that binding or identifies a
pre-v5 topology contract.

The workflow MUST NOT silently change the numerical factor. The existing
numerical factor MAY be reaccepted for v5 without repeating a full calibration
only after a human accepts evidence that the reference calibration CT and
accelerator regions were disjoint and that the corrected topology preserves
material ownership, source, aperture, physics, tally, MU, and normalization for
that reference calculation.

#### Scenario: Existing factor lacks v5 topology binding

- **WHEN** absolute-dose preparation requests a factor whose evidence binds
  only the machine configuration and spectrum or identifies a pre-v5 geometry
  contract
- **THEN** preparation rejects the factor as stale before generating segment
  PHITS inputs

#### Scenario: Existing numerical factor is reaccepted for v5

- **WHEN** reviewed evidence proves the reference calibration geometry was
  non-overlapping and transport-equivalent under the corrected topology and a
  human explicitly accepts the same numerical factor with a v5 binding
- **THEN** absolute-dose preparation may use that numerical value without
  claiming that overlapping cases are dose-equivalent

#### Scenario: Calibration equivalence is not accepted

- **WHEN** disjointness or transport equivalence cannot be established or the
  required human acceptance is absent
- **THEN** the workflow leaves absolute dose fail-closed until suitable v5
  calibration evidence or a newly accepted factor is available

### Requirement: Calibration Reacceptance Evidence Shall Respect the Validation Boundary

Automated calibration-binding tests SHALL use synthetic geometry and fake or
mock external-tool boundaries. Any real DICOM inspection, PHITS calculation,
or numerical dose comparison for factor reacceptance SHALL require separate
explicit human approval and MUST NOT be committed with protected data.

#### Scenario: Repository calibration-binding regression

- **WHEN** stale and accepted topology bindings are tested automatically
- **THEN** synthetic evidence proves fail-closed behavior without real DICOM or
  external scientific execution
