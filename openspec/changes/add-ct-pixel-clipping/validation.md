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

At the time of this experiment, these observations did not authorize silently
changing the public coordinate handoff or narrowing selectable ranges. Later
human decisions for the default-factor clipping path are recorded below. Tests
with fake runners alone cannot establish external-tool properties.

## Approved default-factor clipped conversion, 2026-10-09

The user chose the existing `8 8 2` default for clipped conversion, accepted
that coarse graining changes fine HU and boundary representation, and directed
that incomplete high-end groups cause a warning followed by conversion rather
than rejection. A separate explicit `yes` approved using the selected first
frozen slice's DICOM origin for clipped placement while retaining the complete
source-series origin for audit. The user requested main-GUI colors on child
windows; the CT preview and new modal warning use that palette.

The frontend now writes requested bounds to the CT2PHITS input, and records
retained source bounds, discarded high-end counts, expected voxel counts, and
the selected placement slice. It warns before invoking the runner. A box with
no complete coarse group on any axis still fails before creating a workspace.
Raw CT2PHITS DICOM-origin fields must agree with the selected slice at the
tool's printed precision, and generated voxel counts must match complete
groups. The second CT asset preparation in the public 3D-CRT workspace builder
reuses the frozen placement slice and checks origin, raw hashes, and counts
against completed frontend evidence. Structure relative-error evaluation also
checks placement-origin agreement while retaining full-series source mapping.

Focused synthetic tests: **317 passed, 1 skipped** in the targeted run;
the additional downstream integration test passed separately. The final full
public suite after the raw-origin and full-volume compatibility checks:
**1533 passed, 15 skipped, 1 existing warning**.
`python -m compileall src`, `python tools/verify_public_tree.py`, and
`git diff --check` passed. The OpenSpec CLI was unavailable; manual
structural review found requirement headings and scenarios in all four delta
specifications. The CT child windows could not be visually checked on this
sandboxed Tk display; their colors and styles were inspected in code.
The first full run exposed six synthetic fixture constructor failures after
adding the placement-origin field; the optional default preserved legacy
construction, and the final full run passed. One earlier focused run hit the
existing sandbox pytest temporary-directory permission error and was rerun
with approved execution permissions. No further real CT2PHITS or PHITS
transport run was performed in this implementation turn.

Non-default coarse-graining triples remain unavailable at conversion time.
The installed tool lost Y material with unequal X/Y factors. The user-entered
fields and CLI input validation remain, but supported behavior for general
triples is not established. The active OpenSpec change therefore remains open.

## Authorized 8 8 1 and Computer Use follow-up, 2026-10-09

The user explicitly approved another installed CT2PHITS run with newly generated
non-patient synthetic CT and factors `8 8 1`, and requested GUI operation checks
and bug fixes with Computer Use. The synthetic source had 32 columns, 24 rows,
six slices, 2 mm in-plane spacing, 3 mm slice spacing, and a nonzero origin.
Only the CT2PHITS batch adapter was executed; no PHITS transport was run.

Observed full-volume output: 4 x 3 x 6; voxel sizes 1.6, 1.6, 0.3 cm. Three
constant Y bands remained three distinct materials. The combined crop
(columns 9-24, rows 5-20, slices 3-6) produced 2 x 2 x 4, local X/Y minima
1.5/0.7 cm, and DICOM Z shift 30.6 cm. A 17 x 17 x 5 crop starting at
column/row 4 and slice 2 produced 2 x 2 x 5, local minima 0.5/0.5 cm and
DICOM Z shift 30.3 cm. These agree with retained complete groups and the
selected-first-slice placement. The verified-factor set now includes exactly
`8 8 2` and `8 8 1`; the default remains `8 8 2`.

Windows Computer Use used isolated synthetic GUI processes, separate settings,
and the existing harness's external-process prohibition. It did not inspect or
operate other open applications or user data. Findings and checks:

- Reproduced Apply/Cancel/Reset clipped below the initial preview window under
  application styles. Reserved grid rows now retain actions, numeric fields,
  sliders and direction labels while the image row resizes.
- Reproduced a white native CT preview error dialog despite the requested child
  palette. Application information, warning, error and confirmation messages
  now use the main palette; Escape/close is negative and confirmation starts
  focused on No/Cancel. Windows title bars/file pickers remain OS-controlled.
- Selected Axial corners (5,9) and (28,16), observed synchronized overlays and
  all six fields, then Apply displayed Nx 5-28, Ny 9-16, slices 1-6 in the main
  page. Synthetic unwanted upper/lower bands were visibly outside the box.
