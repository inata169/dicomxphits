# Tasks

## 1. Proposal and approval

- [x] 1.1 Define the bounded segment-progress, time-estimate, interruption, and
  version-2 compatibility contracts without changing runtime code.
- [x] 1.2 Obtain primary-user approval of this proposal before implementation.
  Approved by the primary user on 2026-09-09.

## 2. Durable segment execution evidence

- [ ] 2.1 Add a strict version-3 segment execution summary with an invocation
  identifier, active-segment counts, current-segment state, UTC timestamps,
  monotonic elapsed durations, and per-segment transition evidence.
- [ ] 2.2 Write each progress transition atomically through the workspace output
  guard and retain the last complete record when a later write is interrupted.
- [ ] 2.3 Preserve successful version-2 summary consumption and keep every
  incomplete, running, interrupted, failed, or malformed record unauthorized
  for Sumtally and PHITS reuse.

## 3. GUI progress presentation

- [ ] 3.1 Poll only the selected workspace's expected execution summary while
  the GUI-owned PHITS stage is active and bind updates to that invocation.
- [ ] 3.2 Show completed and total active segments, current ordinal and safe
  segment identifier, elapsed time, approximate remaining time, approximate
  finish time, and terminal state without relying on color alone.
- [ ] 3.3 Show that an abandoned running record is interrupted and incomplete
  after the owning process is no longer active; never present it as currently
  running or complete.

## 4. Synthetic validation

- [ ] 4.1 Add focused fake-runner tests for transition ordering, atomic writes,
  timestamp and duration validation, estimator behavior, interruption, failure,
  skipped segments, and zero/one/multiple active-segment cases.
- [ ] 4.2 Add GUI tests for responsive progress updates, invocation binding,
  unavailable estimates, approximate labels, terminal states, and rejection of
  stale or malformed progress.
- [ ] 4.3 Prove that successful version-2 summaries remain accepted and that no
  non-success version-3 record unlocks Sumtally or workspace recovery.
- [ ] 4.4 Run focused checks and all public checks required by `AGENTS.md`.

## 5. Completion

- [ ] 5.1 Record any separately approved real-tool observation as external and
  unverified by repository tests; do not make it a requirement for synthetic
  acceptance or commit its paths, data, or outputs.
- [ ] 5.2 Promote the accepted deltas, archive the completed change, and strictly
  validate the resulting OpenSpec tree before completion reporting.
