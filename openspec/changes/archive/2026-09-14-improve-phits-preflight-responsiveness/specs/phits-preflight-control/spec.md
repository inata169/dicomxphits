## ADDED Requirements

### Requirement: Owned Preflight Progress

The controller SHALL acquire exclusive workspace ownership and publish strict
invocation-bound preflight evidence before hashing bounded workspace inputs and
the explicitly selected PHITS executable. It SHALL report preparation and
verification phases and measured scanned file/byte counts without claiming
PHITS progress, a known total, installation membership or success. It MUST NOT
recursively enumerate or hash the configured PHITS installation. Progress MUST
NOT grant execution, retry or downstream authority.

#### Scenario: Large configured installation

- **WHEN** the selected installation contains many files unrelated to the
  explicitly selected executable
- **THEN** preparation does not enumerate or hash those siblings and reports
  only bounded executable/workspace work while the GUI remains responsive

### Requirement: Cancellation Before First Commitment

An explicit preparation cancellation SHALL be serialized with first child
commitment and bound to the owning workspace/run. Accepted cancellation MUST
prevent every child launch, abandon incomplete scan work, and persist a strict
`cancelled_before_launch` preflight receipt with distinct exit 5. It MUST NOT
fabricate v5 stopped evidence, result validity or retry eligibility.
If a child is already committed, preparation cancellation SHALL be rejected;
only existing separately requested segment-boundary stopping remains available.

#### Scenario: Cancel during initial hashing

- **WHEN** the owner accepts cancellation before first commitment
- **THEN** bounded hashing ends at a checkpoint, no PHITS starts, and downstream remains disabled

#### Scenario: Commitment wins the race

- **WHEN** a child is committed before preparation cancellation is accepted
- **THEN** cancellation is rejected without terminating or signalling the child

### Requirement: Selected Executable and Workspace-Scoped Binding

The controller SHALL bind the resolved absolute path and SHA-256 of the
explicitly selected PHITS executable without recursively enumerating or hashing
its installation. New execution evidence SHALL identify this bounded executable
scope. The controller SHALL recheck the selected executable as an accepted
regular file and match its bound path and SHA-256 immediately before every PHITS
child commitment. Workspace input, preparation, manifest, runtime-setting and
environment bindings SHALL retain their existing membership and SHA-256 checks.
Control SHALL be checked before each bounded file open and between hash reads of
at most 1 MiB. Blocked I/O MUST NOT be represented as accepted cancellation or
trigger a kill.

#### Scenario: Selected executable changes before commitment

- **WHEN** the selected executable is missing, replaced, unsafe or has a
  different SHA-256 immediately before a child commitment
- **THEN** that child does not start and the invocation cannot publish success

#### Scenario: Unrelated installation content changes

- **WHEN** a file other than the selected executable is added, removed or
  changed under the configured installation
- **THEN** execution binding does not enumerate or hash that file and makes no
  installation-wide mutation-detection claim

#### Scenario: Historical installation-wide evidence is read

- **WHEN** an existing v2-v5 summary contains historical installation-tree
  binding evidence
- **THEN** readers preserve its workspace/result meaning without rewriting it,
  while any new child launch records and validates the bounded executable scope

### Requirement: Mutable Batch Control Is Non-Authorizing

Each PHITS `batch.out` SHALL be treated as a mutable control/progress artifact.
It MAY be monitored or retained subject to existing workspace containment,
ownership and link protections, but its presence, content, remaining-batch
value or digest MUST NOT be required immutable result evidence or proof of
normal completion. Content mutation alone MUST NOT cause an artifact-mutation
error.

#### Scenario: User edits mutable batch control

- **WHEN** a user changes `0 <--- number of remaining batches` to
  `-1 <--- number of remaining batches` in `batch.out`
- **THEN** the byte change alone does not invalidate otherwise required result
  evidence and does not itself establish success or verified stopping

#### Scenario: Batch control exists without complete results

- **WHEN** `batch.out` exists or reports no remaining batches but a required
  output, zero exit, clean geometry, terminal summary or completion state is
  missing or invalid
- **THEN** the result remains incomplete or failed and downstream stays disabled

### Requirement: Checkpointed Verification Preserves Result Gates

Acknowledged segment stopping MUST prevent later commitments but MUST NOT
interrupt required validation/publication of committed or retained results.
Every declared primary output SHALL remain required. A separate statistical-
error companion SHALL be required for the manifest-selected primary 3D dose
output only; an optional error companion for any other declared output SHALL be
included in immutable result evidence when present. Process exit, geometry,
durable summary, stop/completion state, workspace ownership and downstream
eligibility checks SHALL remain authoritative. Mutable `batch.out` MUST NOT
replace or weaken any of these gates.

#### Scenario: Stop arrives during result verification

- **WHEN** a valid owned boundary request arrives during a yielding scan
- **THEN** it is acknowledged at a checkpoint and prevents another commitment while required result checks continue

#### Scenario: Bound workspace mutation preserves file metadata

- **WHEN** bound workspace input or required-result bytes change without a size
  or timestamp change
- **THEN** SHA-256 validation still detects the mismatch and prevents reuse or successful publication

#### Scenario: Secondary PDD embeds relative error

- **WHEN** every declared primary output exists, the selected 3D dose error
  companion exists, and a secondary PDD carries relative error in its primary
  output without a separate companion
- **THEN** the missing secondary companion alone does not invalidate the segment

#### Scenario: Incomplete or stopped result

- **WHEN** current evidence is incomplete, stopped, failed or unverified
- **THEN** it cannot be published as normal completion or passed to Sumtally

### Requirement: Non-Authorizing Preflight Recovery

Readers SHALL validate strict preflight identities and terminal receipts and
reject unknown versions. A current preflight or cancelled attempt MUST keep
downstream disabled even when historical success exists. Cancellation MUST
preserve source attempts and outputs and MUST NOT supply missing execution
binding. Continuation SHALL require fresh explicit preflight and, for selective
execution, a fresh plan against its unchanged original eligible parent.

#### Scenario: Cancellation precedes selective execution

- **WHEN** a selective attempt cancels before any child commitment
- **THEN** its source evidence stays unchanged and the cancellation receipt cannot authorize selective execution or Sumtally

#### Scenario: Controller dies before terminal publication

- **WHEN** no matching durable terminal receipt exists
- **THEN** recovery reports incomplete/interrupted evidence, not verified cancellation
