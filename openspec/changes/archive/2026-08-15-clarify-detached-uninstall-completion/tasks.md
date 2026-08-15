# Tasks

## 1. Proposal approval

- [x] 1.1 Obtain human approval for the detached uninstall completion and
  documentation contract in this change.

## 2. Document observable completion

- [x] 2.1 Update the English offline-installation guide to distinguish
  scheduled return, finalizer progress, verified success, and retained failure
  evidence.
- [x] 2.2 Update the Japanese offline-installation guide with the same lifecycle
  and completion criteria.
- [x] 2.3 Record the earlier true bootstrap refusal, the later
  post-scheduling in-progress observation, and the confirmed asynchronous
  completion boundary in the development handoff without adding personal paths
  or protected evidence.
- [x] 2.4 Confirm the documentation does not advise an uninstall retry or manual
  deletion while detached cleanup is still in progress.
- [x] 2.5 Confirm no runtime, deletion-scope, public physics,
  DICOM, external-tool, or protected-data behavior changes are included.
- [x] 2.6 Record that the existing pre-change ZIP remains untouched and must be
  regenerated and revalidated from the eventual merged HEAD before release.

## 3. Validation

- [x] 3.1 Run strict validation for this active change.
- [x] 3.2 Run the focused synthetic offline uninstaller tests.
- [x] 3.3 Run `python -m compileall src`.
- [x] 3.4 Run `python -m pytest -q -p no:cacheprovider`.
- [x] 3.5 Run `python tools/verify_public_tree.py`.
- [x] 3.6 Run `git diff --check`, `git diff --stat`, and
  `git status --short`.

## 4. Completion

- [x] 4.1 Promote the accepted delta into the current Windows offline
  installation specification.
- [x] 4.2 Archive this completed change and strictly validate the resulting
  current specification tree and archived change.
