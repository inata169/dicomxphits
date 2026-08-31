# iec-gantry-geometry Delta

## ADDED Requirements

### Requirement: V5 Transport Geometry Shall Bind CT and Accelerator Topology

Newly prepared public fixed-field workspaces SHALL carry one current v5
combined transport-geometry contract that includes IEC gantry, MLCX,
collimator, and mutually exclusive CT/accelerator topology semantics. The v5
identity SHALL be recorded consistently in workspace, segment, and transport
evidence.

PHITS evidence created under v4, v3, or any older contract MUST NOT be accepted
as v5 transport. Missing, mixed, or ambiguous geometry provenance MUST fail
closed. No field-size, FOV, gantry-angle, collimator-angle, or analytical
non-overlap exception SHALL permit reuse of pre-v5 transport.

#### Scenario: V4 workspace is opened after the topology correction

- **WHEN** workspace evidence identifies PHITS results produced under the v4
  gantry/MLCX/collimator contract
- **THEN** the workflow does not present those results as reusable v5 transport
- **AND** it requires newly prepared v5 inputs and PHITS and downstream
  recalculation

#### Scenario: Prior workspace appears non-overlapping

- **WHEN** a pre-v5 workspace records geometry that appears disjoint or uses
  zero gantry and collimator angles
- **THEN** the workflow still rejects its PHITS evidence for v5 reuse because
  it lacks corrected topology and geometry-clean runtime evidence

### Requirement: V5 Topology Correction Shall Preserve Independent Geometry Contracts

The v5 topology correction SHALL NOT change the existing IEC gantry or
collimator direction, source position and direction, accelerator transform,
jaw or MLC aperture, CT coordinate mapping, SAD/SSD interpretation, source
spectrum, materials, transport settings, tally definitions, MU semantics,
Sumtally normalization, or RTDOSE mapping, except that an actual overlapping
CT region is removed from accelerator ownership conflict.

#### Scenario: V5 implementation diff is reviewed

- **WHEN** the implementation and synthetic outputs are compared with v4
- **THEN** unrelated beam, DICOM, dose, and coordinate contracts remain
  unchanged
- **AND** overlapping cases are identified as corrected calculations whose
  field shape and dose may differ from invalid pre-v5 transport
