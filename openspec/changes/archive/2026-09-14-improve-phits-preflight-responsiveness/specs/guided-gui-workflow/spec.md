## MODIFIED Requirements

### Requirement: Exclusive Responsive Stage Execution

The GUI SHALL keep the Tk event loop responsive while an external stage runs
and SHALL prevent another external stage from starting concurrently. It SHALL
continue to use each accepted adapter's existing timeout and failure evidence
rather than adding a bypassing process-cancellation path. The explicit owned
PHITS stop-after-current request SHALL request a verified boundary, not child
termination or another stage launch. The distinct owned Cancel preparation
action MAY cancel preflight only under the `phits-preflight-control` contract
before any PHITS child commitment; it MUST NOT cancel a committed child.

#### Scenario: Stage in progress

- **WHEN** one external stage is running
- **THEN** other stage actions remain disabled until a controlled result, with only the applicable owned preflight or segment-boundary control available

### Requirement: Guided PHITS Segment Progress Presentation

While the GUI owns an active direct PHITS segment invocation, it SHALL display
the validated completed and total active-segment counts, the current segment's
manifest ordinal and safe identifier, elapsed time, available approximate
remaining time, available approximate finish time, and running or terminal
state. It SHALL obtain authoritative segment progress only from the documented
summary path inside the selected workspace, bind displayed updates to the
invocation started by that GUI action, and keep the Tk event loop responsive.

Before one active segment completes successfully, the GUI SHALL state that the
estimate is unavailable pending initial evidence. Every displayed remaining
time and finish time MUST be labelled approximate. Optional batch and
Isocenter-voxel relative-error detail SHALL come only from the invocation-bound
observation sidecar under the `phits-live-observation` contract, in a separately
labelled provisional detail area. The relative-error label MUST identify a
single reference voxel and MUST NOT imply whole-volume, ROI, combined-dose or
clinical uncertainty. The GUI MUST NOT display PDD-derived, full-mesh aggregate
or RT Structure relative-error statistics in this change. Observation MUST NOT
claim statistical convergence, a verified PHITS result still being written, or
replace the segment-based ETA calculation.

A persisted running record whose invocation is not owned by an active GUI
process SHALL be presented as interrupted and incomplete rather than currently
running. A stale-invocation, malformed, path-escaping, or unknown-version record
MUST NOT replace current progress or unlock a dependent action. Only the
existing terminal-success evidence contract may display PHITS as completed and
enable Sumtally.

#### Scenario: First segment is running

- **WHEN** the GUI-owned invocation has started its first active segment and no
  active segment has completed successfully
- **THEN** the GUI shows the current segment, zero completed out of the active
  total, elapsed time, and that time estimation awaits the first completion

#### Scenario: Later segment is running

- **WHEN** one or more active segments completed successfully and another is
  running
- **THEN** the GUI shows the validated completed count and clearly labels the
  calculated remaining time and finish time as approximate

#### Scenario: Invocation completes

- **WHEN** the GUI-owned subprocess ends and the accepted terminal summary
  proves all active segments successful
- **THEN** the GUI shows completion with the final counts and existing summary
  path and may enable the accepted Sumtally action

#### Scenario: Invocation is interrupted or fails

- **WHEN** the process ends without accepted terminal success or a prior
  running record is found without its owning process
- **THEN** the GUI identifies the run as failed or interrupted, shows only
  durable validated completion counts, and keeps Sumtally disabled

#### Scenario: Progress record is stale or invalid

- **WHEN** the expected summary is from another invocation, malformed, escapes
  the selected workspace, or declares an unknown schema version
- **THEN** the GUI does not present it as current progress and does not unlock a
  dependent action

#### Scenario: Optional detail is available

- **WHEN** the current owned segment has supported provisional batch or a
  unique Isocenter-containing-voxel observation
- **THEN** the GUI shows the available remaining-batch and single-voxel `r.err`
  facts with independent sample ages, separately from authoritative completion

#### Scenario: Optional detail is unavailable

- **WHEN** observation is stale, unsupported, malformed, absent, or isocenter
  is outside the mesh or on a bin boundary
- **THEN** the GUI labels that limitation without interpolation or another-
  source fallback while preserving normal progress and stop/retry controls

## ADDED Requirements

### Requirement: Distinct Preparation and Verification Presentation

The GUI SHALL display owned preparation/verification phases, elapsed time and
bounded workspace/executable file and byte counts separately from segment and
provisional batch progress. It MUST NOT describe those counts as installation-
wide scanning. The GUI SHALL treat `batch.out` detail as mutable, provisional
observation rather than immutable completion evidence.
It SHALL distinguish Cancel preparation from Stop after current segment, and
request sent from durable acknowledgement and terminal cancellation/stopping.
It MUST NOT describe an active segment when none is committed, invent ETA or
claim retry eligibility from a preflight receipt. Terminal preflight cancellation
SHALL keep Sumtally disabled and offer only fresh explicitly confirmed preflight.

#### Scenario: User cancels before PHITS starts

- **WHEN** the controller exits 5 with a matching validated cancellation receipt
- **THEN** the GUI shows preparation cancelled with no PHITS launched, not completed or v5 user-stopped

#### Scenario: Verification continues after stop acknowledgement

- **WHEN** no child is running but required result validation remains
- **THEN** the GUI says verification is pending and does not claim a current segment is still calculating

#### Scenario: Mutable batch detail changes

- **WHEN** an owned invocation's observed `batch.out` remaining-batch value is
  edited from `0` to `-1`
- **THEN** the GUI may mark provisional batch detail unavailable but does not
  report artifact mutation, normal completion or verified stopping from that
  value alone
