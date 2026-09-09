# Design: Segment progress reporting

## Context

`run_segments` preflights all active segment paths, runs segments sequentially,
and currently writes `analysis/segment_execution_summary.json` after the loop
or after a handled exception. The GUI starts the accepted CLI on a worker
thread and receives only the terminal subprocess result. Existing downstream
consumers require an overall successful execution summary and validated output
digests.

The design must expose useful progress without treating transient display state
as downstream authority, parsing files that PHITS may still be writing, or
changing segment inputs and physics.

## Goals

- Make segment-boundary progress visible and durable.
- Preserve validated results from earlier segments in the record if a later
  segment or the controlling process fails.
- Provide a conservative, visibly approximate duration estimate.
- Preserve successful version-2 summary compatibility.
- Establish evidence that a later, separately proposed selective-rerun feature
  could validate, without implementing reuse in this change.

## Non-goals

- Batch-level progress or reading live PHITS output
- Segment `r.err` summaries or convergence decisions
- User stop, pause, resume, selective rerun, or additional-history integration
- Parallel or distributed execution
- Changes to PHITS inputs, runtime parameters, physics, geometry, dose, MU,
  DICOM meaning, or external workspace recovery

## Decisions

### Extend the existing summary as version 3

The writer will emit `dicomxphits_public_segment_execution_v3` at the existing
summary path. It will write a complete, strict object before starting the first
external process, before each segment starts, after each result is validated,
and at the terminal transition. Each replacement will use the repository's
bounded atomic JSON-write mechanism.

The object will include an opaque invocation identifier; `started_at` and
`updated_at` UTC timestamps; elapsed seconds measured with a monotonic clock;
active, completed, failed, skipped, and remaining counts; the current segment's
manifest ordinal and safe identifier when one is running; and the existing
per-segment output, digest, and geometry evidence after validation. Pending
entries will not contain fabricated result evidence.

An overall `stage_status` other than `success` remains incomplete and cannot
authorize any downstream stage. A persisted `running` record is evidence only
that the invocation reached its last recorded transition. If no matching
GUI-owned process is active, the GUI presents it as interrupted and incomplete,
not as proof that a process still runs.

### Bind GUI polling to the invocation

The GUI will poll the one documented summary path only while its own PHITS
stage worker is active. It will accept progress only after observing the new
invocation created by that launch and will ignore a stale record from a prior
invocation. UI updates will continue through the Tk event queue, preserving the
existing single-stage execution guard and responsive event loop.

The terminal subprocess result remains the authority for ending GUI polling.
The summary must also prove overall success before the GUI reports completion.

### Estimate only from validated completed segments

Each completed active segment records its elapsed duration measured with a
monotonic clock. Before one
active segment completes successfully, remaining time and finish time are
unavailable and the GUI displays `Estimating after first completed segment`.

Afterward, the estimate uses the arithmetic mean of successfully completed
active-segment durations. At a segment boundary it is the mean multiplied by
the number of incomplete active segments. While a segment is running, its
observed elapsed time is subtracted from one mean-duration allowance, floored
at zero, and the full mean is used for later pending segments. Failed or
skipped segments do not contribute to the mean.

Elapsed time continues to update locally while the GUI owns the process. Both
remaining time and finish time are labelled `Approximate` because segment
costs differ. Clock changes cannot make a duration negative: duration
measurement uses a monotonic clock, while UTC timestamps and the displayed
finish clock are presentation metadata.

### Keep version-2 success compatibility explicit

Readers that currently consume a completed segment execution summary will
continue to accept a valid version-2 `success` record under its existing
checks. They will accept version 3 only after strict structural, status, output,
digest, manifest-binding, and geometry-evidence validation. Unknown versions
fail closed.

No version-2 record is upgraded or rewritten merely by inspection. Version-2
records do not gain durable in-progress reporting, and this change does not use
either version to skip segment execution.

## Failure handling

- A handled preflight or execution error writes a terminal failure record while
  preserving every earlier validated segment result in the summary.
- A process or machine interruption may leave the last atomic `running` record;
  it remains incomplete and downstream-disabled.
- A malformed, truncated, stale-invocation, path-escaping, or unknown-version
  record is ignored for live presentation and rejected as execution authority.
- Failure to persist a required transition stops before starting the next
  segment. The implementation must not continue external execution while its
  durable progress evidence is known to be unavailable.

## Validation approach

Use injected monotonic and UTC clocks, fake runners, synthetic manifests, and
temporary workspaces. Tests will observe transition snapshots through a
bounded writer seam rather than attempting to simulate real PHITS timing.
GUI tests will exercise parsing, estimator presentation, stale-invocation
rejection, and event-loop scheduling without launching licensed tools.

Real PHITS, Sumtally, DICOM, and external workspace artifacts are outside the
automated validation boundary and remain separately approval-gated.
