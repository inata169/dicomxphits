# Change: Add read-only PHITS batch and relative-error observation

## Why

Segment progress, explicit incomplete-segment retry, and stopping after the
current segment are implemented. A long-running segment still has no detail
view. Stage 4a adds observational detail without interpreting partial results
as successful computation or changing the calculation.

## What Changes

- Add invocation-bound observation of supported PHITS 3.35 Windows OpenMP
  batch information and the current segment's generated 3D dose/error tally.
- Display observed remaining batches against the prepared batch budget, sample
  age, availability, and explicitly provisional per-cell relative-error
  statistics. Do not infer completed histories or alter the segment ETA.
- Use the entire current 3D tally mesh, reporting valid-cell coverage and
  median/maximum positive relative error. Do not claim ROI, plan-wide, summed
  dose, convergence, or clinical uncertainty.
- Keep optional observation separate from authoritative v2-v5 execution
  evidence and every downstream/retry/stop decision.
- Replace only the GUI specification's blanket prohibition on batch detail
  with a bounded observational exception. Preserve its success guards.

## Impact

Proposed capabilities: `phits-live-observation` (new) and
`guided-gui-workflow` (modified). Likely implementation locations after approval:
the staged segment runner, a bounded observer/parser, GUI presentation, and
synthetic tests. Current runtime and accepted specs are unchanged by this PR.

No input rewriting, parameter changes, batch stop, immediate kill, signals,
timeout changes, additional history, automatic convergence, or result reuse.
Fixed 6 MV/3D-CRT physics, geometry, DICOM, MU, dose factors, PDD and 3D meshes
remain unchanged. Old failed external workspaces and residual staging remain
out of scope. No distribution files or real outputs will be tracked.

## Approval and completion boundary

This is a proposal, not implementation approval. Obtain human approval before
runtime work. Synthetic fixture validation must be distinguished from real
PHITS validation. Exact real-tool verification requires separate permission;
the feature must report unsupported data honestly if identity or format cannot
be established. Keep this change active until approved implementation and
required checks are complete; only then promote deltas and archive.