- Exercised PHITS Run with an in-process runner, Stop after current segment,
  close-during-run warning, User stopped (1/2), incomplete preview, and retry.
  Final state was Completed (2/2), retained 1, newly completed 1. Calls were
  seg_001 followed by seg_002; no real PHITS process was started.
- Exercised Cancel preparation: final state Preparation cancelled; runner
  call list was empty.
- Opened an isolated existing synthetic case through the folder picker,
  observed PHITS verified/locked, Sumtally completed and RTDOSE recovery ready,
  confirmed RTDOSE Run only and observed final Completed. Runner calls were
  exactly run_rtdose; PHITS/Sumtally were not repeated.
- Viewed CT2PHITS, Workspace, PHITS, Sumtally and RTDOSE pages. This is not a
  claim that every button, every input combination, or a real end-to-end
  scientific calculation was exercised through Computer Use.

Focused GUI/frontend checks: 210 passed, 1 skipped. Full public suite:
1534 passed, 15 skipped, one existing duplicate-ZIP-member warning (230.66 s).
Compileall, public-tree audit and Git whitespace checks passed. OpenSpec CLI
remains unavailable; deltas are structurally reviewed manually.

An intermediate text replacement removed adjacent GUI construction statements;
diff inspection caught it immediately and restored those statements before
launching the edited GUI and before the passing validation. The first footer
fix exposed a second instance of the same packing issue at the per-plane
sliders; reserving their rows resolved it. Computer Use sometimes returned an
occluded window image or stale element indexes; fresh activation/screenshot
selection resolved this without operating another application.

General numeric factor conversion remains incomplete due to the installed
tool's observed unequal-X/Y material loss and lack of general-triple evidence.
The active change therefore remains unarchived. Real patient data, real PHITS,
Sumtally/phits2dicom, clinical accuracy, arbitrary factors and every GUI input
combination remain unverified.

Final preview recheck showed all three sliders, direction labels, numeric fields,
and Apply/Cancel/Reset visible at the initial size; Coronal expansion and
one-index stepping preserved the box. After setting the supported minimum
width to 1120, focused preview tests passed again (10 passed, 1.43 s), and
`python -m compileall src` passed. The full suite above preceded only this
minimum-width adjustment and documentation updates.

## CT versus accelerator geometry audit against v1.1.1, 2026-10-09

Requested by the user because clipping might disturb phantom/linac geometry.
Baseline: Git tag v1.1.1; reviewed implementation: 2d2604f. This audit adds
synthetic regression tests only; runtime code and current public specs are
unchanged. No real DICOM or external scientific program was executed.

The accelerator_geometry, rectangular_geometry, gantry_geometry and
prepare_ct_calibration modules have identical Git blobs at v1.1.1 and HEAD.
The CT-to-IEC rotation and origin-minus-isocentre formula are unchanged.
Only a cropped series's selected-first-slice placement reference changes.
The complete-series origin remains audit evidence. CTsurf, CTuniverse and
CTvoxel assets are copied from CT2PHITS rather than recentered by the GUI.
The dose tally grid is independent of the CT crop and is not resized by it.

A temporary comparison loaded the v1.1.1 CT-preparation and workspace-generation
modules directly from Git without modifying a checkout. With the same generated
non-patient axial HFS CT, RT Plan and synthetic raw assets:

- Full-volume preparation produced identical hashes for all six prepared CT
  files in v1.1.1 and current code.
- Full-volume PHITS input bytes matched across eight angle combinations:
  gantry 0/90/180/270 degrees, collimator 0/37 degrees, couch zero.
- Applying the old full-origin preparation to a Z crop starting at slice 3
  differed from current placement by +0.6 cm in IEC Y, matching two skipped
  3 mm slices. This illustrates why the selected-first-slice correction is
  required for the new cropped path; v1.1.1 did not offer that cropped path.

New tests in tests/test_clipped_ct_linac_geometry.py independently calculate
retained coarse-block centres from source DICOM indices and the RT Plan
isocentre, then compare with the generated CT parameter file and transform.
All retained centres match to floating-point arithmetic precision for full,
XY-only, Z-only and combined/remainder cases with 8 8 2 and 8 8 1. The 1e-12
assertion threshold is a numerical comparison tolerance for these exact
synthetic values, not a new physical tolerance in the product.

