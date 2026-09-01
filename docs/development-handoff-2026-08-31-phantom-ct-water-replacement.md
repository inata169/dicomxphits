# Development handoff - 2026-08-31 phantom CT water replacement

This handoff records the current state of the non-patient phantom CT water-
replacement work at the end of the 2026-08-31 development session, updated
through the 2026-09-01 closeout and operational follow-up.
`dicomxphits` remains education and research software for the documented
fixed-field 3D-CRT workflow. This work does not establish clinical validity,
commissioning, patient QA, vendor certification, or general dose accuracy.

No real DICOM file, absolute data path, DICOM UID, patient attribute, facility
identifier, generated CT, or real-data QC artifact is committed to the
repository.

## Repository state

Development was completed and reviewed in pull request #58. It was normally
merged into `main` as merge commit `725aa18` on 2026-09-01, without a force
push or tag change, and the merged feature branch was deleted. The final Codex
review of commit `23f41cb` reported no major issue, and all four required
Ubuntu and Windows CI jobs passed before merge.

The accepted OpenSpec delta is promoted to
`openspec/specs/phantom-ct-derivation/spec.md`, and all fifteen tasks are
complete in the archived change at
`openspec/changes/archive/2026-09-01-add-phantom-ct-water-replacement/`.

## Implemented capability

The branch adds a separate, fail-closed helper for making a calculation-only
derived CT from a non-patient phantom CT. It replaces samples inside one
explicitly named target ROI with water-like CT values estimated from a clean
reference-water ROI.

The implementation is in
`src/dicomxphits/replace_ct_layer_with_water.py`, with the console entry point
`dicomxphits-replace-ct-layer-with-water` and the thin script
`tools/replace_ct_layer_with_water.py`.

The current implementation:

- requires an explicit non-patient confirmation, CT directory, RTSTRUCT,
  target ROI, reference ROI, and new output directory;
- expects the approved ROI semantics represented by `Water_CC13_2cm` and
  `Water_reference`;
- accepts one conventional, native, uncompressed, single-frame CT series and
  validates CT/RTSTRUCT frame, series, and SOP-instance references;
- rasterizes closed planar contours in patient coordinates for axial and
  parallel-oblique CT geometry;
- computes per-slice clean-water medians with a documented global fallback;
- handles per-slice rescale slope/intercept, 8-bit and 16-bit pixels, signed
  and unsigned representation, and stored-bit placement;
- leaves allocated sample bytes outside the target mask unchanged and
  rechecks source hashes before completion;
- writes a new Series Instance UID and new per-slice SOP Instance UIDs,
  synchronizes file meta, and records derived-image metadata;
- rereads and verifies the output before declaring success;
- writes identity-safe JSON and text QC reports plus a representative PNG;
- never rewrites the supplied RTSTRUCT or RTPLAN; and
- stops on QC warnings unless the operator explicitly accepts them.

The final geometry correction in `d38e700` calculates physical target extents
from patient-coordinate voxel support using principal-component axes. The QC
gate requires exactly one principal extent in the approved 15-25 mm layer-
thickness range. This distinguishes a whole thin phantom layer from a narrow
rod that happens to be about 2 cm wide.

User-facing operation and safety boundaries are documented in
`docs/phantom-ct-water-replacement.md` and `docs/cli-reference.md`.

## Real-data validation completed outside the repository

The supplied anonymized non-patient Lung and Bone datasets were inspected only
through bounded, local, read-only preflight runs. Earlier exports were rejected
first for missing approved ROI names and then for independently anonymized,
mismatched CT/RTSTRUCT references. A later batch export of CT, RTSTRUCT,
RTPLAN, and RTDOSE provided coherent frame, series, and SOP references for both
phantoms.

The first whole-layer preflight attempt correctly rejected both target ROIs as
approximately two-centimetre-square rods rather than whole thin layers. The
operator subsequently redrew each `Water_CC13_2cm` ROI as a complete phantom
layer and exported coherent new batches. The final `Water_reference` ROI passed
its water-statistics gates in both cases:

