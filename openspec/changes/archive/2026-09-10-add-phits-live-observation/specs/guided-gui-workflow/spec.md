## MODIFIED Requirements

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
time and finish time MUST be labelled approximate. Optional batch and per-cell
relative-error detail SHALL come only from the invocation-bound observation
sidecar under the `phits-live-observation` contract, in a separately labelled
provisional detail area. It MUST NOT claim statistical convergence, a verified
PHITS result still being written, or replace the segment-based ETA calculation.

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

- **WHEN** the current owned segment has a supported provisional observation
- **THEN** the GUI shows its remaining-batch and per-cell error facts with sample age and coverage, separately from authoritative segment completion

#### Scenario: Optional detail is unavailable

- **WHEN** observation is stale, unsupported, malformed or absent
- **THEN** the GUI labels that limitation while preserving normal segment progress and existing stop/retry controls
