# Implementation checklist

## Planning

- [x] Inspect policies, Git state, current specifications, active changes,
      GUI/frontend/handoff code, and synthetic test limitations.
- [x] Draft synchronized three-plane selection, six bounds, requirements,
      validation, and clipping/geometry evidence gates.
- [x] Obtain human approval before runtime implementation (2026-10-09 user request).
- [x] Record the user's numeric X/Y/Z coarse-graining extension in the
      active proposal and design (2026-10-09 follow-up request).

## Contract evidence

- [x] Establish supported-version endpoint, axis, slice ordering,
      coarse-graining remainder/alignment, and crop-offset behavior for the
      approved `8 8 2` clipped path using the authorized synthetic tool run.
- [x] Define expected counts/extents/placement for XY-only, Z-only, and
      combined crops; assess both CT2PHITS handoffs. The combined case is
      checked with a fake runner, not a second real-tool run.
- [x] Revise the proposal and obtain separate human decisions for the
      selected-first-slice coordinate handoff and warning-plus-conversion
      behavior for non-divisible default-factor boxes.
- [ ] Establish supported-tool behavior for non-default factor triples before
      enabling their conversion; unequal X/Y factors lost material in the
      installed version.

## Implementation after approval

- [x] Implement the shared six-bound model and pure three-plane mappings.
- [x] Add optional CLI/frontend pixel/slice ranges and manifest recording,
      preserving full-volume defaults and complete snapshots.
- [x] Add numeric GUI/CLI coarse-graining fields, validation, input and
      manifest recording, with `8 8 2` as the default.
- [x] Implement bounded responsive stack loading and orthogonal views.
- [x] Implement navigation, contrast, labels, pointer readout, two-click
      selection, synchronized fields/overlays, and Apply/Cancel/reset.
- [x] Integrate case invalidation, immutable execution state, and existing
      shell-free CT2PHITS invocation.
- [x] Verify cropped geometry for the approved default factors, with raw
      origin and output count checks; also verify and enable `8 8 1`, keeping
      other factor triples gated.
- [x] Add synthetic pixel fixtures, independent geometry cases, mapping/state
      tests, input/manifest tests, and full-volume regressions.
- [x] Update English/Japanese GUI manuals with warning, conversion, retained
      bounds, and factor limitations. Match CT child-window colors to the GUI.

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

Implementation checks and the non-default factor evidence gate are recorded
in `validation.md`. The change remains active and cannot be archived yet.

## Windows follow-up

- [x] Run the separately authorized synthetic `8 8 1` CT2PHITS contract check.
- [x] Enable verified `8 8 1` in GUI/frontend while preserving default `8 8 2`.
- [x] Use Windows Computer Use for synthetic clipping and workflow controls.
- [x] Correct clipped preview actions/sliders and unify application message colors.
- [x] Record explicit validation coverage and remaining unverified items.
