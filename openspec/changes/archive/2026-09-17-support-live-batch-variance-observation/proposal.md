# Support live batch-variance observation

## Why

The public segment generator writes `istdev = -1`, but live observation setup
rejects any explicit variance directive. Independently, the current live output
parser only accepts history-variance metadata (`istdev = 2`). Accepting the
generated input alone cannot provide voxel observation for batch-variance
outputs (`istdev = 1`). Supporting that output form needs an explicit reviewed
observation contract, without changing the generated calculation.

## What Changes

- Accept the single generated `istdev = -1` input directive; reject duplicate,
  malformed, or other explicit variance directives and preserve other guards.
- Extend only live Isocenter-voxel observation to reviewed PHITS 3.35 Windows
  OpenMP fresh-output pairs with matching batch-variance metadata.
- Read the reported relative error directly and convert its fraction to percent.
  Do not recompute uncertainty or convert batch counts into histories or ETA.
- Require matching variance mode, restart identity, mesh, roles, source-weight
  metadata, counts, and seeds. For batch variance, require a positive integral
  batch count within the prepared budget and matching prepared maxcas.
- Identify the extended observation format without mislabelling it as the
  existing history-only parser; reject unsupported identities and variance modes.
- Preserve two-sample confirmation, independent age/staleness, bounded reading,
  and reset on segment/workspace/owner transitions.

## Impact

Affected: live observation parser, observer/presentation, and authored synthetic
regression tests. Shared parser callers for post-completion statistics must keep
their existing accepted modes unless separately approved. Calculation inputs,
variance settings, physics, DICOM meaning, Sumtally, Structure evaluation,
execution evidence, and downstream gates do not change.

The input-directive bug fix is implemented locally and focused-tested. The
batch-variance extension was approved by the human on 2026-09-17. This proposal
does not authorize a real external-tool invocation or modification of retained
calculation artifacts. Exact real-run verification requires separate execution
authorization; its absence must be reported explicitly.
