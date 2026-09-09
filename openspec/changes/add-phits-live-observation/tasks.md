## 1. Proposal

- [x] 1.1 Inspect current progress, stop, runtime and tally boundaries.
- [x] 1.2 Define observation authority, version scope, metrics and unavailable states.
- [x] 1.3 Validate this proposal and run required public checks.
- [ ] 1.4 Obtain human approval of the proposal before implementation.

## 2. Implementation after approval

- [ ] 2.1 Document exact supported 3.35 grammar/version markers from official evidence; stop if insufficient.
- [ ] 2.2 Add bounded read-only parsers and authored synthetic fixtures.
- [ ] 2.3 Add generation-bound staged observation and atomic optional sidecar.
- [ ] 2.4 Add responsive GUI availability, remaining-batch and per-cell error presentation.
- [ ] 2.5 Cover stale/torn/unsafe/oversized data, reset races, excluded values and mismatched dose/error pairs.
- [ ] 2.6 Verify unchanged input/output/control bytes, run outcomes, retry, stop and downstream gates.

## 3. Validation and closeout after implementation

- [ ] 3.1 Run focused parser, runner, GUI, retry, stop and downstream regressions.
- [ ] 3.2 Run compile, full pytest, public-tree audit, OpenSpec strict and Git diff/status checks.
- [ ] 3.3 Report synthetic versus separately approved real-tool/desktop verification explicitly.
- [ ] 3.4 Complete review within repository stopping rules; resolve only verified blockers.
- [ ] 3.5 Promote accepted deltas, archive the completed change and validate the resulting tree.

Proposal status: awaiting human approval; no runtime implementation. Real
PHITS, distribution inspection, patient data and external workspaces have not
been used. Real-tool verification is not authorized by proposal creation.

Proposal validation (2026-09-09; repository Python 3.12 virtual environment):

- `openspec.cmd validate add-phits-live-observation --strict`: passed.
- `python -m pytest -q -p no:cacheprovider tests/test_segment_stop.py --basetemp <outside-repository-temp-directory>`: 33 passed.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>`: 1078 passed, 10 skipped.
- `python tools/verify_public_tree.py`: 307 tracked files passed.
- `openspec.cmd validate --all --strict`: 16 items passed.
- `git diff --cached --check`, `git diff --cached --stat`, and `git status --short`: reviewed; only these five proposal files changed.

No runtime or accepted-specification changes. Full tests observe the existing
implementation, not implementation of this proposal. No real PHITS or desktop
verification is claimed. Approval and implementation remain incomplete, so the
change is deliberately active and has not been promoted or archived.
