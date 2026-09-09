## ADDED Requirements

### Requirement: Owned Segment-Boundary Stop Request

The controller SHALL accept an explicit stop-after-current request only for its own active retry-capable invocation, bound to its resolved workspace and run identity.
Acceptance and segment launch MUST be serialized. Once accepted, no later
segment may be committed to launch; the currently committed segment, if any,
SHALL finish normally without a stop-induced kill, signal, timeout change, or
release of workspace ownership. Repeated accepted requests SHALL be idempotent.
Invalid or stale requests MUST NOT alter invocation state.

#### Scenario: Request during a segment

- **WHEN** the owner acknowledges a valid request while one segment is executing
- **THEN** that segment finishes and is validated, and no following segment starts

#### Scenario: Request races with launch

- **WHEN** request acceptance and the next segment launch contend
- **THEN** their serialized ordering determines whether that segment is current, and the acknowledgement identifies the resulting boundary

#### Scenario: No current segment

- **WHEN** a valid request is accepted before the first launch or between segments with work remaining
- **THEN** no further segment starts and the controller records the verified stopped boundary

#### Scenario: Stale or malformed request

- **WHEN** a request has wrong run/workspace identity, malformed or oversized content, or targets a terminal invocation
- **THEN** it cannot acknowledge stopping or modify execution evidence

### Requirement: Durable Stop State and Deterministic Outcome

The controller SHALL durably acknowledge a stop request before presenting it as accepted and SHALL record terminal user stopping only after current-segment validation and publication finish successfully.
Execution or evidence failure MUST take precedence over stopping. Fresh verified
all-active completion MUST be success, including overlap with a final-segment
stop request. Otherwise an acknowledged stop with pending work and no running
or failed entry SHALL yield `stopped`, preserving unstarted entries as pending.
Missing durable terminal evidence MUST NOT be presented as a safe stop.

#### Scenario: Current segment fails after request

- **WHEN** execution, geometry, binding, output publication, or required persistence fails with a stop pending
- **THEN** the controller starts no next segment and reports failure/incomplete evidence rather than user-stopped success

#### Scenario: Final segment completes

- **WHEN** all active entries validate successfully as a stop request arrives
- **THEN** the single terminal outcome is success, not stopped, and late requests cannot rewrite it

#### Scenario: Controller dies after acknowledgement

- **WHEN** the controller exits without a durable validated terminal transition
- **THEN** readers show interrupted/incomplete evidence, not verified user stopping, and surviving child ownership still prevents another execution

### Requirement: Versioned Stop Evidence and Explicit Retry

New stop-capable execution SHALL use strict v5 evidence preserving existing input/runtime/output binding and retained-result provenance, with acknowledged stop identity and timing.
Readers SHALL preserve existing v2/v3/v4 contracts and reject unknown versions.
Eligible v4 and v5 records MAY authorize the existing explicit selective retry
after full validation, without historical rewrites. Each retry MUST reset stop
state and retain successful artifacts unchanged. Stopped evidence MUST NOT
authorize downstream stages. The stopped CLI result SHALL have distinct exit
code 4 and MUST agree with validated stopped evidence.

#### Scenario: Resume a stopped invocation

- **WHEN** a user confirms a freshly validated incomplete-segment preview from a stopped attempt
- **THEN** a new invocation runs only pending work, preserves verified successes, and does not inherit the old stop request

#### Scenario: Mixed-version parent history

- **WHEN** eligible v4 evidence is retained by a v5 attempt and later retried
- **THEN** readers validate the full parent digest chain without upgrading or rewriting historical records

#### Scenario: Historical downstream success exists

- **WHEN** current evidence is stopped while old downstream summaries indicate success
- **THEN** downstream gates remain closed until fresh all-active terminal success validates

#### Scenario: Exit disagrees with summary

- **WHEN** exit code 4 lacks a matching valid stopped summary or the summary contradicts the exit
- **THEN** the GUI reports incomplete/error evidence, not confirmed user stopping
