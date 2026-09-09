# Tasks

## Proposal

- [x] Inspect the merged progress implementation and relevant specifications.
- [x] Record stage-2 scope, evidence compatibility, ownership, GUI, and test design.
- [x] Validate the proposal with strict OpenSpec validation and public checks.
- [x] Obtain human approval before runtime implementation (user approved with `yes` on 2026-09-09).

## Implementation after approval

- [ ] Add v4 evidence capture and strict validation of the complete execution binding.
- [ ] Preserve existing v2/v3 readers while refusing inferred legacy retry eligibility.
- [ ] Add a read-only incomplete-segment plan and CLI execution mode.
- [ ] Add cross-process ownership covering normal runs, retries, and surviving children.
- [ ] Preserve source attempt evidence and retained artifacts; reject write collisions.
- [ ] Execute only incomplete segments in fresh staging and persist attempt provenance.
- [ ] Add GUI preview/confirmation, selected-workspace binding, counts, and current-attempt ETA.
- [ ] Integrate terminal all-active validation with every downstream/recovery gate.
- [ ] Update user-facing retry and legacy-workspace guidance.

## Verification and closeout

- [ ] Cover retention, repeated retries, no-op completion, failures, and crash boundaries.
- [ ] Cover input/dependency/configuration/tool changes and malformed/missing evidence.
- [ ] Cover path escapes, duplicate IDs, output collisions, and cross-process contention.
- [ ] Cover GUI responsiveness, changed selection/preview, and terminal display binding.
- [ ] Run focused and related synthetic suites.
- [ ] Run `python -m compileall src`.
- [ ] Run `python -m pytest -q -p no:cacheprovider` with temporary data outside the repository.
- [ ] Run `python tools/verify_public_tree.py`.
- [ ] Run `openspec.cmd validate --all --strict` and change-specific strict validation.
- [ ] Run `git diff --check`, `git diff --stat`, and `git status --short`.
- [ ] Review the implementation in its own PR; stop at the repository correction limit.
- [ ] Promote accepted deltas, archive the completed change, and validate the resulting tree.

Real PHITS and external-workspace verification is not authorized and is not
represented by synthetic test success. No implementation task is complete yet.

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