| Phantom | Median | Mean | Standard deviation | Reference voxels | Fallback slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lung | 0 HU | about -0.82 HU | about 12.13 HU | about 1,402,158 | 0 |
| Bone | 3 HU | about 2.13 HU | about 14.81 HU | about 1,415,397 | 1 |

The redrawn target ROIs passed the whole-layer dimensionality gate:

| Phantom | Principal physical extents | Approximate target volume |
| --- | --- | ---: |
| Lung | 18.96 x 157.60 x 159.24 mm | 459.96 cm3 |
| Bone | 18.59 x 181.15 x 181.51 mm | 468.65 cm3 |

Each final target has exactly one principal extent in the documented 15-25 mm
range, does not touch the image boundary, and does not intersect boundary-
connected air-like pixels. Both read-only preflights completed without QC
warnings or warning acknowledgement.

After separate human approvals, the helper created the Lung and Bone derived
series only in new external directories. Both completed without warnings and
passed source-CT and RTSTRUCT hash rechecks, outside-target allocated-byte
preservation, post-write reread, incomplete-marker, JSON/text report, and PNG
checks. The operator then confirmed Monaco reassociation, CT geometry and slice
order, phantom and structure alignment, target coverage, water replacement,
target-exterior preservation, and plan position for both non-patient phantoms
on 2026-09-01. Real paths, UIDs, DICOM, and QC artifacts remain outside the
repository.

## Late-session PHITS diagnostic-parser incident

The independent parser correction was completed in pull request #57 and
normally merged into `main` as merge commit `87c61d9` on 2026-09-01. The
bug-fix branch was deleted after merge. The correction remained separate from
this branch and did not change PHITS physics, the CT wrapper, accelerator
geometry, dose, MU, or absolute-dose calibration.

The reported SumTally failure was a cascading gate failure, not a separate
calculation error: the parser rejection prevented the required PHITS output
from reaching its manifest-declared public location, so the SumTally gate could
not find it. The disposition of retained external staging outputs remains
undecided. Do not copy, move, delete, or promote them manually, and do not edit
the failed summary.

The operator later gave separate approval for a new external research run in a
new workspace. That operation did not recover, promote, or otherwise alter the
retained staging output from the original failed workspace. Local DICOM,
PHITS, Sumtally, phits2dicom, and comparison artifacts remain outside the
repository and are intentionally not recorded here. The original staging
disposition therefore remains unresolved; any future recovery, deletion, or
other handling still requires a separate human decision and reviewed
procedure.

## 2026-09-01 GUI operational handoff

The external follow-up exposed several usability limitations without changing
repository code or public behavior:

- opening a workspace that lacks one required public PHITS output correctly
  fails reuse inspection, but existing-case mode then disables the expensive
  stages needed to rerun PHITS;
- standard tool-profile mode derives a deterministic CT2PHITS output path and
  keeps that field read-only, so it does not directly offer a retry suffix;
- `Allow overwrite of downstream stage summaries` relaxes the GUI's summary-
  existence gate, but Workspace Prepare still correctly refuses to overwrite
  an existing generated `phits.inp`; and
- reusing a validated CT2PHITS handoff for a newly prepared 3D-CRT workspace
  requires the advanced handoff controls, which is not obvious from the
  failed-workspace path.

The fail-closed guards prevented an existing PHITS input from being
overwritten. The supported operational route was to preserve the failed
workspace, select a new external 3D-CRT workspace, reuse the already validated
CT2PHITS handoff, and apply the documented runtime controls during Workspace
Prepare. These observations are possible future UX work only. No Issue,
OpenSpec change, implementation branch, or follow-up pull request was created.

## Completed human verification and OpenSpec closeout

The operator completed the planned Monaco reassociation and visual checks for
both derived series and reported them acceptable on 2026-09-01. This completes
the bounded real-data acceptance criterion for the helper; it does not
authorize CT2PHITS, PHITS, Sumtally, RTDOSE creation, absolute-dose assessment,
or GPR comparison.

