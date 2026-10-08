# Implementation checklist

## 1. Proposal and approval

- [x] Inspect the existing standalone change, Structure mapping code, and
  relevant public safety boundaries.
- [x] Record that a Structure name alone cannot determine PHITS membership.
- [x] Draft GUI, explicit selection, coordinate, and reporting requirements.
- [x] Validate this proposal's structure and resolve material ambiguities.
- [x] Obtain explicit human approval before runtime implementation.

## 2. Implementation (after approval)

- [x] Add a separate GUI with explicit case/member and region selectors.
- [x] Add validated RT Structure, RT Plan, CT-series, and PHITS mesh binding
  with transient same-grid membership and no workflow-authority write.
- [x] Present each selected case's sphere or Structure result with clear
  cell-sum, mean-dose, and voxel r.err labels.
- [x] Provide optional safe new-only reports and usage documentation.

## 3. Validation (after approval)

- [x] Add synthetic selector, geometry, population, error-state, and export
  tests; use no real DICOM or local calculation outputs in automated tests.
- [x] Run focused tests, compilation, full pytest, public-tree audit, and
  Git diff/status checks.
- [x] Assess the explicitly selected local geometry read-only. Complete frozen
  CT2PHITS evidence was unavailable, so real Structure values remain
  unverified; no real DICOM-derived mask or result was saved.

## 4. Completion (after approval)

- [ ] Promote accepted requirements, archive the completed OpenSpec change,
  and validate the resulting tree.
- [ ] Prepare a reviewable PR within the authorized external-write scope.

The primary user approved implementation of this proposal on 2026-10-08.
The primary user authorized PR publication on 2026-10-08. Final validation,
publication, and the completion archive are now in progress.

## Implementation validation record (2026-10-08)

- Synthetic focused tests: 17 passed, including explicit selectors,
  end-to-end frozen CT/RT Plan/RT Structure mapping, one/many/no native
  cells, boundary and frame failures, report destination rejection, and
  the standalone script integration path.
- Hidden Tk GUI construction and disabled initial action state: passed.
- `python -m compileall src` and independent tool `py_compile`: passed.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`: 1491 passed,
  15 skipped, one intentional duplicate-ZIP-member warning.
- Public-tree audit and Git diff/status checks: passed after staging the
  intended files; unrelated untracked files were left untouched.
- OpenSpec CLI was unavailable. The active proposal and deltas received a
  manual structural review. Promotion and archive await the required PR
  decision and are not represented as complete.

## Proposal-stage validation record (2026-10-08)

- Read-only inspection of three explicitly supplied RT Structure Sets found
  one display name `Chamber` and six closed planar contours in each. No
  patient identifier, file content, or local result was added to this tree.
- The existing Structure evaluator requires RT Plan isocenter, frozen CT
  series, and dose-grid placement in addition to RT Structure contours.
  This proposal requires those inputs explicitly and does not infer geometry
  from ROIName alone.
- OpenSpec CLI was unavailable. Manual structural review passed for the four
  UTF-8 files, required headings, five added requirements, and their
  WHEN/THEN scenarios. Whitespace and final-newline checks passed.
- `python -m compileall src`: passed.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`: 1484 passed,
  15 skipped, with one expected duplicate-ZIP-member warning (142.96 seconds).
- `python tools/verify_public_tree.py`: passed for 417 tracked files. This
  untracked proposal was reviewed separately; it is not part of that audit.
- `git diff --check`, `git diff --cached --check`, diff statistics, and
  `git status --short`: passed/read. Existing staged implementation and
  pre-existing untracked files were preserved.
