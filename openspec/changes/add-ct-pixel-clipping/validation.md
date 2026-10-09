# Planning validation record

This record concerns the proposal only, not implementation acceptance.

- Branch: `codex/plan-ct-pixel-clipping`, based on `ec4fbec`.
- Initial repository: `main`, expected origin, tags v1.0.0 through v1.1.1.
- Existing untracked local configuration/screenshots were left untouched and
  were not included in the proposal.
- New files, all under `openspec/changes/add-ct-pixel-clipping/`:
  - `proposal.md`
  - `design.md`
  - `tasks.md`
  - `specs/ct-pixel-clipping/spec.md`
  - `specs/ct2phits-frontend/spec.md`
  - `specs/guided-gui-workflow/spec.md`
  - `validation.md`
- Runtime code, accepted specifications, source data, and tests are unchanged.

## Planning checks

- OpenSpec CLI: unavailable; no installation performed. Manual structural
  review plus an inline Python check passed for all seven requirements:
  required proposal headings, delta headings, SHALL/MUST, Scenario headings,
  WHEN/THEN, UTF-8, whitespace, and absence of local absolute paths.
- Independent bounded review: no verified inconsistency in the three-plane
  box, source snapshot preservation, slice numbering, fixed coarse graining,
  coordinate evidence gates, or approval boundary.
- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: passed, 448 tracked files including
  the seven staged proposal files.
- `git diff --check` and `git diff --cached --check`: passed.
- `git diff --stat`, `git diff --cached --stat`, `git status --short`:
  inspected; only the seven proposal files were added to the index. The
  pre-existing untracked files remain untracked.

## Test environment observations

- `python -m pytest -q -p no:cacheprovider`: failed at collection with 32
  errors because the default interpreter lacks numpy/pydicom. No source change
  or dependency installation was made in response.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`: the existing
  project environment has Python 3.12.10 and dependencies, but the sandboxed
  run encountered repeated fixture setup errors and was interrupted.
- `.venv/Scripts/python.exe -m pytest -x -q -p no:cacheprovider --tb=short`:
  14 passed, 1 setup error; diagnosed PermissionError accessing pytest's
  temporary directory.
- A fresh temporary-directory retry with `--basetemp` also produced repeated
  setup errors and was interrupted. Neither interrupted run is a pass.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`, with sandbox
  escalation: **1505 passed, 15 skipped, 1 warning in 202.38 seconds**. The
  warning comes from the deliberate duplicate-ZIP-member test. Skipped tests
  are not represented as verified functionality.

## Unverified and stopping outcome

Implementation, GUI operation, cropped output geometry, and actual CT2PHITS
endpoint/coarse-graining behavior are not verified by this planning task.
No real DICOM or external scientific tool was opened or executed. No official
distribution files were copied. No commit, push, PR, merge, or tag change was
performed. The draft remains active pending approval and the evidence gates
in the design; it must not be promoted or archived as completed functionality.

## Implementation progress, 2026-10-09

The user's saved implementation prompt approved the proposal's scope. The
approved change now has a source-index box model, reversible display mappings,
bounded asynchronous synthetic CT preview, numeric and two-corner editing,
crosshairs, case invalidation, and CLI parsing. Both GUI and frontend reject a
non-default conversion before launching the external tool or creating a
workspace. Full-volume input and manifest generation remain unchanged.
No DICOM coordinate, crop-origin, coarse-graining, or physics correction was
made. The proposed clipped-input and cropped-manifest path remains incomplete.

Observed validation after the implementation diff:

- Focused `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
  tests/test_ct_pixel_clipping.py tests/test_run_ct2phits.py tests/test_gui.py`:
  **194 passed, 1 skipped**. The synthetic Tk interaction test itself passed.
- Final `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`:
  **1518 passed, 15 skipped, 1 warning in 154.37 seconds**. The warning is
  the existing duplicate-ZIP-member test.
- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: passed, 453 tracked files checked.
- `git diff --check`, `git diff --cached --check`, stats, and short status:
  passed and inspected; unrelated local configuration and JPEGs were not staged.
- OpenSpec CLI unavailable. Manual structural validation passed for the
  proposal headings and all seven delta requirements, with SHALL/MUST,
  scenarios, WHEN, and THEN.

An initial sandboxed pytest attempt failed during fixture setup because the
temporary directory was inaccessible. A workspace-local `--basetemp` attempt
also failed for permissions; its temporary folder was removed after its exact
path was checked. Escalated test runs passed. One new synthetic test initially
had an incorrect expected rescale number; it was corrected and the same
focused test group passed. These failures were not hidden as successful runs.

The supported CT2PHITS version's inclusive endpoint, `8 8 2` remainder and
alignment, and generated physical placement are not established by available
repository evidence. Real data, official distributions, and external
scientific tools were neither explored nor executed. Independent XY-only,
Z-only, and XYZ cropped mesh position expectations therefore remain
unverified. The acceptance criteria for non-default conversion are not met;
the change stays active, and its deltas must not be promoted or archived.
