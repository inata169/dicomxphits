# Research geometry recovery acceptance: implementation report

Date: 2026-10-27. Branch: `codex/research-geometry-recovery-rtdose`.
Starting HEAD: `91aa975`. No real external tool execution is included.

## Behavior

The separate research route accepts saved tally outputs only after full
verification and an explicit operator acknowledgement and reason. Lost and
unrecovered counts must remain zero; a positive recovering total has no
acceptance cap but must agree with every recorded region-pair count. Exactly
one active segment may have failed, solely for geometry diagnostics, with
return code zero and final batch equal to prepared `maxbch`.

Original summary, preflight, manifest, companion output and staging bytes are
preserved. PHITS stays failed. The GUI does not recalculate PHITS or launch any
external tool during acceptance. Sumtally and RTDOSE actions remain separate.
Each revalidates the receipt and records its SHA-256 and segment identity.
Ordinary success validation and existing failure-message order are preserved.

The v2 receipt uses relative artifact paths, a canonical preview digest,
invocation-bound retained evidence, new-only publication, a lease, and receipt
publication last. Prototype receipts and historical runs without prospective
staging evidence are ineligible. A fixed-path receipt also prevents PHITS
execution or retry before mutation, even when that receipt is malformed.

## Changed files

- Runtime: `src/dicomxphits/research_geometry_recovery.py` (replaces the inherited
  unapproved prototype), `research_geometry_gui.py`, `phits_geometry_diagnostics.py`,
  `run_segments.py`, `segment_retry.py`, `workspace_recovery.py`,
  `prepare_sumtally.py`, `prepare_rtdose.py`, `gui.py`, and `pyproject.toml`.
- Tests: `tests/test_research_geometry_recovery.py`,
  `test_research_geometry_recovery_evidence.py`, `test_gui_geometry_recovery.py`,
  `test_gui_action_readiness.py`, and
  `tests/fixtures/phits_geometry_recovery_summary.synthetic.txt`.
- Documentation: `docs/gui-user-guide.md`,
  `docs/instruction/_manual/gui-manual.en.md`, and `gui-manual.ja.md`.
- Specifications: the approved change documents and deltas for
  `research-geometry-recovery-acceptance`, `phits-segment-runtime`,
  `phits-segment-retry`, and `guided-gui-workflow`; promotion/archive status is
  recorded in `tasks.md`.

## Validation

Detailed failed attempts and bounded corrections remain in `tasks.md`.
Focused regression: 521 passed, three skipped. GUI callback and independent
hidden-Tk tests: 43 passed. Hidden-Tk verification uses an isolated subprocess,
synthetic workspace and defaults, and an audit hook forbidding external
execution. It covers responsive checks, affirmative acceptance, No, closure,
and an empty reason.

The final public-suite and post-archive results are recorded below when
available. Commands use Python 3.12 from the existing virtual environment for
pytest, with a fresh short OS temporary basetemp because sandboxed temporary
storage and Windows path-length limits were independently encountered:

```text
python -m compileall src
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp <fresh-short-OS-temporary-directory> --tb=short
python tools/verify_public_tree.py
.venv/Scripts/openspec.cmd validate add-research-geometry-recovery-acceptance --strict
git diff --check
git diff --stat
git status --short
```

## Limits and stopping boundary

- The supported raw table grammar comes from the operator's supplied example.
  It is not independently validated against an original nonzero PHITS output;
  all tracked numeric examples are synthetic. Unknown layouts fail closed.
- No real PHITS, Sumtally or phits2dicom execution or end-to-end physics/dose
  validation was performed. This does not establish clinical validity.
- No historical external workspace was re-accepted or written. The ongoing
  user GUI and 12-thread PHITS calculation were not controlled or modified.
- DICOM attributes, dose factors, normalization, MU, coordinates, public
  aperture boundary, and PHITS physics were not changed by this capability.
- Unrelated local configuration, screenshots, and old test-temp storage remain
  untouched. The standard tree audit checks indexed files; an additional
  scoped snapshot audit covers the new/modified working-tree files.
- The pre-existing canonical OpenSpec strict baseline was 19 failures among
  22 specifications, all reported as requirement-length warnings. Unrelated
  specification text has not been rewritten to suppress those warnings.
- No merge, tag modification, force-push, or release is included.


## Final source results

- Final full pytest: **1648 passed, 16 skipped, one existing warning**, 262.10
  seconds. The warning is the intentional duplicate-ZIP-member test fixture.
- Compilation, standard public-tree audit (459 indexed files), active-change
  strict validation and `git diff --check`: passed.
- CLI module help: passed. The console-script entry is registered in
  `pyproject.toml`; local editable-install metadata was not rewritten while
  the user's calculation was active. It can also be invoked with
  `python -m dicomxphits.research_geometry_recovery`.
- Review correction rounds after implementation: one verified receipt-schema
  correction (tool-version syntax), with a failing-then-passing regression.
  No verified merge-blocking runtime defect remains after the final suite.
- Existing archived-task validation also has one unrelated historical failure:
  `2026-08-07-add-windows-offline-installer`, 24/25 tasks checked. It was found
  before this archive and has not been changed.


## Specification closeout and stopping outcome

The OpenSpec CLI promoted all four capabilities (14 added and six modified
requirements) and archived this change under the date-prefixed directory.
Its generated Purpose placeholder was replaced with the approved concrete
purpose. The new canonical capability and archived deltas pass strict
validation with zero findings. The full canonical result remains 19 failures
from exactly 96 baseline length warnings (23 total specifications, four pass),
with no new finding from this change. The pre-existing historical archived-task
failure is reported rather than changed.

Implementation and synthetic acceptance are complete. Changes remain local and
reviewable on the existing feature branch: no commit, push, PR, merge, tag or
release was performed. Any GitHub publication is a separate external-write
step. Stop after the final status/audit checks; do not start optional work.
The running GUI was not restarted; a newly launched GUI after the current
calculation finishes will load the changed source.


Final post-archive checks:

- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: passed, 459 indexed files.
- Scoped current-file snapshot audit: passed, 30 changed/new files and 474
  combined entries, zero issues; UTF-8 and trailing whitespace checked.
- `git diff --check`: passed (line-ending notices only).
- `git diff --stat`: 15 tracked files, 668 insertions and 51 deletions; this
  excludes the 15 new task-scoped files. The report above also lists new files.
- `git status --short`: inspected. The unrelated configuration/screenshots and
  an existing inaccessible old test-temp warning are preserved untouched.
- Archived strict delta validation: passed with zero findings using the
  installed CLI's Validator API. The path-qualified name is unsupported by
  the CLI's single-change command.
- Canonical strict validation: 23 items, four pass, the same 19 baseline
  failures from 96 length warnings; the new capability passes individually.
- Archived-task strict validation: this change passes with zero incomplete
  tasks; globally 40 of 41 archives pass, with only the previously recorded
  historical offline-installer archive failing.
- The active change directory is absent. No runtime or test changes followed
  the final 1648-pass full suite; subsequent edits were specification/archive
  cleanup and these reports only.


## Authorized GitHub review phase: 2026-10-27

The human approved publication as a draft PR, explicitly requested the GitHub
plugin and `@codex review`, and authorized fixing verified in-scope defects
without renewed human approval until review reports no remaining defects.
This supersedes the earlier local-only stopping checkpoint and the default
six-round cap for this requested review loop. It does not authorize real-tool
execution, real-data writes, physics/DICOM changes, scope expansion or merging.
The existing branch and PR will be used throughout; unrelated local files are
excluded. Review findings and corrections will be recorded with their evidence
and validation results.
