# Development handoff - 2026-08-31 phantom CT water replacement

This handoff records the current state of the non-patient phantom CT water-
replacement work at the end of the 2026-08-31 development session.
`dicomxphits` remains education and research software for the documented
fixed-field 3D-CRT workflow. This work does not establish clinical validity,
commissioning, patient QA, vendor certification, or general dose accuracy.

No real DICOM file, absolute data path, DICOM UID, patient attribute, facility
identifier, generated CT, or real-data QC artifact is committed to the
repository.

## Repository state

Development was completed on branch `add-phantom-ct-water-replacement`. The
branch is based on main commit `8b6f0e1` and includes these implementation and
handoff commits before final closeout:

- `8d461b7 Add phantom CT water replacement tool`
- `6a7b6ec Record phantom CT preflight blocker`
- `d38e700 Validate whole-layer phantom ROI geometry`
- `c806071 Document phantom CT water replacement handoff`
- `e581dad Record PHITS diagnostic parser incident`
- `9125089 Record PHITS parser fix outcome`

The branch initially had no configured upstream or pull request. Its accepted
OpenSpec delta is now promoted to
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
the failed summary. Either rerunning PHITS or attempting provenance-preserving
output recovery requires separate human approval and a reviewed procedure.

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
938 passed, 10 skipped

.venv\Scripts\python.exe -m compileall src
passed

.venv\Scripts\python.exe tools\verify_public_tree.py
passed

openspec.cmd validate --all --strict --no-interactive
13 passed, 0 failed

git diff --check
passed
```

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
- No CT2PHITS, PHITS, Sumtally, RTDOSE, absolute-dose, or GPR validation has
  been run for this change.
- No clinical commissioning, patient-QA, vendor-certification, or general dose-
  accuracy conclusion was made from the bounded phantom validation.
- The branch has not been pushed, reviewed in a pull request, merged, or
  deleted.
- The independent PHITS 3.35 geometry-diagnostic parser regression was fixed
  and merged through pull request #57; its retained staged tally has not been
  promoted or used downstream, and its disposition remains undecided.
- Existing CT2PHITS selection, accelerator geometry, beam physics, dose, MU,
  normalization, and the public fixed-field 3D-CRT scope were not changed by
  this helper.

The correct stopping state is a completed and archived phantom CT derivation
change with synthetic tests, bounded external Lung/Bone validation, and human
Monaco verification complete. Downstream transport and dose stages remain
unrun and require separately approved scope. The independent parser correction
is merged into `main`, while disposition of its retained staging outputs
remains unresolved and requires a separate human decision.
