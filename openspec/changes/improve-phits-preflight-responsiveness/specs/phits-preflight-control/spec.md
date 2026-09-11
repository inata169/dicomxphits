## ADDED Requirements

### Requirement: Owned Preflight Progress

The controller SHALL acquire exclusive workspace ownership and publish strict
invocation-bound preflight evidence before enumerating the configured runtime
tree. It SHALL report preparation and verification phases and measured scanned
file/byte counts without claiming PHITS progress, a known total, or success.
Progress MUST NOT grant execution, retry or downstream authority.

#### Scenario: Large configured installation

- **WHEN** binding capture takes longer than a normal GUI refresh
- **THEN** owned preparation progress is available before the scan completes and the GUI event loop remains responsive

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
- **THEN** scanning ends at a checkpoint without completing the tree, no PHITS starts, and downstream remains disabled

#### Scenario: Commitment wins the race

- **WHEN** a child is committed before preparation cancellation is accepted
- **THEN** cancellation is rejected without terminating or signalling the child

### Requirement: Checkpointed Verification Without Weaker Binding

Enumeration SHALL check control before each entry/open and hashing SHALL check
between reads of at most 1 MiB. Required membership and SHA-256 checks MUST
remain intact for execution, retained results and terminal result validation.
Acknowledged segment stopping MUST prevent later commitments but MUST NOT
interrupt required validation/publication of committed or retained results.
Blocked I/O MUST NOT be represented as accepted cancellation or trigger a kill.

#### Scenario: Stop arrives during result verification

- **WHEN** a valid owned boundary request arrives during a yielding scan
- **THEN** it is acknowledged at a checkpoint and prevents another commitment while required result checks continue

#### Scenario: Runtime mutation preserves file metadata

- **WHEN** bound bytes change without a size or timestamp change
- **THEN** SHA-256 validation still detects the mismatch and prevents reuse or successful publication

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
