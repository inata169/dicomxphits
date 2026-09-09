## MODIFIED Requirements

### Requirement: Durable Segment-Boundary Progress Evidence

Direct PHITS segment execution SHALL atomically write a strict versioned
execution record before the first active segment starts, before each active
segment starts, after each active segment result is validated, and at terminal
success, user stopping, or failure. The record SHALL identify one invocation,
bind to the current manifest, distinguish pending, running, successful, skipped,
failed, and gate-failed segment states, and record the current active segment
and validated results completed by that invocation. Selective execution SHALL
identify retained results separately, preserving their producing invocation and
original timing without counting them as work measured in the new invocation.

Each recorded successful segment MUST retain accepted output paths, SHA-256
bindings, and geometry-clean evidence required by the existing execution
contract. Pending or running segments MUST NOT contain fabricated success
evidence. Failure to persist a required transition MUST prevent another launch.

Only a terminal record whose overall status is `success` and whose active
segments all satisfy accepted successful-segment evidence MAY authorize Sumtally
or PHITS reuse. Running, interrupted, stopped, pending, failed, gate-failed,
malformed, stale-invocation, or unknown-version records MUST remain incomplete
and MUST NOT authorize a downstream stage.

#### Scenario: Segment transitions are persisted

- **WHEN** a multi-segment invocation starts and its first segment passes all output and geometry checks
- **THEN** the record progresses through current-segment execution to one validated new completion before the next launch

#### Scenario: Later segment fails

- **WHEN** earlier segments succeeded and a later segment fails execution or validation
- **THEN** the record retains verified results and records failure without authorizing Sumtally

#### Scenario: Controlling process is interrupted

- **WHEN** execution ends without a durable terminal transition
- **THEN** the last atomic record retains results but remains incomplete for downstream use

#### Scenario: Progress persistence fails

- **WHEN** a required transition cannot be persisted safely
- **THEN** no later segment launches and no overall success or verified stop is fabricated

#### Scenario: Success is retained from an earlier attempt

- **WHEN** selective execution revalidates an earlier success
- **THEN** its producing invocation and timing remain intact and distinct from new completions

#### Scenario: User stops with work remaining

- **WHEN** a request is acknowledged and the current segment finishes with valid evidence
- **THEN** the controller persists stopped with remaining entries pending and downstream disabled

### Requirement: Compatible Segment Execution Summary Versions

Segment-summary readers SHALL continue accepting valid v2 terminal-success,
v3 progress/terminal, and v4 execution-binding records under their established
checks without rewriting them. They SHALL accept
`dicomxphits_public_segment_execution_v5` only when strict invocation, progress,
timing, binding, retained-result provenance, manifest, output digest, geometry,
and stop-state evidence validate. Selective execution MUST require eligible v4
or v5 evidence captured before the originating execution; current file hashes
MUST NOT substitute for missing historical evidence. Unknown versions MUST
fail closed.

#### Scenario: Existing version-2 success record

- **WHEN** a valid v2 terminal success satisfies its existing evidence checks
- **THEN** downstream inspection may accept it without rewriting it or granting selective execution

#### Scenario: Incomplete version-3 record

- **WHEN** a valid v3 record is running or incomplete
- **THEN** readers may display progress but cannot authorize downstream stages or selective execution

#### Scenario: Version-4 retry record

- **WHEN** a v4 record mixes retained and newly produced successes
- **THEN** readers preserve its existing provenance and binding checks and require fresh complete terminal success for downstream use

#### Scenario: Version-5 stopped record

- **WHEN** a valid v5 record is user-stopped with pending active work
- **THEN** readers can offer explicit validated retry but cannot authorize downstream stages

#### Scenario: Unknown summary version

- **WHEN** an execution record declares an unsupported version
- **THEN** readers reject it without inferring compatibility from its fields
