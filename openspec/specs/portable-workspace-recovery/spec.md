# portable-workspace-recovery Specification

## Purpose

Define fail-closed inspection and downstream recovery for an explicitly
selected existing 3D-CRT workspace after GUI restart or bounded relocation,
while preserving verified PHITS segment outputs and historical artifacts.

## Requirements
### Requirement: Explicit Bounded Workspace Relocation

The workflow SHALL inspect a relocated workspace only after the user explicitly
selects an existing workspace root. It SHALL consider a recorded absolute path
eligible for relocation only when that path is below the summary's recorded
former workspace root, and SHALL map it only to the same relative path below
the selected current workspace root. It MUST NOT search for artifacts, match by
basename alone, or automatically rebind a recorded path that was external to
the former workspace.

#### Scenario: Workspace moved between computers

- **WHEN** an existing workspace is selected at a different absolute root and
  a recorded artifact was below the former workspace root
- **THEN** inspection evaluates the artifact only at the equivalent relative
  path below the selected current root

#### Scenario: Recorded external path

- **WHEN** a summary records a licensed tool, source input, or other path
  outside the former workspace root
- **THEN** relocation does not search for or automatically substitute that
  path and requires the applicable explicit current-computer input

#### Scenario: Ambiguous or escaping path

- **WHEN** a path cannot be proven to be below the former root or its mapped
  candidate escapes the selected current workspace
- **THEN** inspection rejects that evidence without reading an unrelated path

### Requirement: Relocated Evidence Revalidation

The workflow SHALL classify relocated stage evidence as current and verified,
historical and recoverable, or invalid and incomplete. Current and verified
evidence MUST include every stage-required artifact at its accepted current
path, matching SHA-256 evidence wherever the public workflow records a digest,
and all existing stage-specific provenance gates. A success value in a copied
summary alone MUST NOT establish current completion.

#### Scenario: Relocated artifact matches recorded evidence

- **WHEN** every required in-workspace artifact exists at its bounded mapped
  path and matches its recorded digest and provenance
- **THEN** the workflow may accept that evidence as current and verified

#### Scenario: Successful summary points to missing output

- **WHEN** a copied summary reports success but its required current output is
  absent
- **THEN** the workflow classifies the stage as historical and recoverable or
  invalid and incomplete, and does not present it as currently completed

#### Scenario: Relocated artifact digest differs

- **WHEN** a required current artifact differs from its recorded SHA-256
- **THEN** the workflow fails closed and does not unlock a dependent external
  stage

### Requirement: Verified PHITS Reuse and Fresh Downstream Evidence

The workflow SHALL allow a relocated workspace's PHITS segment outputs to be
reused without PHITS execution only when the strict manifest, complete active
segment output set, a recorded SHA-256 for every active segment output, and the
current IEC gantry-geometry contract validate at the current workspace. A
legacy manifest without that contract MAY remain reusable only when every
active segment explicitly records gantry zero, whose source and transform
geometry is unchanged by the correction. Missing, ambiguous, or nonzero-angle
legacy gantry provenance MUST fail closed and require newly prepared segment
inputs followed by PHITS, Sumtally, and RTDOSE recalculation.

Missing SHA-256 evidence for any active segment output MUST fail closed and
MUST NOT be inferred from file existence, path binding, or a successful
execution summary. Recovery SHALL regenerate Sumtally and RTDOSE evidence under
the current workspace and SHALL retain the existing requirement that an
external run create a new output or change its SHA-256. It MUST NOT silently
delete a conflicting historical artifact or accept unchanged bytes as a fresh
result. It MUST NOT treat a final-DICOM mirror, affine rewrite, or coordinate
relabel as repair for transport made with the prior nonzero-angle convention.

With explicit recovery permission, it SHALL move conflicting downstream
summaries and artifacts into a new
`recovery_history/<unique-recovery-id>/` directory below the current workspace,
preserve their workspace-relative layout, and record a history manifest with
their original and preserved relative paths, sizes, and SHA-256 values. It MUST
fail before external execution if the history directory already exists or any
required preservation step fails, and MUST NOT move PHITS segment outputs.

#### Scenario: Verified relocated segment outputs

- **WHEN** all active PHITS segment outputs, their binding evidence, and their
  individually recorded SHA-256 values, and the current IEC gantry-geometry
  contract validate after bounded relocation
- **THEN** the user may start recovery at Sumtally Generate without rerunning
  PHITS

#### Scenario: Proven legacy all-zero-gantry workspace

- **WHEN** a legacy manifest lacks the current gantry contract but every active
  segment explicitly records gantry zero
- **THEN** recovery may reuse the unchanged PHITS transport after all existing
  digest and binding checks pass

#### Scenario: Legacy nonzero or ambiguous gantry workspace

- **WHEN** a legacy manifest contains a nonzero active gantry angle or does not
  provide enough angle provenance to prove every active segment used gantry
  zero
- **THEN** recovery rejects PHITS reuse and requires newly prepared inputs and
  PHITS and downstream recalculation

#### Scenario: Missing or changed segment output

- **WHEN** any active segment output is missing, lacks a recorded SHA-256, or
  differs from its recorded SHA-256 after relocation
- **THEN** the workflow rejects downstream recovery before Sumtally execution

#### Scenario: Conflicting historical downstream output

- **WHEN** recovery would write to a path containing a historical Sumtally or
  RTDOSE summary or artifact and the user grants explicit recovery permission
- **THEN** the workflow moves the conflict into a new workspace-local recovery
  history, records its relative-path and digest evidence, and leaves the
  original output path absent before execution

#### Scenario: Historical preservation fails

- **WHEN** a collision-safe recovery-history directory cannot be created or a
  conflicting downstream item cannot be preserved and recorded
- **THEN** recovery fails before external execution without deleting or
  overwriting that item

#### Scenario: Recovery produces unchanged output

- **WHEN** a recovery execution returns success but leaves the expected output
  bytes unchanged
- **THEN** the stage fails and records no fresh downstream provenance

### Requirement: Current-Computer Tool Binding

Portable recovery SHALL obtain PHITS, RT-PHITS, and phits2dicom roles from the
current computer's explicitly validated tool profile. It MUST NOT treat an
executable path copied from a former computer as a portable artifact or as
authority to launch a program.

#### Scenario: Receiving computer has a valid local profile

- **WHEN** relocated evidence is valid and the receiving computer's applicable
  tool roles validate
- **THEN** a human-authorized recovery stage uses and records those current
  tool paths

#### Scenario: Only former-computer tool paths are available

- **WHEN** copied summaries contain executable paths but no applicable local
  tool profile validates
- **THEN** dependent execution remains disabled

### Requirement: Synthetic Portable-Recovery Validation Boundary

Automated portable-workspace validation SHALL use copied temporary synthetic
workspaces, placeholder roots, synthetic DICOM, and fake or mock external-tool
runners. It MUST NOT use real DICOM, licensed distributions, or real PHITS,
Sumtally, phits2dicom, or GPR execution.

#### Scenario: Automated relocation test

- **WHEN** relocation, path rebinding, recovery, or failure handling is tested
- **THEN** all workspace artifacts and external-tool results are synthetic or
  mocked and remain in test-controlled temporary directories
