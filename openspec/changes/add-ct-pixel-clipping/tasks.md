# Implementation checklist

## Planning

- [x] Inspect policies, Git state, current specifications, active changes,
      GUI/frontend/handoff code, and synthetic test limitations.
- [x] Draft synchronized three-plane selection, six bounds, requirements,
      validation, and clipping/geometry evidence gates.
- [x] Obtain human approval before runtime implementation (2026-10-09 user request).

## Contract evidence

- [ ] Establish supported-version endpoint, axis, slice ordering,
      coarse-graining remainder/alignment, and crop-offset behavior.
- [ ] Define independent expected counts/extents/placement for XY-only,
      Z-only, and combined crops; assess the existing coordinate handoff.
- [ ] If coordinate changes or additional restrictions are needed, revise
      the proposal and obtain the required human decision first.

## Implementation after approval

- [x] Implement the shared six-bound model and pure three-plane mappings.
- [ ] Add optional CLI/frontend pixel/slice ranges and manifest recording,
      preserving full-volume defaults and complete snapshots.
- [x] Implement bounded responsive stack loading and orthogonal views.
- [x] Implement navigation, contrast, labels, pointer readout, two-click
      selection, synchronized fields/overlays, and Apply/Cancel/reset.
- [x] Integrate case invalidation, immutable execution state, and existing
      shell-free CT2PHITS invocation.
- [ ] Verify cropped geometry; do not enable conversion with unresolved
      external contract or coordinate assumptions.
- [ ] Add synthetic pixel fixtures, independent geometry cases, mapping/state
      tests, input/manifest tests, and full-volume regressions.
- [x] Update English/Japanese GUI manuals with the current development-stage boundary.

## Verification and completion

- [x] Run focused tests and a synthetic GUI interaction check.
- [x] Run `python -m compileall src`.
- [x] Run the full pytest command with the existing `.venv` interpreter.
- [x] Run `python tools/verify_public_tree.py`.
- [x] Run `git diff --check`, `git diff --stat`, and `git status --short`.
- [x] Run strict OpenSpec validation when available; otherwise report a
      manual structural review.
- [x] Record unverified real-tool behavior without treating mocks as external
      validation; real execution needs separate explicit authorization.
- [ ] After completed approved implementation, promote accepted deltas,
      archive, validate the resulting tree, and provide a reviewable PR.

Implementation checks and the remaining contract evidence gate are recorded
in `validation.md`. The change remains active and cannot be archived yet.
