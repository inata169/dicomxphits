## ADDED Requirements

### Requirement: Research Geometry Exception Presentation

The GUI SHALL enforce the research-exception presentation contract below when a fully revalidated receipt authorizes downstream work. It MUST retain failed PHITS status, show the accepted segment and research-only notice, and create receipts only through the explicit confirmed acceptance requirement.

#### Scenario: Complete research presentation is shown

- **WHEN** the GUI displays a selected synthetic workspace with a research receipt
- **THEN** the following complete contract SHALL hold:

When downstream authority comes from a fully revalidated research
geometry-recovery receipt, the GUI SHALL present the PHITS stage as failed
with an accepted research exception, never as success. It SHALL show the
accepted segment identity. It SHALL also show a persistent research-only notice
on the PHITS, Sumtally, and RTDOSE stages, stating that the result is not for
clinical use, commissioning, patient QA, or vendor certification. When the
receipt is absent or invalid, the GUI SHALL keep the existing failed
presentation and the existing disabled downstream actions.

The GUI MUST NOT create a receipt without the explicit confirmation and
full revalidation required by Confirmed GUI Research Geometry Acceptance.

#### Scenario: Valid receipt displayed

- **WHEN** a selected synthetic workspace has a fully revalidating receipt
- **THEN** the GUI shows the research-exception state and notice and enables
  only the downstream actions that the shared gate authorizes

#### Scenario: Invalid receipt displayed

- **WHEN** the receipt is missing, malformed, or stale
- **THEN** the GUI presents the ordinary failed state and keeps downstream
  actions disabled

### Requirement: Explicit Workspace Evidence Re-read

The GUI SHALL provide an explicit action that re-reads the selected workspace's
evidence and recomputes stage availability without running an external tool.
Users MUST NOT need to toggle an unrelated option to refresh stage state.

#### Scenario: Evidence changed outside the GUI

- **WHEN** a receipt is created through the CLI while the GUI is open and the
  user invokes the re-read action
- **THEN** the GUI recomputes stage availability from current evidence

### Requirement: Confirmed GUI Research Geometry Acceptance

The GUI SHALL offer explicit research acceptance through the same read-only
preview and digest-bound apply backend as the CLI. It SHALL show counts and
all region pairs, require a reason and affirmative confirmation, and preserve
failed PHITS status. Acceptance MUST NOT launch an external tool or recalculate
PHITS. It MAY unlock only separately invoked downstream actions authorized by
the shared gate. The GUI MUST remain responsive during validation.

#### Scenario: Operator reviews and confirms existing results

- **WHEN** one explicitly selected retained staging directory validates for
  the currently selected workspace under the research eligibility policy
- **THEN** the GUI shows the workspace and segment identity, all diagnostic
  totals, every region pair and count, final-batch completion evidence, and
  the persistent research-only notice
- **AND** it requests a non-empty reason and asks whether to continue for
  research use with affirmative and negative choices, stating that the saved
  calculation is not rerun
- **AND** only an affirmative answer supplies the explicit acknowledgement to
  apply with that exact preview digest and reason
- **AND** apply rechecks all evidence, publishes the validated existing tally
  set new-only with the receipt last, and preserves every original record
- **AND** no PHITS, Sumtally, or phits2dicom process starts during acceptance

#### Scenario: Operator declines or closes the confirmation

- **WHEN** the operator declines, closes or escapes the dialog, or omits the
  reason
- **THEN** no acknowledgement is supplied, no receipt or output is published,
  and no downstream action is unlocked by that interaction

#### Scenario: Evidence changes after the displayed preview

- **WHEN** the workspace selection, invocation binding, diagnostic counts,
  pair distribution, source digests, or destination state changes before apply
- **THEN** confirmation cannot authorize mutation using the old preview and
  the GUI requires a new validated preview

#### Scenario: Nonzero loss or incomplete calculation

- **WHEN** saved evidence reports lost or unrecovered particles, unfinished
  final batches, unsupported parsing, or another failure reason
- **THEN** the GUI explains the failed precondition and does not offer an
  affirmative continuation that bypasses it

#### Scenario: Historical evidence cannot prove the invocation

- **WHEN** the selected saved result lacks the required authoritative staging
  and invocation binding
- **THEN** the GUI explains why acceptance is unavailable and creates no
  receipt, without triggering PHITS recalculation or automatic retry

#### Scenario: Research acceptance completes

- **WHEN** GUI acceptance publishes and independently revalidates its receipt
- **THEN** the GUI retains failed PHITS status with the research-exception
  indication and refreshes the availability of Sumtally and RTDOSE actions
- **AND** those separately invoked actions each revalidate current receipt
  authority at their existing boundaries

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
time and finish time MUST be labelled approximate. Optional batch and
Isocenter-voxel relative-error detail SHALL come only from the invocation-bound
observation sidecar under the `phits-live-observation` contract, in a separately
labelled provisional detail area. The relative-error label MUST identify a
single reference voxel and MUST NOT imply whole-volume, ROI, combined-dose or
clinical uncertainty. The live progress presentation MUST NOT display
PDD-derived, full-mesh aggregate or RT Structure relative-error statistics.
RT Structure relative-error statistics SHALL appear only in a distinct
`Post-completion Structure r.err` section on the Sumtally page after verified
all-active-segment Sumtally success and an explicit user action. They MUST NOT
replace or augment the live Isocenter-voxel detail. Observation MUST NOT claim statistical
convergence, a verified PHITS result still being written, or replace the
segment-based ETA calculation.

A persisted running record whose invocation is not owned by an active GUI
process SHALL be presented as interrupted and incomplete rather than currently
running. A stale-invocation, malformed, path-escaping, or unknown-version record
MUST NOT replace current progress or unlock a dependent action. Only the
existing terminal-success evidence contract may display PHITS as completed.
Ordinary Sumtally availability SHALL require terminal success; only the
separate fully revalidated research receipt MAY authorize downstream research
actions while PHITS remains displayed as failed.

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
  durable validated completion counts, and keeps Sumtally disabled unless the
  separate research receipt fully revalidates under its own eligibility checks;
  a research exception never changes the PHITS failure presentation

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

#### Scenario: Post-completion Structure statistics are available

- **WHEN** an explicitly requested post-completion evaluation reports RT
  Structure relative-error statistics from verified Sumtally success
- **THEN** the GUI presents them only in the distinct Sumtally-page section,
  outside live PHITS progress, and does not use them as convergence, stopping,
  completion, or downstream evidence

### Requirement: Workspace-Bound Retry Progress

The GUI SHALL bind preview, execution, polling, and terminal callbacks to the
currently selected resolved workspace and invocation. Relevant workspace
selection controls SHALL be locked during ordinary or selective PHITS execution;
an unexpected programmatic selection change MUST invalidate old presentation
updates. Other stage actions and repeated launch requests MUST remain disabled.
Retry progress SHALL distinguish retained successes from newly completed results.
Elapsed time and estimates SHALL describe the new invocation; retained durations
MUST NOT supply its ETA. Sumtally SHALL remain disabled until fresh all-active
terminal-success evidence validates, unless the separate research-recovery
receipt fully revalidates through the shared downstream gate. That exception
MUST NOT bypass current workspace or invocation checks or display PHITS as
successful.

#### Scenario: Selection changes while an invocation is active

- **WHEN** the selected root no longer matches the invocation workspace
- **THEN** polling and terminal callbacks cannot display the old workspace as current or unlock downstream actions

#### Scenario: Retry begins with retained successes

- **WHEN** retained results exist but no segment has completed in the new invocation
- **THEN** the GUI shows the retained count separately and states that ETA awaits a new completion
