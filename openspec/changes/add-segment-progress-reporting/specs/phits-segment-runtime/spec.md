## ADDED Requirements

### Requirement: Durable Segment-Boundary Progress Evidence

Direct PHITS segment execution SHALL atomically write a strict versioned
execution record before the first active segment starts, before each active
segment starts, after each active segment result is validated, and at terminal
success or failure. The record SHALL identify one invocation, bind to the
current manifest, distinguish pending, running, successful, skipped, failed,
and gate-failed segment states, and record the current active segment and
validated results completed by that invocation.

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

- **WHEN** a multi-segment invocation starts and its first segment passes every
  accepted output and geometry check
- **THEN** the execution record progresses atomically from an initial running
  state, through the current first segment, to one validated completed segment
  before the next segment is launched

#### Scenario: Later segment fails

- **WHEN** an earlier segment succeeded and a later segment fails execution or
  accepted output validation
- **THEN** the terminal failure record retains the earlier segment's validated
  result, records the later failure, and does not authorize Sumtally

#### Scenario: Controlling process is interrupted

- **WHEN** execution ends without writing a terminal transition
- **THEN** the last complete atomic record may retain earlier validated segment
  results but remains incomplete and cannot authorize Sumtally or PHITS reuse

#### Scenario: Progress persistence fails

- **WHEN** a required progress transition cannot be written safely
- **THEN** no later segment is launched and no overall success is recorded

### Requirement: Segment Timing and Estimate Inputs

The execution record SHALL contain UTC start and update timestamps, nonnegative
elapsed duration, and a nonnegative duration for each completed active segment.
Elapsed and segment durations MUST be measured with a monotonic clock. Pending,
failed, and skipped segments MUST NOT contribute a successful-segment duration
to remaining-time estimation.

Before one active segment completes successfully, remaining time SHALL be
unavailable. Afterward, the estimate SHALL use the arithmetic mean of validated
successful active-segment durations. It SHALL account for every incomplete
active segment, subtract observed current-segment elapsed time from at most one
mean segment duration with a zero lower bound, and identify the result as an
estimate rather than measured completion evidence.

#### Scenario: No completed active segment

- **WHEN** execution has started but no active segment has completed
  successfully
- **THEN** elapsed time and current segment may be reported but remaining time
  and finish time are unavailable

#### Scenario: Estimate after completed segments

- **WHEN** successful active segments have durations and other active segments
  remain incomplete
- **THEN** remaining time is derived from their arithmetic mean and the
  incomplete workload and is explicitly approximate

#### Scenario: System clock changes

- **WHEN** the system wall clock changes during an invocation
- **THEN** measured elapsed and segment durations remain nonnegative because
  they use a monotonic clock

### Requirement: Compatible Segment Execution Summary Versions

Segment-summary readers SHALL continue to accept a valid terminal-success
`dicomxphits_public_segment_execution_v2` record under its existing evidence
checks. They SHALL accept a version-3 record only when its stricter invocation,
progress, timing, manifest, output-digest, and geometry-evidence structure is
valid. Inspection MUST NOT rewrite or infer missing version-3 fields for a
version-2 record, and unknown versions MUST fail closed.

#### Scenario: Existing version-2 success record

- **WHEN** a valid version-2 terminal success summary satisfies its existing
  manifest, output, digest, and geometry checks
- **THEN** existing downstream inspection may accept it without rewriting it

#### Scenario: Incomplete version-3 record

- **WHEN** a structurally valid version-3 record reports running or another
  non-success overall state
- **THEN** readers may display its progress but do not authorize Sumtally or
  PHITS reuse

#### Scenario: Unknown summary version

- **WHEN** a segment execution record declares an unsupported schema version
- **THEN** readers fail closed without inferring compatibility from its fields
