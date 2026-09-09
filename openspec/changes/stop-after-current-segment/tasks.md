# Tasks

## Proposal

- [x] Confirm PR #61 merge, branch deletion, and clean synchronized main baseline.
- [x] Read existing runtime, retry, GUI, and repository/OpenSpec contracts.
- [x] Define stop ordering, ownership, acknowledgement, evidence, GUI and test scope.
- [x] Validate the proposal with strict OpenSpec and public checks.
- [ ] Obtain human approval before implementation.

## Implementation after approval

- [ ] Add a bounded invocation-scoped control channel and serialized acknowledgement/launch.
- [ ] Keep direct-child ownership and GUI responsiveness through pipe and controller failures.
- [ ] Add v5 stop metadata, strict terminal state validation and distinct exit code.
- [ ] Preserve v2/v3/v4 reading and eligible v4 retry; support mixed v4/v5 provenance.
- [ ] Apply failure/completion/stop precedence without changing no-request behavior.
- [ ] Add GUI stop action, request-sent/pending/stopped presentation and identity checks.
- [ ] Keep downstream disabled for stopped or otherwise incomplete records.
- [ ] Reuse explicit incomplete-segment preview after stop and reset prior stop requests.
- [ ] Document supported scope, unavailable cases, and limitations.

## Verification and closeout after implementation

- [ ] Test deterministic launch/stop races and final completion/failure precedence.
- [ ] Test retained outputs, repeated retries, mixed versions and downstream refusal.
- [ ] Test malformed/stale control, persistence errors, crash and child ownership boundaries.
- [ ] Test GUI responsiveness, acknowledgement, workspace/run binding and exit/summary mismatch.
- [ ] Run focused tests, compile, full pytest, public audit, strict OpenSpec and Git checks.
- [ ] Review the independent stage-3 PR under the bounded correction policy.
- [ ] Promote accepted deltas, archive the completed change, and validate the resulting tree.

No runtime implementation or real PHITS verification is authorized yet. Keep
this proposal active; do not mark implementation tests complete from baseline
test success. Physics, geometry, DICOM semantics, MU and dose conversion are
unchanged. External failed workspaces and retained staging remain excluded.

## Proposal validation record (2026-09-09)

Using the existing `.venv` interpreter and synthetic temporary workspaces outside
the repository:

- `python -m pytest -q -p no:cacheprovider tests/test_run_segments.py tests/test_segment_retry.py tests/test_gui.py --basetemp <outside-repository-temp-directory>`:
  194 passed, 2 skipped.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>`:
  1045 passed, 10 skipped.
- `python tools/verify_public_tree.py`: 298 tracked files passed, including six
  staged proposal documents.
- `openspec.cmd validate stop-after-current-segment --strict`: passed.
- `openspec.cmd validate --all --strict`: 15 passed, 0 failed.
- `git diff --cached --check`, diff/stat and status: passed; only six proposal
  files changed, with no runtime or current-spec changes.

These tests validate the existing baseline, not the proposed stop capability.
No proposed feature was implemented or tested. No real PHITS, external-workspace,
or interactive desktop execution was performed. Proposal remains active awaiting
human approval; implementation tasks and archive closeout remain incomplete.
