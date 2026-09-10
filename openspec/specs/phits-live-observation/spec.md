# phits-live-observation Specification

## Purpose

Provide optional, read-only batch and per-cell relative-error observations for
owned PHITS 3.35 Windows OpenMP segments without changing calculation inputs,
execution authority, completion evidence or downstream safety gates.

## Requirements

### Requirement: Owned Non-Authoritative Observation

The controller SHALL optionally publish bounded, atomic presentation data at
`analysis/phits_observation.json` using schema `dicomxphits_phits_observation_v1`,
bound to its workspace, invocation, current segment generation and input/runtime
identity. It MUST read only expected regular files in its owned staging and
reject links, reparse points and path escapes. Missing or invalid observation
MUST NOT authorize or prevent execution, retry, stopping or downstream use.
Existing mandatory execution evidence and v2-v5 summary contracts SHALL remain
unchanged. Observation MUST NOT modify PHITS inputs, outputs, batch control,
parameters, process signals or lease ownership.

#### Scenario: Low error or zero remaining batches

- **WHEN** an observation reports low relative error or zero remaining batches
- **THEN** no segment is marked complete and no downstream gate is unlocked without existing terminal-success evidence

#### Scenario: Observer fails

- **WHEN** sampling, parsing or sidecar publication fails
- **THEN** detail becomes unavailable without changing the PHITS outcome or weakening mandatory evidence validation

#### Scenario: Old or unsafe observation source

- **WHEN** a source belongs to another invocation, retired staging or an unsafe path
- **THEN** it is not sampled or adopted as current observation

### Requirement: Explicit Supported Batch Observation

Observation SHALL support only positively identified PHITS 3.35 Windows OpenMP
output with reviewed syntax and bound prepared runtime values. A filename or
layout alone MUST NOT establish version compatibility. The GUI SHALL show
observed remaining batches and prepared total separately, requiring an integer
remaining count between zero and the prepared total and rejecting within-run
regressions. It MUST NOT derive completion, histories, percent progress or ETA
from that counter. Other modes, versions or unrecognized records SHALL report
unsupported without changing the simulation.

#### Scenario: Supported counter

- **WHEN** a complete supported record reports 7 remaining against a prepared budget of 10
- **THEN** the GUI labels these as observed remaining and prepared total, not 3 verified completed batches

#### Scenario: Version or counter is ambiguous

- **WHEN** identity is absent, syntax is unknown, or the counter is contradictory
- **THEN** batch detail is unavailable rather than inferred from a filename or fragment

### Requirement: Descriptive Current-Segment Relative Error

Observation SHALL use only a complete matching dose/error pair for the current
generated 3D dose tally, covering every mesh cell and slice. Mesh, tally role,
particle, output mode and available history/restart metadata MUST agree.
It SHALL report full-mesh total, valid and excluded cell counts, valid coverage,
and median/maximum relative error as percent for cells with finite positive
dose and finite positive relative error. Zero dose or error SHALL be excluded
once and labelled unevaluable; negative, malformed or non-finite values SHALL
invalidate the sample. Positive errors above 100 percent MUST NOT be clipped.
An empty valid set SHALL display unavailable, not zero error. These metrics
MUST NOT be described as ROI, combined-dose or clinical uncertainty or used for
convergence or automatic stopping. Tally and variance settings MUST NOT change.

#### Scenario: Mixed evaluable and zero cells

- **WHEN** a complete pair has positive valid cells and cells with zero dose or zero error
- **THEN** statistics use only valid cells and disclose excluded count and coverage without claiming precision for excluded cells

#### Scenario: Incomplete or mismatched pair

- **WHEN** a slice is missing or dose and error metadata disagree
- **THEN** no new relative-error statistic is published

#### Scenario: No evaluable cells

- **WHEN** all cells are excluded
- **THEN** statistics are unavailable and not represented as zero percent error

### Requirement: Bounded Provisional Snapshots and Reset

Sampling SHALL run off the GUI thread, no faster than once per second, with one
in-flight job, one latest-result slot, bounded file/token/cell sizes and a
cooperative two-second deadline. Batch/header reads SHALL be at most 64 KiB,
each tally at most 256 MiB, tokens at most 64 characters, cells at most
10,000,000, and sidecars at most 64 KiB. Limit failures SHALL disable detail only.
Samples SHALL require complete supported syntax, stable before/after file
metadata and agreement across two successive observations; they MUST still be
labelled provisional, never atomic PHITS results. Batch/error sample ages SHALL
remain independent. Unchanged values MUST NOT receive a new sample timestamp.
After five seconds without a new accepted sample the GUI SHALL mark it stale.
Transitions, new invocations, workspace changes and owner loss MUST clear live
observation; delayed workers MUST NOT republish retired-generation data.

#### Scenario: Writer replaces or truncates a tally

- **WHEN** bytes or file identity change during sampling or a record is incomplete
- **THEN** the GUI shows updating/unavailable or explicitly stale prior values, never a new mixed snapshot

#### Scenario: Late worker after segment transition

- **WHEN** a completed sampling job refers to the previous segment generation
- **THEN** its result is discarded without replacing current observation

#### Scenario: Large or slow source

- **WHEN** a sampling resource limit is reached
- **THEN** the job yields unavailable and the GUI remains responsive without controlling PHITS
