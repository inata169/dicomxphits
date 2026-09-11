# Improve PHITS preflight responsiveness

## Why

The controller captures the configured installation tree before publishing its
first execution summary. It repeats that capture before polling a stop request
and again before terminal stopping. The GUI can consequently show unexplained
startup or stop-pending waits even when no PHITS child has started. This follows
from `capture_binding()` in `segment_retry.py` and the ordering in
`_run_segments_locked()` in `run_segments.py`; private validation motivated this
review, but no private paths, outputs or measured results belong in this change.

## What Changes

- Publish bounded, invocation-owned preparation/verification progress without
  misrepresenting it as PHITS progress or completed execution binding.
- Add an explicit **Cancel preparation** action only before the first child is
  committed. Cooperatively interrupt enumeration and hashing at checkpoints.
- Persist a separate, strict preflight-cancellation receipt proving no launch,
  not a v5 stopped result or permission to reuse incomplete statistics.
- Poll existing segment-boundary requests during verification, preserving all
  current-result validation and publication gates after any committed child.
- Keep full membership and SHA-256 validation at existing execution gates.
  Normal execution may still be slow; no digest cache or dependency narrowing
  is authorized by this proposal.

## Impact

Proposed capability: `phits-preflight-control`; guided GUI delta also required.
Expected implementation surfaces: controller, binding scanner, stop control,
GUI presentation, read-only recovery/downstream gates, and synthetic tests.
Existing v2-v5 evidence remains readable without migration or changed meaning.

The human approved this proposal before runtime implementation. It is a
bounded first response, not a claim to solve total hashing cost. A smaller
runtime dependency profile requires separate evidence and approval; installation
contents must not be guessed from filenames or pruned to make a test fast.
No physics, geometry, DICOM, MU, dose factor, tally, history, external tool or
release changes. No batch/immediate PHITS stop, process kill, automatic retry,
installation cleanup, push, PR creation or release is authorized.
