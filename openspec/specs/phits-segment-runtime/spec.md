# PHITS Segment Runtime Specification

## Purpose

Define the explicit, auditable calculation-size and OpenMP controls applied to
newly prepared fixed-field PHITS segment inputs and direct segment execution.
## Requirements
### Requirement: Explicit Prepared Segment Runtime Parameters

Workspace preparation SHALL accept decimal positive integers for segment
`maxcas`, `maxbch`, and OpenMP thread count, defaulting to `1000000`, `10`, and
`8`. It SHALL validate them before creating or modifying workspace artifacts,
render the exact effective values into every active segment PHITS input, and
record them in preparation evidence. These parameters MUST NOT change the
fixed-field geometry, machine model, dose calibration, MU semantics, or
Sumtally inputs.

#### Scenario: Default CLI preparation

- **WHEN** workspace preparation is invoked without explicit runtime options
- **THEN** every active segment input contains `maxcas = 1000000`,
  `maxbch = 10`, and `$OMP = 8`, and the summary records those values

#### Scenario: Explicit CLI preparation

- **WHEN** workspace preparation receives valid explicit runtime options
- **THEN** every active segment input and the preparation summary contain the
  exact selected values

#### Scenario: Invalid CLI runtime value

- **WHEN** any runtime option is zero, negative, fractional, boolean, empty, or
  non-decimal text
- **THEN** preparation fails before creating or modifying workspace artifacts

### Requirement: Documented OpenMP Directive and Direct Execution

Generated segment inputs SHALL place `$OMP = N` before the first PHITS section,
where `N` is the validated positive OpenMP thread count. The direct segment
execution adapter SHALL pass the same value as `OMP_NUM_THREADS=N` to the PHITS
child process. It MUST reject a missing or malformed generated directive rather
than silently executing with an unrecorded thread setting.

#### Scenario: Prepared OpenMP segment execution

- **WHEN** the adapter executes a generated segment containing `$OMP = 12`
- **THEN** it directly launches the selected PHITS executable with
  `OMP_NUM_THREADS=12`

#### Scenario: Unsupported directive spelling

- **WHEN** a prepared segment contains `OMP = 12` without the documented
  dollar sign
- **THEN** the adapter rejects the input instead of treating it as the supported
  OpenMP directive

#### Scenario: Invalid generated thread count

- **WHEN** a generated `$OMP` directive has a missing, zero, negative, or
  non-integer value
- **THEN** the adapter rejects the input before launching PHITS

### Requirement: Segment Success Shall Require Geometry-Clean PHITS Evidence

The direct PHITS segment adapter SHALL accept a segment as successful only when
the process returns zero, all currently required outputs exist, and the staged
PHITS companion output contains one recognized and unambiguous geometry
diagnostic summary with zero `Number of lost particles`, `Number of geometry
recovering`, and `Number of unrecovered errors` counts. A missing, malformed,
duplicate, contradictory, or nonzero required
diagnostic summary SHALL fail the segment before its tally is published for
downstream use.

The execution evidence SHALL record the parsed diagnostic status and counts.
The parser SHALL use bounded numeric fields from reviewed summary records and
MUST NOT treat an unrelated textual occurrence of a geometry term as a count.

#### Scenario: PHITS returns zero with clean geometry

- **WHEN** a fake PHITS run returns zero, creates every required output, and
  supplies one recognized summary whose geometry counts are all zero
- **THEN** the adapter may publish the segment as successful and records the
  clean diagnostic evidence

#### Scenario: PHITS reports a geometry error

- **WHEN** a fake PHITS run returns zero and creates a tally but the recognized
  summary reports a nonzero lost-particle, geometry-recovering, or unrecovered
  error count
- **THEN** the adapter fails the segment and does not publish that tally for
  Sumtally

#### Scenario: Geometry summary is not provable

- **WHEN** the required geometry summary is missing, malformed, duplicated, or
  contradictory
- **THEN** the adapter fails closed even when the process return code is zero
  and an expected tally exists

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
