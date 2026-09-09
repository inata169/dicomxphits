## MODIFIED Requirements

### Requirement: Durable Segment-Boundary Progress Evidence

Direct PHITS segment execution SHALL atomically write a strict versioned
execution record before the first active segment starts, before each active
segment starts, after each active segment result is validated, and at terminal
success or failure. The record SHALL identify one invocation, bind to the
current manifest, distinguish pending, running, successful, skipped, failed,
and gate-failed segment states, and record the current active segment and
validated results completed by that invocation. Selective execution SHALL also
identify retained results separately, preserving their producing invocation and
original timing without counting them as work measured in the new invocation.

Each recorded successful segment MUST retain the accepted output paths,
SHA-256 bindings, and geometry-clean evidence required by the existing
execution contract. A pending or running segment MUST NOT contain fabricated
success evidence. Failure to persist a required transition MUST stop execution
before another segment is launched.

Only a terminal record whose overall status is `success` and whose active
segments all satisfy the accepted successful-segment evidence MAY authorize
Sumtally or PHITS reuse. A running, interrupted, pending, failed, gate-failed,
malformed, stale-invocation, or unknown-version record MUST remain incomplete
and MUST NOT authorize a downstream stage.

#### Scenario: Segment transitions are persisted

- **WHEN** a multi-segment invocation starts and its first segment passes every accepted output and geometry check
- **THEN** the record progresses from running through the current segment to one validated new completion before the next segment starts

#### Scenario: Later segment fails

- **WHEN** earlier segments succeeded and a later segment fails execution or validation
- **THEN** the record retains verified results and records failure without authorizing Sumtally

#### Scenario: Controlling process is interrupted

- **WHEN** execution ends without writing a terminal transition
- **THEN** the last atomic record retains durable results but remains incomplete for downstream use

#### Scenario: Progress persistence fails

- **WHEN** a required transition cannot be persisted safely
- **THEN** no later segment is launched and no overall success is recorded

#### Scenario: Success is retained from an earlier attempt

- **WHEN** selective execution revalidates an earlier successful result
- **THEN** its producing invocation and timing remain intact and are distinct from newly measured completions

### Requirement: Compatible Segment Execution Summary Versions

Segment-summary readers SHALL continue accepting valid v2 terminal-success and
v3 progress/terminal records under their established checks without rewriting
them. They SHALL accept `dicomxphits_public_segment_execution_v4` only when its
strict invocation, progress, timing, execution binding, retained-result
provenance, manifest, output digest, and geometry evidence validate. Selective
execution MUST require v4 evidence captured before the originating execution;
current file hashes MUST NOT be substituted for missing historical evidence.
Unknown versions MUST fail closed.

#### Scenario: Existing version-2 success record

- **WHEN** a valid v2 terminal success satisfies its existing manifest, output, digest, and geometry checks
- **THEN** downstream inspection may accept it without rewriting it or granting selective execution

#### Scenario: Incomplete version-3 record

- **WHEN** a valid v3 record is running or otherwise incomplete
- **THEN** readers may display progress but cannot authorize downstream stages or selective execution

#### Scenario: Version-4 retry record

- **WHEN** a v4 record contains a mixture of retained and newly produced successes
- **THEN** readers validate their provenance and binding, and require fresh complete terminal success for downstream use

#### Scenario: Unknown summary version

- **WHEN** an execution record declares an unsupported version
- **THEN** readers reject it without inferring compatibility from its fields
