# Tasks

## 1. Proposal approval

- [ ] 1.1 Obtain human approval for the root-file and child-directory
  protection contract in this change.

## 2. Specification alignment

- [ ] 2.1 Promote the accepted Bundle Integrity Inventory requirement into the
  current Windows offline installation specification.
- [ ] 2.2 Confirm the promoted requirement preserves fail-closed behavior for
  root-file protection and every required child-directory handle.
- [ ] 2.3 Confirm no runtime, public physics, DICOM, dose, or protected-data
  behavior changes are included.

## 3. Validation

- [ ] 3.1 Run strict validation for this change.
- [ ] 3.2 Run the focused synthetic offline bootstrap tests.
- [ ] 3.3 Run `python -m compileall src`.
- [ ] 3.4 Run `python -m pytest -q -p no:cacheprovider`.
- [ ] 3.5 Run `python tools/verify_public_tree.py`.
- [ ] 3.6 Run `git diff --check`, `git diff --stat`, and
  `git status --short`.

## 4. Completion

- [ ] 4.1 Resolve the corresponding pull-request review thread after the
  accepted specification is present and validated.
- [ ] 4.2 Promote the accepted delta, archive this change, and validate the
  resulting current specification tree and archived change.
- [ ] 4.3 Request a new exact-HEAD Codex review and confirm the exact-HEAD CI
  succeeds before merge.