Task 5.3 was completed with identity-safe evidence only. The accepted delta was
promoted to `openspec/specs/phantom-ct-derivation/spec.md`, and the completed
change was archived under
`openspec/changes/archive/2026-09-01-add-phantom-ct-water-replacement/`.

## Validation evidence

The implementation revision at `d38e700` passed:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_replace_ct_layer_with_water.py
19 passed

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>
938 passed, 10 skipped in 157.06s

.venv\Scripts\python.exe -m compileall -q src
passed

.venv\Scripts\ruff.exe check src\dicomxphits\replace_ct_layer_with_water.py tests\test_replace_ct_layer_with_water.py tools\replace_ct_layer_with_water.py
passed

.venv\Scripts\python.exe tools\verify_public_tree.py
passed

openspec.cmd validate add-phantom-ct-water-replacement --strict
passed

git diff --check
passed
```

Final closeout validation on 2026-09-01 passed:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp <outside-repository-ASCII-temp> tests\test_replace_ct_layer_with_water.py
19 passed

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp <outside-repository-ASCII-temp>
973 passed, 10 skipped in 101.33s

.venv\Scripts\python.exe -m compileall src
passed

.venv\Scripts\python.exe tools\verify_public_tree.py
passed

openspec.cmd validate --all --strict --no-interactive
13 passed, 0 failed

git diff --check
passed
```

The 2026-09-01 end-of-day handoff refresh passed:

```text
.venv\Scripts\python.exe -m compileall src
passed

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>
973 passed, 10 skipped in 99.20s

.venv\Scripts\python.exe tools\verify_public_tree.py
passed (275 tracked files checked)

openspec.cmd validate --all --strict --no-interactive
13 passed, 0 failed

git diff --check
passed
```

The first full-test attempt could not create its repository-external temporary
directory under the sandbox permission profile and stopped with setup-time
permission errors. The same command passed after the required external-temp
write was explicitly approved; no test failure from repository code was
observed.

The OpenSpec CLI does not directly validate an archived change by archive name.
The archived delta therefore received a manual structural review confirming one
delta header, seven requirements, twelve scenarios, and no unchecked tasks.
Ruff was not rerun during closeout because the current virtual environment does
not contain a Ruff executable; the implementation revision's earlier passing
Ruff evidence remains recorded above.

Use a temporary directory outside the repository for full pytest runs. Some
GUI safety tests intentionally detect untracked in-repository temporary files,
so an in-tree pytest base directory can create an environment-induced failure.

## Unverified and deliberately not done

- The derived non-patient CT series and their accepted QC evidence remain
  outside the repository; no real path, UID, DICOM, or QC artifact is tracked.
- No local external-tool output, DICOM RT Dose, dose comparison, or GPR
  evidence is committed or treated as repository acceptance evidence. A
  separately approved external research workflow remains outside this
  handoff's tracked artifacts and claims.
- No clinical commissioning, patient-QA, vendor-certification, or general dose-
  accuracy conclusion was made from the bounded phantom validation.
- Pull request #58 is reviewed, merged, and its feature branch is deleted.
- The independent PHITS 3.35 geometry-diagnostic parser regression was fixed
  and merged through pull request #57; its retained staged tally has not been
  promoted or used downstream, and its disposition remains undecided.
- The GUI usability limitations observed during failed-workspace retry were
  not changed or filed as follow-up work.
- Existing CT2PHITS selection, accelerator geometry, beam physics, dose, MU,
  normalization, and the public fixed-field 3D-CRT scope were not changed by
  this helper.

The correct stopping state is `main` at merge commit `725aa18`, with the
phantom CT derivation change completed, reviewed, merged, and archived; the
independent parser correction from pull request #57 also merged; all protected
external artifacts remaining outside the repository; the original retained
staging disposition unresolved; and the observed GUI retry usability work
explicitly deferred unless a human requests a separate scoped change.
