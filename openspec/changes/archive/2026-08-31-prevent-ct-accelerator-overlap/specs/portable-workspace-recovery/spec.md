# portable-workspace-recovery Delta

## MODIFIED Requirements

### Requirement: Verified PHITS Reuse and Fresh Downstream Evidence

The workflow SHALL allow a relocated workspace's PHITS segment outputs to be
reused without PHITS execution only when the strict manifest, complete active
segment output set, a recorded SHA-256 for every active segment output, the
current v5 IEC gantry/MLCX/collimator/CT-accelerator topology contract, and
geometry-clean runtime evidence validate at the current workspace.

Any v4, v3, older, missing, mixed, or ambiguous geometry provenance MUST fail
closed regardless of recorded gantry, collimator, MLC, field, FOV, or apparent
non-overlap values. Recovery MUST require newly prepared v5 segment inputs
followed by PHITS, Sumtally, and RTDOSE recalculation. It MUST NOT provide an
angle-, field-, FOV-, or overlap-dependent exception for a workspace produced
under an earlier geometry contract.

Missing SHA-256 evidence for any active segment output or missing, ambiguous,
or non-clean PHITS geometry-diagnostic evidence MUST fail closed and MUST NOT
be inferred from file existence, path binding, or a successful execution
summary. Recovery SHALL regenerate Sumtally and RTDOSE evidence under the
current workspace and SHALL retain the existing requirement that an external
run create a new output or change its SHA-256. It MUST NOT silently delete a
conflicting historical artifact or accept unchanged bytes as a fresh result.
It MUST NOT treat a final-DICOM mirror, rotation, affine rewrite, coordinate
relabel, geometry-version relabel, or CT crop as repair for stale transport.

With explicit recovery permission, it SHALL move conflicting downstream
summaries and artifacts into a new
`recovery_history/<unique-recovery-id>/` directory below the current workspace,
preserve their workspace-relative layout, and record a history manifest with
their original and preserved relative paths, sizes, and SHA-256 values. It MUST
fail before external execution if the history directory already exists or any
required preservation step fails, and MUST NOT move PHITS segment outputs.

#### Scenario: Verified relocated v5 segment outputs

- **WHEN** all active PHITS segment outputs, their binding evidence, their
  individually recorded SHA-256 values, the current v5 combined geometry
  contract, and zero-error PHITS geometry diagnostics validate after bounded
  relocation
- **THEN** the user may start recovery at Sumtally Generate without rerunning
  PHITS

#### Scenario: Prior v4 workspace

- **WHEN** a workspace carries the v4 gantry/MLCX/collimator geometry contract
- **THEN** recovery rejects PHITS reuse and requires newly prepared v5 inputs
  and complete downstream recalculation

#### Scenario: Prior workspace appears unaffected

- **WHEN** a pre-v5 workspace records zero angles or apparently disjoint CT and
  accelerator bounds
- **THEN** recovery still rejects PHITS reuse without an angle-, FOV-, or
  non-overlap exception

#### Scenario: Older or ambiguous geometry provenance

- **WHEN** geometry provenance is older than v4, missing, mixed, or ambiguous
- **THEN** recovery rejects PHITS reuse and requires newly prepared inputs and
  PHITS and downstream recalculation

#### Scenario: Missing or changed segment output

- **WHEN** any active segment output is missing, lacks a recorded SHA-256, or
  differs from its recorded SHA-256 after relocation
- **THEN** the workflow rejects downstream recovery before Sumtally execution

#### Scenario: Missing geometry-clean runtime evidence

- **WHEN** an otherwise complete segment lacks unambiguous zero-error PHITS
  geometry diagnostics
- **THEN** recovery rejects PHITS reuse before Sumtally execution

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
