# Support live batch-variance observation

## Why

The public segment generator writes `istdev = -1`, but live observation setup
rejects any explicit variance directive. Independently, the current live output
parser only accepts history-variance metadata (`istdev = 2`). Accepting the
generated input alone cannot provide voxel observation for outputs whose
effective variance mode is batch variance (`istdev = 1`). Supporting that output
form needs an explicit reviewed observation contract, without changing the
generated calculation.

The input directive and effective output mode are distinct. PHITS documents
`istdev = -1` as enabling restart mode: without a past tally result it starts a
new batch-variance calculation; with a past result, the variance mode is taken
from that result. The directive alone therefore does not establish the output
mode or prove that a calculation is new. See the official
[PHITS parameter documentation](https://phits.jaea.go.jp/manual/PHITS-en/chapters/sections/parameters/parameters_2.html).
This online reference describes version 3.37; it does not widen this observer's
reviewed 3.35 format identity.

## What Changes

- Accept the single generated `istdev = -1` input directive; reject duplicate,
  malformed, or other explicit variance directives and preserve other guards.
- Extend only live Isocenter-voxel observation to reviewed PHITS 3.35 Windows
  OpenMP fresh-output pairs with matching batch-variance metadata.
- Read the reported relative error directly and convert its fraction to percent.
  Do not recompute uncertainty or convert batch counts into histories or ETA.
- Require matching variance mode, restart identity, mesh, roles, source-weight
  metadata, counts, and seeds. For batch variance, require a positive integral
  batch count within prepared maxbch and an effective maxcas recorded in both
  outputs that agrees with prepared maxcas for the supported newly started
  calculation. These prepared-value checks remain mandatory.
- Identify the extended observation format without mislabelling it as the
  existing history-only parser; reject unsupported identities and variance modes.
- Preserve two-sample confirmation, independent age/staleness, bounded reading,
  and reset on segment/workspace/owner transitions.

## Fresh-calculation boundary

This extension accepts only output pairs explicitly marked as newly started;
PHITS restart outputs remain unsupported. In particular, the restart-information
section present in a new output is not evidence that restart execution occurred.
The existing segment retry workflow preserves validated completed segments and
uses fresh staging for incomplete segments; it does not add histories to a
retained tally through this observation extension.

For a batch-variance restart, input maxcas cannot generally stand in for the
effective batch size. The official
[PHITS 3.02 manual, section 4.2.2](https://phits.jaea.go.jp/manual/manualE-phits302.pdf)
documents reading maxcas from prior tally state rather than the current input.
Supporting such state would need separate provenance and budget rules; replacing
the prepared-maxcas equality check with an unspecified effective value is not
part of this change. The older manual explains the distinction and is not a
claim of newly validated restart support in version 3.35.

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
