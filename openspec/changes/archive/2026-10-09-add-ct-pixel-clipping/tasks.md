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
- [x] Complete bounded external synthetic checks for the final supported
      equal-X/Y factor range after separate execution authorization; unequal
      factors are now rejected before the installed tool is run.

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
- [x] After completed approved implementation, promote accepted deltas,
      archive, validate the resulting tree, and provide a reviewable PR.

Implementation checks and the non-default factor evidence gate are recorded
in `validation.md`. The change was kept active while those checks remained.

## Windows follow-up

- [x] Run the separately authorized synthetic `8 8 1` CT2PHITS contract check.
- [x] Enable verified `8 8 1` in GUI/frontend while preserving default `8 8 2`.
- [x] Use Windows Computer Use for synthetic clipping and workflow controls.
- [x] Correct clipped preview actions/sliders and unify application message colors.
- [x] Record explicit validation coverage and remaining unverified items.

## Arbitrary numeric factors and independent output verification

- [x] Record the user's separate approval for CT2PHITS output verification
      and CT voxel-only correction of the known Y-count defect.
- [x] Remove the fixed-factor gate while retaining positive-integer and
      at-least-one-output-voxel checks.
- [x] Recalculate all retained voxel materials from frozen CT pixels and the
      conversion table; stream the comparison and reject other mismatches.
- [x] Verify lattice pitch, minimum bounds, surfaces, cell fill, material
      definitions and densities before accepting a clipped/non-default result.
- [x] Record original and accepted CT voxel hashes when correction occurs.
- [x] Complete focused/full public checks and bounded synthetic GUI review for
      the current diff.
- [x] Complete a separately authorized installed-CT2PHITS synthetic comparison
      for the final supported equal-factor cases before claiming external
      behavior verified.

## Revised supported factor range

- [x] Record the user's rejection of a 13-triple allowlist and approval of
      equal arbitrary positive X/Y factors with Z from `1` through `4`.
- [x] Apply the same factor validation in GUI and CLI before workspace creation.
- [x] Retain output verification for supported factors and document that
      physical voxel pitch also depends on source DICOM spacing.
- [x] Re-run all public checks and review the bounded GUI state after the
      revised factor validation.
- [x] Confirm supported factors against the installed CT2PHITS executable
      only after a separate explicit execution approval.
