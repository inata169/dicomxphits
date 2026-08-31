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

Development is paused on branch `add-phantom-ct-water-replacement`. The branch
is based on main commit `8b6f0e1` and has these implementation commits:

- `8d461b7 Add phantom CT water replacement tool`
- `6a7b6ec Record phantom CT preflight blocker`
- `d38e700 Validate whole-layer phantom ROI geometry`

The branch has no configured upstream and no pull request has been opened.
It must remain a feature branch until the active OpenSpec change is complete.
Do not merge it, delete it, or archive the OpenSpec change in its present
state.

The active change is
`openspec/changes/add-phantom-ct-water-replacement/`. Thirteen of its fifteen
tasks are complete. Task 5.3 remains incomplete because the supplied real-data
target ROIs failed the whole-layer geometry gate. Task 5.4 remains incomplete
because promotion and archive are only allowed after successful bounded
real-data validation and completion of the approved acceptance criteria.

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

## Real-data preflight completed outside the repository

The supplied anonymized non-patient Lung and Bone datasets were inspected only
through bounded, local, read-only preflight runs. Earlier exports were rejected
first for missing approved ROI names and then for independently anonymized,
mismatched CT/RTSTRUCT references. A later batch export of CT, RTSTRUCT,
RTPLAN, and RTDOSE provided coherent frame, series, and SOP references for both
phantoms.

The `Water_reference` ROI passed its water-statistics gates in both cases:

| Phantom | Median | Mean | Standard deviation | Reference voxels | Fallback slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lung | 0 HU | about -0.82 HU | about 12.13 HU | about 1,402,158 | 2 |
| Bone | 3 HU | about 2.13 HU | about 14.81 HU | about 1,415,397 | 2 |

The target ROI did not represent a whole 2 cm layer:

| Phantom | Principal physical extents | Approximate target volume |
| --- | --- | ---: |
| Lung | 19.53 x 19.94 x 160.07 mm | 60.27 cm3 |
| Bone | 18.55 x 18.55 x 160.00 mm | 55.08 cm3 |

Each target is therefore approximately a 2 cm by 2 cm rod extending through
about 16 cm, with two thickness-like dimensions. The dimensionality gate
correctly stopped both preflights. `--accept-qc-warnings` must not be used to
bypass this failure. No derived CT directory, derived DICOM instance, or
real-data QC report was created.

## Required human preparation before resuming

Only `Water_CC13_2cm` needs to be redrawn in Monaco. Leave the validated
`Water_reference` ROI unchanged.

The replacement target must be a whole phantom layer:

- keep its thickness in the physical stacking direction at approximately
  2 cm;
- expand both in-plane directions to the external phantom boundary while
  excluding external air;
- include the chamber, cavity, wall, electrode, cable, and associated artifact
  inside that layer; and
- contour every CT slice spanned by the physical layer.

Export CT, RTSTRUCT, RTPLAN, and RTDOSE together in one anonymization/export
operation to a new empty external directory for each phantom. Do not
independently anonymize or copy the objects afterward, because that can break
the DICOM reference graph.

## Exact restart sequence

1. Read `AI_AGENT_RULES.md`, `AGENTS.md`, and `openspec/AGENTS.md`, then confirm
   the repository root, branch, status, history, remote, and tags.
2. Confirm the active OpenSpec change still has tasks 5.3 and 5.4 unchecked.
3. Obtain the operator's new batch-export paths and explicit approval for a
   bounded read-only preflight on the two non-patient datasets.
4. Run preflight only. Verify reference consistency, target topology, target
   dimensionality, mask coverage, water statistics, slice fallback, and every
   warning. Do not use `--accept-qc-warnings` to make an invalid target pass.
5. Report the preflight evidence. If both cases pass, obtain a separate human
   approval before writing derived CT objects into new, empty output
   directories.
6. After derivation, inspect the generated QC JSON, text, and PNG evidence and
   perform the planned human Monaco reassociation/visual check. Existing source
   CT and RTSTRUCT objects must remain unchanged.
7. CT2PHITS, PHITS, Sumtally, RTDOSE creation, absolute-dose assessment, and
   GPR comparison are later workflow stages. They require their own explicit
   scope and must not be inferred from approval to derive the CT.
8. Once the approved acceptance criteria and required checks are complete,
   mark task 5.3 complete, promote the accepted delta into `openspec/specs/`,
   archive the change under the date-prefixed archive name, complete task 5.4,
   and strictly validate the resulting OpenSpec tree before review and pull
   request work.

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

Use a temporary directory outside the repository for full pytest runs. Some
GUI safety tests intentionally detect untracked in-repository temporary files,
so an in-tree pytest base directory can create an environment-induced failure.

## Unverified and deliberately not done

- No derived real-data CT has been created.
- No real-data QC artifact has been accepted.
- No derived CT has been imported or reassociated in Monaco.
- No CT2PHITS, PHITS, Sumtally, RTDOSE, absolute-dose, or GPR validation has
  been run for this change.
- The active OpenSpec delta has not been promoted or archived.
- The branch has not been pushed, reviewed in a pull request, merged, or
  deleted.
- Existing CT2PHITS selection, accelerator geometry, beam physics, dose, MU,
  normalization, and the public fixed-field 3D-CRT scope were not changed by
  this helper.

The correct stopping state is an active, tested implementation with a
real-data ROI-definition blocker. Resume from target-ROI correction and
read-only preflight; do not restart implementation and do not treat the
synthetic test result as real-data acceptance.
