## 1. Proposal

- [x] 1.1 Inspect current progress, stop, runtime and tally boundaries.
- [x] 1.2 Define observation authority, version scope, metrics and unavailable states.
- [x] 1.3 Validate this proposal and run required public checks.
- [x] 1.4 Obtain human approval of the proposal before implementation.

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

Proposal status: human approved; implementation paused at task 2.1. Real
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
verification is claimed. Implementation remains incomplete, so the
change is deliberately active and has not been promoted or archived.

## Implementation prerequisite check (2026-09-09)

The human approved implementation. No runtime changes have been made: task 2.1
requires stopping if the exact supported grammar cannot be established.
The official 3.35 manual, section 4.9 (printed pages 44-45), describes a
T-Track example whose version caption is 3.28, rather than a complete 3.35
Windows OpenMP 3D T-Deposit dose/error pair. Section 3.2 describes the remaining
batch counter but does not provide the complete record grammar required by
this proposal. These examples do not establish the exact version/mode markers
and paired history/restart metadata needed by the proposed parser. This is an
evidence gap, not proof that PHITS 3.35 lacks the feature or uses a different
format. The current public HTML manual is version 3.37 and is not substituted.

Source: https://phits.jaea.go.jp/manual/manualE-phits335.pdf

Needed evidence: a documented complete target-format example, or separately
approved synthetic PHITS 3.35 OpenMP observations of batch output, version
identity and the matching generated 3D dose/error pair. No installed tool,
distribution, real output or external workspace was inspected. No new execution
permission is inferred. A minimal synthetic verification plan may be proposed
to the human; this note does not authorize its execution. Do not fabricate a
3.35 fixture by replacing the version string in an older example.
