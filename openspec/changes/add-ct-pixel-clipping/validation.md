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

## Human-directed manual-selection refinement, 2026-10-09

The user clarified that a human must visually identify the source region to
retain and manually exclude a couch or any other unwanted material. The user
approved arbitrary-size, image-axis-aligned rectangular selection shared by
all three planes. This is a manual spatial selection, not an automatic couch
or anatomy classifier, and it does not remove voxels inside the selected box.

The preview now separates browse clicks from explicit two-corner selection,
returns to browse after a completed pair, allows one-index plane stepping by
buttons or mouse wheel, and can enlarge one plane before returning to all
three. The six source-index bounds, overlays, and conversion gate remain
unchanged. The proposal, design, delta, and bilingual manual now state this
human-directed behavior explicitly.

- Focused `.venv/Scripts/python.exe -m pytest -q -x -p no:cacheprovider
  tests/test_ct_pixel_clipping.py tests/test_gui.py`: **144 passed,
  1 skipped**; the synthetic Tk browse, enlargement, selection, step, and
  Apply interaction passed.
- Full `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`:
  **1518 passed, 15 skipped, 1 existing warning in 150.73 seconds**.
- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: passed, 453 tracked files checked.
- OpenSpec CLI remains unavailable; manual structural check passed for the
  proposal and all seven active delta requirements.

The supported-version clipping and physical-placement evidence remains
unresolved. Non-default conversion is still blocked, and the active change
is not eligible for promotion or archive.

## RT-PHITS lecture evidence, 2026-10-09

At the user's direction, the five supplied RT-PHITS lecture decks were read
without running the distribution or copying its files into the repository.
The GUI decks (`phits-lec-RTphits-GUI-jp.pptx` slide 12,
`phits-lec-RTphits-GUI-en.pptx` slide 12, and
`HowToUseRTphitsGUI.pptx` slide 21) explicitly describe minimum/maximum CT
pixel and slice clipping, show the selected area as a rectangle, and distinguish
the voxel-center and DICOM-coordinate origin options. The CUI decks
(`phits-lec-RTphits-CUI-jp.pptx` and
`phits-lec-RTphits-CUI-en.pptx`, slide 6) document the CT2PHITS input order:
minimum/maximum slice, then Nx minimum/maximum and Ny minimum/maximum,
then X/Y/Z coarse-graining factors and coordinate mode. Both slide 12 examples
use slices `2 46`, pixels `93 432 134 386`, coarse graining `8 8 1`, and
coordinate mode `1`. They instruct the user to rerun CT2PHITS and
InputCreater4PHITS after changing the region.

These decks establish that manual spatial clipping is an intended RT-PHITS
operation and support the proposed input-field mapping. They do not describe
how the supported tool handles small, non-divisible, or unaligned selections
with this project's then-fixed `8 8 2` factors, nor where crop offsets are encoded
in generated geometry. Slide 12 says mode `1` extracts position from the DICOM
header; it does not establish whether this project's later replacement of
`c91/c92/c93` with the original series origin preserves cropped geometry.
No clipped output was produced or checked. The conversion gate remains in
place pending those contract and placement checks.

## Numeric coarse-graining extension, 2026-10-09

The user requested numeric X/Y/Z coarse-graining controls after seeing the
lecture example. The active proposal and deltas now include case-local positive
integer fields with default `8 8 2`. The GUI passes non-default factors through
the existing CLI path; the frontend validates them before workspace creation,
and the input renderer and manifest have an effective-factor parameter.
Because the cited lecture examples use `8 8 1` and do not establish the
supported tool's remainder or placement behavior for arbitrary triples, both
GUI and frontend still reject non-default external conversion. No external
tool was run. This extension is not complete until the documented supported
tool geometry contract and required checks permit the requested conversion.

Validation after this extension:

- Focused synthetic GUI/frontend tests: **194 passed, 1 skipped**.
- Full synthetic suite: **1525 passed, 15 skipped, 1 existing warning**.
- `python -m compileall src`, `python tools/verify_public_tree.py`, and
  `git diff --check`: passed.
- OpenSpec CLI remains unavailable; manual proposal/delta structure check
  passed for all three delta files.
- The first full-suite attempt under sandbox permissions hit the existing
  pytest temporary-directory access error. A later full-suite run was
  interrupted after a small input-validation correction; the final run above
  completed successfully under approved execution permissions.

## Authorized synthetic CT2PHITS contract check, 2026-10-09

The user explicitly approved running the installed CT2PHITS tool with only
newly generated non-patient synthetic CT. The experiment used 32 columns,
24 rows, six slices, 2 mm in-plane spacing, 3 mm slice spacing, and a nonzero
synthetic DICOM origin. It invoked the provided CT2PHITS batch adapter only;
PHITS transport was not run. Inputs and generated files stayed outside the
repository and were removed after extracting the following bounded findings.
No distribution file or generated output was added to Git.

- The full volume with `8 8 2` produced 4 x 3 x 3 voxels. An XY-only crop
  (columns 9-24, rows 5-20) produced 2 x 2 x 3, with X/Y local bounds
  shifted by the skipped source columns/rows.
- A Z-only crop (slices 3-6) produced 4 x 3 x 2. Its raw DICOM Z shift was
  0.6 cm larger than the full-volume shift, matching the two skipped 3 mm
  slices. The existing `prepare_ct2phits_assets()` replaced that shift using
  the full frozen series origin, losing the 0.6 cm crop offset in the prepared
  IEC Y translation. This is a demonstrated coordinate-handoff defect for
  non-default Z selection, not an assumed correction.
- An off-centre 17 x 17 x 5 selection with `8 8 2` produced 2 x 2 x 2:
  incomplete high-end groups were discarded. The same selection with
  `4 4 1` produced 4 x 4 x 5. Arbitrary numeric bounds therefore do not
  guarantee that every selected source voxel is retained when dimensions are
  not divisible by their factors.
- With equal X/Y factors, three synthetic Y bands mapped to three distinct
  voxel materials. With factors `4 8 1`, the third band was absent from the
  output even though the tool reported success. The installed source's
  `SETcoarse` uses the X factor while truncating the Y source count; this
  agrees with the observed loss. Unequal X/Y factors are unsafe in this
  installed version.

These observations do not authorize silently changing the public coordinate
handoff or narrowing selectable ranges. The active conversion gate remains
until the human decides on the selected-slice coordinate handoff and on how to
handle non-divisible and unequal-factor selections. Tests with fake runners
alone cannot establish these external-tool properties.
