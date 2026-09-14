# Improve PHITS preflight responsiveness

## Why

The controller recursively enumerates and hashes the configured PHITS
installation before execution and repeatedly during result verification. Real
boundary-stop acceptance showed that this repeated installation-wide work can
dominate controller elapsed time even when PHITS itself finishes normally. The
scan does not provide a practical safety benefit for the documented workflow:
the selected executable, workspace inputs, required results, process outcome,
stop state, ownership and downstream eligibility are the relevant boundaries.
Private paths and raw execution evidence do not belong in this change.

## What Changes

- Replace recursive installation membership/SHA-256 capture with a bounded
  launch-time check of the explicitly selected PHITS executable. Continue to
  bind the resolved executable path and SHA-256 without scanning its siblings.
- Keep invocation-owned preparation/verification progress for the bounded
  workspace and executable checks without misrepresenting it as PHITS progress
  or completed execution binding.
- Add an explicit **Cancel preparation** action only before the first child is
  committed. Cooperatively interrupt bounded hashing at checkpoints.
- Persist a separate, strict preflight-cancellation receipt proving no launch,
  not a v5 stopped result or permission to reuse incomplete statistics.
- Poll existing segment-boundary requests during verification, preserving all
  current-result validation and publication gates after any committed child.
- Treat PHITS `batch.out` files as mutable control/progress artifacts. They may
  be monitored or retained, but their content is not immutable result evidence,
  and a user edit such as `0` to `-1` remaining batches does not by itself cause
  an artifact-mutation failure.
- Replace full-mesh relative-error summary display with one provisional
  Isocenter-voxel `r.err` value read from the manifest-selected primary 3D dose
  error companion. Do not display PDD-derived, whole-volume or RT Structure
  relative-error statistics in this change.
- Keep workspace input membership and SHA-256 binding; required primary dose
  outputs, the selected 3D dose error companion, optional produced error
  companions, exit code, geometry diagnostics, stop evidence, workspace
  ownership and downstream gates remain fail-closed. `batch.out` alone can
  never prove normal completion.

## Impact

Proposed capability: `phits-preflight-control`; `phits-live-observation` and
guided GUI deltas are also required. Expected implementation surfaces:
controller, binding scanner, live-observation parser, stop control, GUI
presentation, read-only recovery/downstream gates, and synthetic tests.
Existing v2-v5 workspace/result evidence remains readable without migration or
historical rewriting. Any new child launch uses newly recorded bounded
executable-scope evidence.

The original responsiveness proposal was approved before its first runtime
implementation. The revised executable-only runtime boundary and the
Isocenter-voxel presentation in this document were approved for implementation
on 2026-09-14.
Installation siblings are deliberately outside the execution binding; the
workflow does not claim to detect their mutation.
No physics, geometry, DICOM, MU, dose factor, tally, history, external tool or
release changes. No new built-in batch/immediate PHITS stop control, process
kill, automatic retry, installation cleanup, push, PR creation or release is
authorized.
