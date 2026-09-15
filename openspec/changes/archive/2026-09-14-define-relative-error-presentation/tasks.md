# Tasks

## Proposal and decisions

- [x] Inspect the current live-observation, GUI, Sumtally, RTDOSE, and existing
  RT Structure boundaries.
- [x] Preserve execution-time Isocenter-only presentation and separate PDD,
  whole-mesh, and Structure meanings in draft deltas.
- [x] Record the additional authoritative completed dose/error source decision.
- [x] Create the proposal, design, tasks, and initial requirement deltas without
  runtime changes.
- [x] Strictly validate the initial definition-phase draft.
- [x] Obtain human approval to use only the validated all-active-segments
  Sumtally combined 3D result, with verified combined `r.err` semantics and
  dose pairing, as the authoritative completed source (2026-09-14).
- [x] Obtain human approval to evaluate exactly one explicitly selected unique
  `ROINumber`, use `ROIName` only as a label, and fail closed without implicit
  name matching or multi-ROI evaluation (2026-09-14).
- [x] Obtain human approval to use the existing RTDOSE affine and a validated
  frozen-CT voxel-centre mask for uniquely mapped dose-voxel centres, accepting
  only matching `CLOSED_PLANAR` contours without interpolation, partial volume,
  or a new coordinate tolerance (2026-09-14).
- [x] Obtain human approval to use the fixed `D > 0.5 * Dmax` threshold, where
  `Dmax` is the non-displayed finite positive maximum of the entire validated
  combined 3D dose grid, and to make evaluation unavailable when the reference
  or eligible Structure volume is absent (2026-09-14).
- [x] Obtain human approval to require complete matching grids with finite
  non-negative values, fail the whole evaluation on malformed, non-finite,
  negative, or mismatched data, admit only thresholded positive dose/error
  cells, count zero error as excluded, and require at least two eligible voxels
  (2026-09-14).
- [x] Obtain human approval to report unweighted `r.err` percent arithmetic
  mean, median, and linearly interpolated P95 with mapped, above-threshold,
  eligible, and zero-error exclusion counts, while excluding minimum, maximum,
  and standard deviation (2026-09-14).
- [x] Obtain human approval for an explicit, separately labelled Sumtally-page
  evaluation; deterministic evidence-bound scalar-summary persistence; exact
  stale invalidation; no v1 export; and no downstream authority (2026-09-14).
- [x] Add an exact post-completion Structure-statistics capability delta after
  those decisions are approved.
- [x] Strictly validate the complete decision-ready proposal (2026-09-14;
  change and all-spec validation passed).
- [x] Obtain human approval of the complete proposal as the implementation
  contract (2026-09-14); runtime implementation remains separately gated.

## Implementation

- [x] Implement only the approved post-completion evaluator and evidence
  contract; do not alter live Isocenter observation.
- [x] Add the separately approved GUI presentation and non-clinical labeling.
- [x] Add synthetic and fake-runner focused coverage for every approved
  scenario and fail-closed boundary.
- [x] Run focused checks and the full public checks required by `AGENTS.md`
  (2026-09-14; focused 339 passed and 1 skipped; full 1238 passed and 11
  skipped; review round 1 focused 140 passed and 1 skipped; review round 1
  full 1239 passed and 11 skipped; review round 2 focused 141 passed and 1
  skipped; review round 2 full 1240 passed and 11 skipped; review round 3
  focused 284 passed and 1 skipped; review round 3 full 1239 passed and 12
  skipped; review round 4 focused 284 passed and 1 skipped; review round 4 full
  1239 passed and 12 skipped; review round 5 focused 271 passed and 1 skipped;
  review round 5 full 1241 passed and 12 skipped; review round 6 focused 271
  passed and 1 skipped; review round 6 full 1241 passed and 12 skipped;
  review round 7 focused 271 passed and 1 skipped; review round 7 full 1241
  passed and 12 skipped; review round 8 focused 272 passed and 1 skipped;
  review round 8 full 1242 passed and 12 skipped; compileall, OpenSpec strict
  validation, public-tree audit, and diff checks passed; review round 9 focused
  274 passed and 1 skipped; review round 9 full 1244 passed and 12 skipped;
  compileall, OpenSpec strict validation, public-tree audit, and diff checks
  passed; review round 10 focused 274 passed and 1 skipped; review round 10
  full 1244 passed and 12 skipped; compileall, OpenSpec strict validation,
  public-tree audit, and diff checks passed; review round 11 focused 274 passed
  and 1 skipped; review round 11 full 1244 passed and 12 skipped; compileall,
  OpenSpec strict validation, public-tree audit, and diff checks passed).
- [x] Promote accepted deltas, archive the completed change, and strictly
  validate the resulting specification tree (2026-09-14).

Implementation was separately approved on 2026-09-14. Real-tool execution,
release, and archive were not authorized by the creation of the original
draft; archive was separately approved and completed on 2026-09-14.
