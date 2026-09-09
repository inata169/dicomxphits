# Change: Rerun only incomplete PHITS segments

## Why

Segment progress is available after PR #60, but repeating PHITS execution still
runs every active segment. A failed or interrupted calculation needs an explicit
way to retain verified completed results and execute only the remaining work.
Current v2/v3 records do not bind the complete input dependency set at execution
time, so their output hashes alone cannot safely authorize selective execution.

## What Changes

- Add read-only retry planning and an explicit GUI/CLI action for incomplete
  segments, with a preview of retained and scheduled segment identities.
- Introduce version-4 execution evidence for new runs, binding actual inputs,
  recursive dependencies, preparation/model/calibration evidence, executable
  identity, effective runtime settings, and required outputs.
- Revalidate every retained success and the full execution binding before any
  retry mutation or launch. Missing evidence or changed conditions require a
  newly prepared workspace; they never silently turn a success into a retry.
- Preserve earlier attempt evidence, successful artifacts, and provenance while
  executing incomplete segments from the beginning in fresh staging.
- Prevent concurrent PHITS executions in one workspace across GUI and CLI,
  including a surviving child after its controller exits.
- Keep downstream stages disabled until a fresh terminal record validates the
  complete unique active-segment set. Keep normal v2/v3 downstream compatibility,
  but never infer retry eligibility for these older records.
- Bind GUI preview, launch, polling, and terminal presentation to the current
  selected workspace and invocation, including changes to selection while busy.

## Impact

Expected implementation areas: `run_segments.py`, `workspace_recovery.py`, GUI
stage integration, evidence readers in Sumtally/recovery, a workspace execution
lock, and synthetic tests. Existing output-path guards remain mandatory.
New specifications cover selective execution; runtime and GUI deltas describe
the versioned evidence and presentation changes needed by that capability.

This is stage 2 in the user-selected sequence: segment progress (merged),
incomplete-segment retry, segment-boundary stopping, batch progress/error and
expanded stopping, then additional history. Stopping and additional-history
semantics are not part of this change. Fixed 6 MV, 3D-CRT physics, geometry,
DICOM semantics, MU, and dose conversion are unchanged.

The original failed external workspace and retained staging are excluded. No
migration, rescue, real-tool discovery, or real execution is authorized by this
proposal. Automated validation uses synthetic data and fake runners only.

Status: approved by the human on 2026-09-09, implemented in PR #61, and archived
after validation and review-driven correction. PR #60 was merged at `f7dfbac`;
its historical handoff is not authority to repeat correction round 8. Its
workspace-selection review finding is covered by the implemented binding checks.
PR #61 remains draft pending the human's ready/merge decision; no real PHITS
or interactive desktop verification is claimed.
