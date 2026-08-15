# Tasks

## 1. Proposal approval

- [x] 1.1 Obtain human approval for the root-file and child-directory
  protection contract in this change.

## 2. Specification alignment

- [x] 2.1 Promote the accepted Bundle Integrity Inventory requirement into the
  current Windows offline installation specification.
- [x] 2.2 Confirm the promoted requirement preserves fail-closed behavior for
  root-file protection and every required child-directory handle.
- [x] 2.3 Confirm no runtime, public physics, DICOM, dose, or protected-data
  behavior changes are included.

## 3. Validation

- [x] 3.1 Run strict validation for this change.
- [x] 3.2 Run the focused synthetic offline bootstrap tests.
- [x] 3.3 Run `python -m compileall src`.
- [x] 3.4 Run `python -m pytest -q -p no:cacheprovider`.
- [x] 3.5 Run `python tools/verify_public_tree.py`.
- [x] 3.6 Run `git diff --check`, `git diff --stat`, and
  `git status --short`.

## 4. Completion

- [x] 4.1 Resolve the corresponding pull-request review thread after the
  accepted specification is present and validated.
- [x] 4.2 Promote the accepted delta, archive this change, and validate the
  resulting current specification tree and archived change.