Eight additional comparisons generate full/cropped PHITS inputs using the
public default accelerator and the same angles above. After removing only
the CT lattice counts line, input text is identical: source, accelerator
surfaces/cells, rotations, materials, dose factor and tally are unchanged.
The CT wrapper excludes accelerator cell 2 (#2), and the main-air cell excludes
both CT and accelerator (#1201 #2), preserving the v1.1.1 topology protection.

Interpretation: no displacement of retained material or change of the linac
geometry was found in the inspected application code and synthetic comparison.
Cropping changes the phantom's outer extent. Coarse graining changes HU and
boundary representation; unaligned crop starts also change coarse-block
membership and centres compared with the old full-volume coarse lattice.
These are not a rigid displacement or stretch of the retained source region,
but they can affect transport/scatter and dose. Identical geometry code does
not establish identical dose after removing material.

Limits: the new raw fixtures deliberately use placeholder surface/material/
universe/voxel bodies and model the previously observed CT2PHITS parameter
contract. They validate application placement and emitted accelerator input,
not external surface semantics, lost particles or real PHITS transport. The
frontend checks raw origin and voxel counts but does not independently verify
every surface, voxel pitch/minimum or material assignment. Prior approved
CT2PHITS experiments provide bounded external evidence for 8 8 2 and 8 8 1,
not a full current-branch CT-to-PHITS transport validation. Nonzero couch and
non-axial/non-HFS CT remain outside the supported contract.

Focused command: .venv/Scripts/python.exe -m pytest -q --tb=short
-p no:cacheprovider tests/test_clipped_ct_linac_geometry.py
tests/test_ct2phits_datfiles.py tests/test_prepare_3dcrt_workspace.py
tests/test_accelerator_geometry.py tests/test_rectangular_geometry.py
tests/test_phits_geometry_diagnostics.py: 171 passed (8.16 s).
The first attempt failed 16 new cases because the synthetic fixture rendered
voxel counts with decimal points; rendering the integer counts in the documented
format corrected the fixture, and the same focused set then passed. No runtime
validation was weakened. General-factor acceptance is still incomplete and
this OpenSpec change remains active.

Final public checks for this audit:

- `python -m compileall src`: passed.
- `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`: 1550 passed,
  15 skipped, one existing duplicate-ZIP-member warning (151.38 s).
- `.venv/Scripts/python.exe tools/verify_public_tree.py`: passed, 456 tracked
  files checked after staging the new test.
- `git diff --check` and `git diff --cached --check`: passed.
- Diff/stat/status review: only this validation record and the new regression
  test are included; unrelated untracked configuration/screenshots preserved.

## Arbitrary-factor request and installed-tool source audit, 2026-10-09

The user rejected completion with only `8 8 2` and `8 8 1`: any positive
integer factor triple that produces at least one complete voxel on each axis
must be usable. This supersedes accepting the current
gate as the finished feature. The gate remains in place until conversion can
be shown to preserve all retained source blocks and their geometry.

Read-only inspection of the user-identified RT-PHITS installation found a
specific defect in `src/ct2phits.f`'s `SETcoarse`: after calculating the Y
output count using `nyc`, the routine truncates its Y input count using
`nxc`. `READCONV` then uses that truncated input count as its Y loop limit,
while dividing the Y index and HU sum by `nyc`. This directly explains the
previous observed missing third Y material band for `4 8 1`; using X greater
than Y could instead cause the loop to index beyond the Y output array.
The tool can report success despite an incorrect phantom. The installed
source's Windows build recipe requires 32-bit `gfortran`; no `gfortran` or
`gcc` executable is currently available on PATH. Neither source nor binary
was changed, compiled, or run during this audit.

Removing the frontend's factor gate would accept a known wrong output.
The smallest fidelity-preserving route is correction of this installed
external tool and a bounded synthetic comparison covering unequal X/Y,
several Z factors, material identities, voxel counts, pitch, and placement.
This requires a separate explicit decision for modification/execution outside
the repository. Replacing the conversion inside dicomxphits would require a
new, independently reviewed material-mapping and geometry contract rather
than assuming equivalent results from the existing synthetic mocks. The PR
must remain draft and the OpenSpec change active until arbitrary factors are
demonstrated and the approved acceptance criteria are met.

This documentation-only audit passed `python -m compileall src`,
`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (1550 passed,
15 skipped, one existing duplicate-ZIP warning),
`python tools/verify_public_tree.py` (456 tracked files), and `git diff --check`.
No runtime code or current public specification was changed.
