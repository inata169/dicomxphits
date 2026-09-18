# Simplify complete live observation and optimize voxel parsing

## Why

Full numeric validation of a supported primary 3D dose/error pair can exhaust
the live observer's two-second sampling budget before it can display a voxel
reference. An isolated synthetic prototype demonstrated equivalent numeric
results with bulk conversion, but its page-wide token lists still require
bounded-memory and deadline-checkpoint work before product integration.

On 2026-09-18 the human accepted a median of at most two seconds as a
**provisional performance criterion** and authorized preparation of this
proposal. That decision does not relax the per-attempt deadline or authorize
implementation. Existing synthetic feasibility evidence is not acceptance
evidence for a future integrated implementation.

## What Changes

- Review the complete synchronous observation attempt, from identity/batch
  reads through guarded dose/error reads, hashing, parsing, pairing, selection
  and candidate records. Simplify demonstrated redundant work, unnecessary
  copies and temporary objects within that attempt, not only numeric checks.
- Combine equivalent checks on the same immutable snapshot where equivalence
  is demonstrated. Preserve every validation obligation and freshness boundary;
  do not treat checks before and after a file read as redundant.
- Add an explicitly selected numeric fast path for live observation only.
  Preserve the existing scalar path for other shared-parser consumers.
- Validate every token and every cell. Bulk-convert a strictly validated
  common numeric spelling using existing NumPy; preserve the scalar grammar
  and conversion for all other supported spellings.
- Bound numeric tokenization and conversion scratch space independently of
  page cell count, with deadline checks between bounded chunks. Avoid the
  prototype's page-wide list of token objects.
- Preserve full structural/pair validation, fresh-output provenance, runtime
  budgets, all current resource limits, and the cooperative two-second deadline.
- Keep positive-dose/positive-error Isocenter selection, two-observation
  confirmation, independent sample ages, staleness, reset, and presentation-only
  authority unchanged.
- Validate the integrated path with synthetic differential/resource tests and
  a repeatable complete `Observer.sample` benchmark. Use five declared attempts
  and median at most two seconds for provisional timing acceptance, retaining
  timeout counts and every outcome. Functional correctness remains mandatory.

## Impact

Affected capability: `phits-live-observation`. Expected implementation surface:
live sample orchestration, guarded read/hash implementation, parsing helpers,
candidate-record construction, synthetic tests and a synthetic benchmark
utility. Shared structural helpers may be reused without changing
the default numeric path or accepted formats for post-completion consumers.
No additional dependency is proposed.

This proposal is based on the current branch's accepted fresh batch-variance
contract. Integration must preserve that baseline; this proposal does not
authorize merging its prerequisite branch or any pull request.

Out of scope: calculation inputs or PHITS settings; DICOM meaning, geometry,
physics, dose or variance calculation; additional-history/restart support;
batch-boundary stopping; cache/incremental observation architecture; zero-value
causation; GUI completion-hint fixes; and new post-completion acceptance modes.
Existing parser identity, sidecar schema, worker count and scheduling remain.

Tests use project-authored data and fake runners. Neither proposal approval nor
implementation approval authorizes real external-tool execution, replay of real
outputs, or manipulation of the user's running calculation GUI. Exact real
verification requires separate authorization. No real GUI verification is a
prerequisite for this synthetic-only change; its absence must remain explicit.

## Approval and stopping point

Status: implementation approved and completed; the human-authorized concurrent
synthetic performance run passed on 2026-09-18. The idle-load wait was explicitly
replaced by measurement during the user's reported seven-thread calculation.
Eight-thread load, real-output replay and real-GUI display remain unverified.
Accepted deltas are promoted and this change is archived at closeout. No further
optimization is required by the approved provisional criterion. Publication of
a review PR is a separate external write; a local review description is prepared.
