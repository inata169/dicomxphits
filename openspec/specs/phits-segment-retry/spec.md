# phits-segment-retry Specification

## Purpose

Define explicit selective execution of incomplete PHITS segments while
preserving verified successes, binding new launches to the selected executable
and workspace evidence, and keeping incomplete or invalid results ineligible
for Sumtally and downstream processing.

## Requirements
### Requirement: Explicit Incomplete Segment Plan

The workflow SHALL provide a read-only plan and an explicit selective execution
action for a selected workspace. A plan MUST list retained successful segments,
incomplete active targets, and skipped entries by their unique manifest identity.
It MUST NOT launch a process, mutate artifacts, or infer eligibility from file
existence. Execution SHALL revalidate the plan and its source evidence before
mutation; changed evidence or selection MUST require a new plan.

#### Scenario: Partial valid calculation

- **WHEN** a retry-capable record contains verified successes and incomplete active segments
- **THEN** the plan lists both sets and schedules only the incomplete entries in manifest order

#### Scenario: Nothing remains

- **WHEN** every active segment has current valid success evidence
- **THEN** the action launches no process, preserves the record, and defers downstream authorization to existing gates

### Requirement: Complete Execution Binding for Retry

Retry SHALL require evidence captured before the original execution that binds
the current manifest, all workspace-local segment inputs, preparation/model/
calibration identity, effective runtime settings and relevant environment, and
the explicitly configured PHITS executable's resolved path and SHA-256. The
controller MUST NOT recursively enumerate or hash the configured PHITS
installation. Bound workspace file membership and SHA-256 values MUST match,
and the selected executable MUST pass its path/file checks and match its bound
SHA-256 immediately before every new child commitment. New retry evidence SHALL
identify the bounded executable scope. Historical installation-tree evidence
MUST NOT be rewritten or represented as newly verified bounded evidence.

Retained successes MUST additionally have every required output with its
recorded digest, zero return code and geometry-clean evidence. Every declared
primary output remains required, while only the manifest-selected primary 3D
dose output requires a separate statistical-error companion. An optional error
companion for another declared output is immutable evidence when present.
`batch.out` is mutable control/progress state and MUST NOT be a required output
or immutable digest gate. Any other missing or mismatched required evidence
SHALL reject the entire retry before execution and advise preparing a new
workspace.

#### Scenario: Input changes while output remains intact

- **WHEN** any bound workspace input, include, model, calibration, runtime
  setting, environment or selected executable identity changes
- **THEN** selective execution is rejected before launching any segment

#### Scenario: Installation sibling changes

- **WHEN** a file other than the selected executable changes in the configured
  installation while all bounded evidence remains valid
- **THEN** retry does not enumerate or hash that sibling and does not reject on
  an installation-wide mutation claim

#### Scenario: Mutable batch control changes

- **WHEN** a retained segment's `batch.out` content or remaining-batch value
  changes while every required immutable result still matches
- **THEN** that content change alone does not reject retry or authorize success

#### Scenario: Retry source has historical installation-tree evidence

- **WHEN** otherwise eligible v4 or v5 source evidence records the older
  installation-wide binding
- **THEN** the source remains unchanged, the current selected executable and
  workspace evidence are freshly validated without scanning the installation,
  and any new attempt records the bounded executable scope

#### Scenario: Previously successful segment is damaged

- **WHEN** a success lacks a required output, matching digest or clean geometry
  evidence
- **THEN** retry rejects the plan rather than silently recalculating that segment

#### Scenario: Older summary or moved workspace

- **WHEN** a source is v2/v3, lacks retry evidence, or differs from the recorded
  resolved root
- **THEN** selective execution is unavailable without rewriting or migrating the
  source record

### Requirement: Preserved Results and Independent Retry Attempts

Selective execution SHALL preserve verified successful artifacts and immutable
source-attempt evidence. Each retry SHALL have a new invocation ID and recorded
parent evidence digest. Retained entries MUST retain their original producer and
timing; only incomplete active entries MAY be executed, from the beginning in
fresh staging. A target write or cleanup set overlapping a retained artifact or
bound input MUST reject the attempt before mutation. Old staging MUST NOT be
promoted or consumed, and partial tallies MUST NOT be accumulated.

#### Scenario: Retry succeeds

- **WHEN** incomplete segments finish with valid evidence
- **THEN** retained artifact bytes and modification times are unchanged and new results have the new attempt identity

#### Scenario: Retry fails again

- **WHEN** a later retry segment fails
- **THEN** prior verified entries and source attempt evidence survive, while overall evidence stays incomplete

#### Scenario: Unsafe publication or evidence preservation

- **WHEN** outputs collide, paths escape containment, or source evidence cannot be preserved
- **THEN** no segment starts and no retained artifact is replaced

### Requirement: Exclusive Workspace Execution Ownership

Ordinary and selective PHITS execution SHALL share exclusive ownership of the
resolved workspace across GUI and CLI processes. Ownership MUST cover preflight
through final publication, including any surviving child capable of writing.
Conflicting repository-controlled workspace mutations MUST be rejected while
ownership is active. Uncertain ownership SHALL fail closed without automatic
lock deletion, process termination, or timeout-based takeover.

#### Scenario: Second process starts

- **WHEN** another GUI or CLI owns execution for the same workspace
- **THEN** the second attempt starts no child and changes no execution evidence

#### Scenario: Controller exits before its child

- **WHEN** the controller ends but its PHITS child may still be writing
- **THEN** another attempt cannot take ownership until safe release is established

### Requirement: Complete Unique Downstream Evidence After Retry

The workflow SHALL authorize downstream processing after retry only when fresh
terminal success validates exactly one successful result for every active segment.
Retained and new results MUST be revalidated against the same execution binding.
Current incomplete or invalid evidence MUST take precedence over historical
downstream success. Sumtally MUST NOT include a segment twice or incorporate
intermediate statistics. Existing downstream preservation permissions remain
separate from selective PHITS execution.

#### Scenario: Some retained and some newly completed segments

- **WHEN** the union covers every unique active segment and passes fresh full validation
- **THEN** downstream gates may accept one terminal success with each active segment counted once

#### Scenario: Partial or duplicated result set

- **WHEN** any active segment is incomplete or identities are duplicated or inconsistent
- **THEN** Sumtally and downstream recovery remain disabled regardless of old success summaries
