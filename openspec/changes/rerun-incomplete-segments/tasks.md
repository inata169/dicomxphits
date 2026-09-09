# Tasks

## Proposal

- [x] Inspect the merged progress implementation and relevant specifications.
- [x] Record stage-2 scope, evidence compatibility, ownership, GUI, and test design.
- [x] Validate the proposal with strict OpenSpec validation and public checks.
- [x] Obtain human approval before runtime implementation (user approved with `yes` on 2026-09-09).

## Implementation after approval

- [x] Add v4 evidence capture and strict validation of the complete execution binding.
- [x] Preserve existing v2/v3 readers while refusing inferred legacy retry eligibility.
- [x] Add a read-only incomplete-segment plan and CLI execution mode.
- [x] Add cross-process ownership covering normal runs, retries, and surviving children.
- [x] Preserve source attempt evidence and retained artifacts; reject write collisions.
- [x] Execute only incomplete segments in fresh staging and persist attempt provenance.
- [x] Add GUI preview/confirmation, selected-workspace binding, counts, and current-attempt ETA.
- [x] Integrate terminal all-active validation with every downstream/recovery gate.
- [x] Update user-facing retry and legacy-workspace guidance.

## Verification and closeout

- [x] Cover retention, repeated retries, no-op completion, failures, and crash boundaries.
- [x] Cover input/dependency/configuration/tool changes and malformed/missing evidence.
- [x] Cover path escapes, duplicate IDs, output collisions, and cross-process contention.
- [x] Cover GUI worker responsiveness, changed selection/preview, and terminal display binding with synthetic/unit checks and callback inspection.
- [x] Run focused and related synthetic suites.
- [x] Run `python -m compileall src`.
- [x] Run `python -m pytest -q -p no:cacheprovider` with temporary data outside the repository.
- [x] Run `python tools/verify_public_tree.py`.
- [x] Run `openspec.cmd validate --all --strict` and change-specific strict validation.
- [x] Run `git diff --check`, `git diff --stat`, and `git status --short`.
- [x] Review the implementation in its own PR; stop at the repository correction limit.
- [ ] Promote accepted deltas, archive the completed change, and validate the resulting tree.

Real PHITS and external-workspace verification is not authorized and is not
represented by synthetic test success. Interactive desktop verification is
not claimed. PR #61 review identified one blocker, addressed in correction
round 2 below; specification archive remains pending final checks.

## Implementation validation results

Validated on 2026-09-09 with the existing `.venv` interpreter:

- Focused runner suite: 41 passed, 1 skipped.
- Related runner, GUI, recovery and downstream suites: 306 passed, 2 skipped.
- Retry and output-security focused suite: 48 passed, 8 skipped.
- Closeout GUI/retry suite: 150 passed, 1 skipped.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>`:
  1042 passed, 10 skipped.
- `python tools/verify_public_tree.py`: 291 tracked files passed, including new files.
- `openspec.cmd validate --all --strict`: 14 passed, 0 failed before archive.
- `git diff --cached --check`: passed.

Observed implementation failures and bounded fixes were retained in this record:
the initial runner suite had 26 failures caused by validating a nonexistent
optional preparation directory; after allowing absent preparation evidence to
disable retry, one failure remained in existing OMP validation precedence.
Restoring that precedence yielded 41 passed / 1 skipped. A related GUI test
failed because an unused invalid installation path was forwarded; forwarding
only a configured existing directory restored 306 passed / 2 skipped.
An interrupted-child test fixture initially needed a deterministic readiness
handshake; the final synthetic process test verifies ownership after controller
death. Final callback inspection found that unexpected selection changes also
needed to suppress the error terminal callback; the closeout focused suite passed.
No guard or acceptance condition was weakened.

PR CI correction round 1: Ubuntu reported one existing linked-log test failure
(976 passed / 75 skipped). Binding enumeration resolved a linked output before
the established guarded-publication check, producing the wrong exception type.
Keep output targets lexical in the binding so the established path guard rejects
the link before any child starts. Local Windows skips this symlink case;
Ubuntu CI is required to verify the platform-specific regression.

Correction round 1 verified: focused runner/retry 68 passed / 1 skipped;
full local pytest 1042 passed / 10 skipped; public audit 291 passed; compile
passed; both Ubuntu and Windows CI runs #540 and #541 succeeded.

PR review correction round 2: the reviewer correctly identified that the
canonical `write_libpath()` output uses `file(1)` and was incorrectly classified
as an unsupported dependency, disabling the approved feature for prepared
workspaces. Accept only the canonical workspace-root `libpath.inp` directive
when its declared installation matches the explicitly configured runtime tree.
Its bytes remain in the input binding, and downstream read-only inspection does
not resolve a former computer's tool path. Every retry fixture now includes the
real project writer's synthetic libpath, with additional mismatch/extra-directive/
wrong-file negative tests. Focused runner/retry: 71 passed / 1 skipped. No
additional verified merge blocker remained after this correction; no optional
scope expansion or new review loop was started.

## Proposal validation results

Validated on 2026-09-09, using the existing `.venv` Python interpreter:

- `openspec.cmd validate rerun-incomplete-segments --strict`: passed.
- `openspec.cmd validate --all --strict`: 14 passed, 0 failed.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>`:
  1015 passed, 10 skipped. These are baseline tests, not proof of the proposed feature.
- `python tools/verify_public_tree.py`: 287 tracked files passed, including the six staged proposal files.
- `git diff --cached --check`: passed; staged diff/status contain only these six files.

Initial strict validation rejected one requirement whose SHALL clause wrapped
across lines. Rewording that sentence resolved the parser error on the next check;
no requirement was relaxed. No additional feature tests exist before approval.
