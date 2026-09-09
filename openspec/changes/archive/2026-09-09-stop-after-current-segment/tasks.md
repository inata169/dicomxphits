# Tasks

## Proposal

- [x] Confirm PR #61 merge, branch deletion, and clean synchronized main baseline.
- [x] Read existing runtime, retry, GUI, and repository/OpenSpec contracts.
- [x] Define stop ordering, ownership, acknowledgement, evidence, GUI and test scope.
- [x] Validate the proposal with strict OpenSpec and public checks.
- [x] Obtain human approval before implementation (user approved with `yes` on 2026-09-09).

## Implementation after approval

- [x] Add a bounded invocation-scoped control channel and serialized acknowledgement/launch.
- [x] Keep direct-child ownership and GUI responsiveness through pipe and controller failures.
- [x] Add v5 stop metadata, strict terminal state validation and distinct exit code.
- [x] Preserve v2/v3/v4 reading and eligible v4 retry; support mixed v4/v5 provenance.
- [x] Apply failure/completion/stop precedence without changing no-request behavior.
- [x] Add GUI stop action, request-sent/pending/stopped presentation and identity checks.
- [x] Keep downstream disabled for stopped or otherwise incomplete records.
- [x] Reuse explicit incomplete-segment preview after stop and reset prior stop requests.
- [x] Document supported scope, unavailable cases, and limitations.

## Verification and closeout after implementation

- [x] Test deterministic launch/stop races and final completion/failure precedence.
- [x] Test retained outputs, repeated retries, mixed versions and downstream refusal.
- [x] Test malformed/stale control, persistence errors, crash and child ownership boundaries.
- [x] Test GUI adapter responsiveness, acknowledgement, workspace/run binding and exit/summary mismatch with synthetic/unit tests and callback inspection.
- [x] Run focused tests, compile, full pytest, public audit, strict OpenSpec and Git checks.
- [x] Review the independent stage-3 PR under the bounded correction policy.
- [x] Promote accepted deltas, archive the completed change, and validate the resulting tree.

Runtime implementation is approved; real PHITS verification is not. Keep
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

## Implementation validation (2026-09-09)

The proposal was subsequently approved and runtime work began on the same
branch. Stop control uses a bounded reader queue; the owner thread alone writes
acknowledgements and commits launches. While the child adapter waits on a worker,
the owner polls control; persistence failure still joins the child before staging
cleanup. GUI controller output is drained concurrently and stop requests are
sent off the Tk thread. Stopped workspace display and explicit retry both check
the local binding, rather than trusting a terminal label.

- Initial stop/runner/retry/GUI focused tests: 217 passed, 2 skipped.
- Synthetic pipe/ownership and stop tests: 28 passed.
- Related suites including workspace recovery: 248 passed, 2 skipped.
- Final stop/GUI/recovery focused suite: 178 passed, 1 skipped.
- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: 301 tracked files passed (new files staged).
- `openspec.cmd validate --all --strict`: 15 passed, 0 failed.
- `git diff --cached --check`: passed.

One added existing-workspace display test initially omitted the required summary
argument (1 failed / 177 passed / 1 skipped). Passing the intended summary fixed
the test on its next identical focused run (178 passed / 1 skipped). No runtime
guard or expected rejection was weakened. Initial full pytest passed with
1074 passed / 10 skipped. The final bounded-JSON reader check (deep invalid
JSON within the size limit) also passed: stop-specific suite 29 passed.
Full-suite confirmation on that final reader change, PR review, and archive
closeout are pending. Interactive desktop and real PHITS verification are not
claimed; only synthetic workspaces, fake runners, and temporary Python children
were used.

Final initial implementation at `d20ad50`: full pytest confirmation passed
(1074 passed / 10 skipped), and Ubuntu/Windows CI runs #547 and #548 succeeded.

PR #62 review correction round 1: verified the reported ability to misidentify
a retained or previously completed result as the acknowledged boundary. New
committed entries now record the current producer run ID immediately. Boundary
validation requires a non-retained current-run entry and acknowledgement within
its monotonic execution interval. Regression tests corrupt both retained and
earlier-completed boundaries and prove rejection by retry planning and GUI stop
confirmation. Related tests: 251 passed / 2 skipped; the two corruption cases
also passed separately (2 passed / 29 deselected). Compile and all 15 strict
OpenSpec checks passed. No additional verified review blocker remained after
this minimal correction. Independent re-review is not claimed; no optional
review loop or scope expansion was started. Final full checks and archive follow.

Final runtime validation at `104bc38`: `python -m pytest -q -p no:cacheprovider
--basetemp <outside-repository-temp-directory>` passed (1076 passed / 10 skipped).
Compile, public audit (301 files), strict OpenSpec (15 items), and Git diff checks
passed. Ubuntu and Windows both succeeded in CI runs #549 and #550. PR #62
remains draft: the human decides ready/merge. Specification promotion/archive is
the sole remaining closeout operation; no real-tool verification is claimed.

Archive closeout: `openspec.cmd archive stop-after-current-segment --yes`
validated and promoted four added and three modified requirements, then moved
this change to the dated archive. The sole unchecked task at invocation was the
archive operation itself. Generated placeholder Purpose and blank EOF lines were
cleaned up without changing requirements. All 15 current specs pass strict
validation; archived proposal/deltas are also checked directly with the installed
OpenSpec strict Validator. The final public audit includes the new stop spec
(302 tracked files). Archive changes are documentation/specification only.
