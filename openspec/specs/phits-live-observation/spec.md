# phits-live-observation Specification

## Purpose

Provide optional, read-only remaining-batch and single Isocenter-voxel
relative-error observations for owned PHITS 3.35 Windows OpenMP segments
without changing calculation inputs, execution authority, completion evidence
or downstream safety gates.
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
manifest-selected primary 3D dose tally. Mesh, tally role, particle, output mode
and available history/restart metadata MUST agree. It SHALL locate the unique
mesh cell whose bin interior contains `(0, 0, 0)` in the existing PHITS
isocenter-origin coordinate system and report that cell's finite positive
relative error as percent only when its paired dose is also finite and positive.

The observer MUST NOT interpolate, select a nearest cell, add a coordinate
tolerance or change the existing mesh/coordinate mapping. If isocenter is
outside the mesh or lies on a bin boundary, the pair is incomplete or
mismatched, or the selected dose/error value is zero, negative, malformed or
non-finite, the relative-error detail SHALL be unavailable. The observer MUST
NOT substitute a value from `deposit-pdd.out`, compute full-mesh minimum,
maximum, median, mean, standard deviation or coverage, inspect DICOM RT
Structure contours, or calculate structure-based statistics.

The displayed value SHALL be identified as a provisional single Isocenter-voxel
reference, not whole-volume, ROI, combined-dose or clinical uncertainty and not
completion, convergence or automatic-stopping evidence. Tally and variance
settings MUST NOT change. Any future RT Structure relative-error evaluation
SHALL remain a separate post-completion capability and MUST NOT replace or
augment this live observation.

#### Scenario: Unique Isocenter-containing voxel is evaluable

- **WHEN** a complete matching primary 3D dose/error pair has one mesh-bin
  interior containing `(0, 0, 0)` with finite positive dose and relative error
- **THEN** observation reports only that cell's provisional `r.err` percentage
  and identifies it as an Isocenter-voxel reference

#### Scenario: Isocenter is not inside one voxel

- **WHEN** isocenter is outside the primary 3D mesh or lies on a bin boundary
- **THEN** relative-error detail is unavailable without interpolation, nearest-
  cell selection, coordinate tolerance or another-source fallback

#### Scenario: Incomplete or mismatched pair

- **WHEN** a slice is missing or dose and error metadata disagree
- **THEN** no new relative-error value is published

#### Scenario: Isocenter value is not evaluable

- **WHEN** the Isocenter voxel dose or relative error is zero, negative,
  malformed or non-finite
- **THEN** relative-error detail is unavailable and not represented as zero

#### Scenario: Other statistical sources are present

- **WHEN** PDD relative error, other mesh cells or RT Structure data are present
- **THEN** they do not replace or augment the single primary 3D Isocenter-voxel
  live reference

#### Scenario: Post-completion Structure evaluation exists

- **WHEN** a separately approved post-completion Structure evaluation is
  available
- **THEN** its statistics remain outside the live observation and do not alter
  live progress, convergence, stopping, completion, or downstream authority

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
