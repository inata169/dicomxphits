# Guided CT2PHITS GUI Tasks

## 1. Specification and Design

- [x] 1.1 Review the repository rules, current GUI, accepted CT2PHITS frontend
  contract, handoff document, and existing local path settings.
- [x] 1.2 Audit the supplied current-screen evidence and identify usability and
  accessibility risks.
- [x] 1.3 Record the proposed GUI integration, persistence, visual, and safety
  boundaries.
- [x] 1.4 Obtain human approval of the OpenSpec proposal. The human maintainer
  approved implementation on 2026-08-02.
- [x] 1.5 Obtain human selection of a generated visual direction. Visual
  direction 1 was selected by the human maintainer on 2026-08-02.

## 2. Implementation

- [x] 2.1 Add CT2PHITS source inputs, workspace state, validation, command
  construction, and stage execution through the existing CLI.
- [x] 2.2 Apply the documented frozen handoff to downstream preparation after a
  successful frontend result.
- [x] 2.3 Add safe path suggestions without filesystem or installation discovery.
- [x] 2.4 Add backward-compatible local stable-setting persistence and separate
  Browse history for every path field.
- [x] 2.5 Rebuild the Tkinter presentation with grouped `ttk` sections, the
  selected blue visual system, stage status, focused errors, and keyboard use.
- [x] 2.6 Keep stage execution responsive and prevent overlapping external
  commands.
- [x] 2.7 Preserve the advanced manual validated-DATfiles handoff.
- [x] 2.8 Update launch and workflow documentation.

## 3. Automated and Visual Validation

- [x] 3.1 Add synthetic/mock focused tests for CT2PHITS GUI command and frozen
  handoff behavior.
- [x] 3.2 Add focused tests for suggestions, settings migration, non-persisted
  safety controls, and independent Browse histories.
- [x] 3.3 Add focused tests for active-stage exclusion and controlled error
  reporting.
- [x] 3.4 Render and inspect the GUI using only synthetic placeholder paths.
- [x] 3.5 Run `python -m compileall src`. Passed on Windows with the
  repository-local Python 3.12 environment.
- [x] 3.6 Run `python -m pytest -q -p no:cacheprovider`. The final
  review-corrected branch passed all `470` tests, including `45` focused GUI
  tests.
- [x] 3.7 Run `python tools/verify_public_tree.py`. Public tree audit passed
  after staging the promoted and archived specifications, with 91 tracked files
  checked.
- [x] 3.8 Run `git diff --check`, `git diff --stat`, and `git status --short`.
  All checks completed; only the approved GUI change is present.

## 4. Completion

- [x] 4.1 Update the task checklist with exact validation evidence and any
  explicitly deferred non-blocking item.
- [x] 4.2 Promote the accepted delta into the current specification tree.
- [x] 4.3 Archive the completed change and validate the resulting OpenSpec tree.
  The accepted specification was promoted and the change was archived on
  2026-08-02; strict CLI validation was unavailable, so a manual structural
  review confirmed seven requirements and thirteen scenarios in both forms.
  The post-merge documentation audit repeated that structural comparison and
  found no active change directory or unpromoted delta.
- [x] 4.4 Create a reviewable pull request without merging it automatically.
  Draft pull request #5 was created through the GitHub connector on 2026-08-02:
  https://github.com/inata169/dicomxphits/pull/5. After final review reported no
  major issues and the human explicitly requested the merge, it was squash
  merged as `bc6296d5f6949f461e7d50b86db6a0b4579e048d`; its local and remote
  feature branches were then deleted.
