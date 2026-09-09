# Change: Stop PHITS after the current segment

## Why

PR #61 provides explicit incomplete-segment execution. Users now need a safe
way to stop an owned calculation at a verified segment boundary, retain its
completed results, and later use that existing retry action. Killing PHITS or
its controller cannot establish that boundary and is not the proposed operation.

## What Changes

- Add an explicit GUI action to request stopping after the current segment for
  an owned, retry-capable ordinary or selective PHITS invocation.
- Distinguish request transmission, acknowledged stop pending, user-stopped,
  execution failure, interruption, and complete success.
- Finish and validate the committed current segment, persist its evidence, then
  start no further segment once the request is acknowledged.
- Serialize request acceptance and segment launch so boundary races have one
  outcome. Failure takes precedence; final verified completion remains success.
- Introduce v5 execution evidence with stop metadata and a terminal `stopped`
  state. Preserve v2/v3/v4 read contracts and valid v4 selective retry.
- Keep unstarted entries pending and downstream gates closed after a partial
  stop; restart through the existing explicit incomplete-segment preview.
- Use an invocation-scoped controller input channel, not a shared stop file,
  process termination, signal interception, or removal of execution ownership.

## Impact

Expected implementation areas are the segment controller and summary validators,
GUI stage adapter and presentation, retry/provenance readers, downstream gates,
and synthetic tests. No runtime code or current specification is changed by
this proposal. Implementation requires separate human approval.

This is stage 3 only. Batch-boundary stopping, immediate cancellation, batch
progress/error parsing, checkpoint continuation, and additional history remain
out of scope. Fixed 6 MV, 3D-CRT physics, geometry, DICOM semantics, MU, and dose
conversion stay unchanged. Existing external failed workspaces and remaining
staging are excluded; no automatic migration, rescue, or real-tool execution.

Baseline: PR #61 merged at `9a4e036` by explicit human instruction. Its Ready
triggered review was still running at merge; this proposal does not claim that
review had approved the change. The old CI #538 failure was corrected before
merge, with successful subsequent CI #540 through #545.
Post-merge main CI #546 also passed on both Ubuntu and Windows. The merged
feature branch was deleted locally and remotely, and synchronized main was
confirmed clean before creating this proposal branch.

Status: approved by the human on 2026-09-09 and implemented on the proposal
branch. This change remains active pending final checks, PR review, and the
required specification promotion/archive closeout.
