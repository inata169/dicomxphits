# Portable Workspace Recovery Delta

## MODIFIED Requirements

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

- **WHEN** all active PHITS segment outputs, their binding evidence, their
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
