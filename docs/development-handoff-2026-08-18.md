# Development handoff - 2026-08-18 collimator direction closeout

This handoff follows the
[2026-08-17 MLCX correction closeout](development-handoff-2026-08-17.md) and
records the completion of the bounded human-operated comparison sequence and
the reviewed repository correction it prompted. `dicomxphits` remains
education and research software for the documented fixed-field 3D-CRT
workflow. This record does not establish clinical validity, commissioning,
patient QA, vendor certification, or general dose accuracy.

## Repository and GitHub baseline

At this closeout, local `main` was clean and matched `origin/main` at merge
commit `6816b6329fef94c72a24f6f3b338ffd451689292`.

- Pull request [#47](https://github.com/inata169/dicomxphits/pull/47),
  **Fix IEC collimator rotation direction**, is merged and closed.
- Its final reviewed exact HEAD was
  `77e35455f3be015a63930fff39c6831adb5a18d2`, and its merge commit was
  `6816b6329fef94c72a24f6f3b338ffd451689292`.
- `@codex` reviewed that exact HEAD and reported no major issues. No review
  thread remained unresolved, and public CI run #409 succeeded.
- The pull request was merged with a normal merge commit; rebase and
  force-push were not used. Its local and remote feature branches were
  deleted after merge.
- Tags `v1.0.2`, `v1.0.1`, and `v1.0.0` were not changed.
- The published `v1.0.2` tag and offline ZIP remain based on
  `efb0dace568fbcb12019f3d320a468dcfb446e34`. Neither the pull request #44
  MLCX correction nor the later pull request #47 collimator-direction
  correction is part of that tag or published ZIP.

## Human-operated comparison sequence

The human operator reported that the fresh external per-field PHITS
calculations described in the 2026-08-17 handoff completed, per-field RTDOSE
files were generated, and all four TPS-reference and PHITS-evaluation fields
were visually accepted for MLC aperture orientation and shape. Distribution
shape was assessed before gamma interpretation because the calculation
statistics were intentionally limited for this bounded check.

After the MLCX shape check, the human operator created the planned non-patient,
fixed-gantry, asymmetric-aperture test. The first comparison exposed an
opposite collimator rotation between the TPS reference and PHITS evaluation.
After the repository correction in pull request #47, the human reran the
workflow and reported that the collimator rotation and aperture shape agreed.

These are human-reported research observations, not imported repository
evidence. The agent did not execute or open PHITS, Sumtally, phits2dicom, GPR,
real DICOM, external workspaces, or calculation-result files. No personal
absolute path, dataset identifier, DICOM, image, comparison metric, dose value,
or generated output is recorded in Git.

## README workflow animation

The README now embeds the sanitized guided-workflow animation at
`docs/assets/dicomxphits-gui-workflow.gif`. It presents the CT2PHITS,
Workspace, PHITS, Sumtally, and RTDOSE stages while masking local paths,
identifiers, tool locations, generated-output locations, runtime values, and
Activity log content. The external source screenshots and any unredacted
animation remain outside the repository.

All animation frames were reviewed in a sanitized-only contact sheet, with the
normal stage frames also inspected at original resolution. The animation
metadata and SHA-256 are recorded in the
[GUI animation anonymization handoff](development-handoff-2026-08-18-gui-animation.md).
This documentation asset does not add a runtime, physics, DICOM, dose, MU,
normalization, geometry, or treatment-scope change.

## Corrected collimator direction

Pull request #47 corrected the sign of the collimator rotation applied by the
PHITS accelerator `tr2` transform. The DICOM Beam Limiting Device Angle remains
recorded unchanged, while the transform now applies its positive direction in
the intended patient-axis convention. Independent synthetic patient-axis
tests cover positive, negative, cardinal, asymmetric-feature, and zero-angle
cases.

Prepared-workspace geometry provenance advanced from
`dicomxphits_iec_gantry_mlcx_geometry_v3` to
`dicomxphits_iec_gantry_mlcx_collimator_geometry_v4`. PHITS transport evidence
from v3, older, missing, mixed, or ambiguous geometry provenance is rejected
regardless of recorded gantry, collimator, or MLC values. A newly prepared v4
workspace is required before PHITS transport may be accepted under the
corrected convention.

The correction preserves final RTDOSE voxel coordinates, DICOM patient axes,
dose, MU, normalization, source and gantry geometry, source spectrum, MLC and
jaw values, effective-aperture semantics, and the supported fixed-field 3D-CRT
scope.

## OpenSpec and automated validation

The accepted collimator-direction and recovery requirements were promoted into
the current `iec-gantry-geometry` and `portable-workspace-recovery`
specifications. The completed change is archived as
`2026-08-18-fix-iec-collimator-direction`; no active OpenSpec change remains.

The final pull request #47 revision passed focused renderer, coordinate,
workspace, execution, and recovery tests, source compilation, the public-tree
audit, and public CI run #409. The recorded full local suite result had no new
failure relative to its unchanged environment-dependent baseline. The PATH
OpenSpec CLI remains the older 0.15.0 parser: it accepts nine of ten current
specifications and rejects the unchanged `fixed-6mv-beam-model-safety`
specification under its older SHALL/MUST interpretation. No unrelated
specification was changed to accommodate that parser.

The unrelated archived
`2026-08-07-add-windows-offline-installer` change still contains its known
unchecked historical task. The withdrawn
`add-rtdose-coordinate-output-choice` proposal remains withdrawn.

## README GUI animation

The README now includes a guided-workflow animation whose local paths,
identifiers, generated-output paths, and Activity log bodies were removed with
opaque frame-level masks. The animation retains the five public GUI stages and
contains no external screenshot, DICOM, workspace, or calculation-result
artifact. Its preparation and verification boundary is recorded in the
[GUI animation anonymization handoff](development-handoff-2026-08-18-gui-animation.md).

The same README update replaces the obsolete pre-v4 zero-gantry recovery
wording with the accepted v4 fail-closed rule. This is a documentation
alignment with the already merged runtime and OpenSpec contract, not a new
behavioral change.

## Stopping boundary

The MLCX patient-axis reflection correction, per-field human comparison,
empirical collimator-direction test, repository correction, OpenSpec promotion
and archive, exact-head Codex review, CI, merge, and feature-branch deletion
are complete. No known merge-blocking defect, required repository
implementation, or active OpenSpec change remains.

Do not create another implementation, OpenSpec change, pull request, release,
or tag without a new human-approved purpose. Do not reuse pre-v4 PHITS
transport as evidence for the corrected geometry. Any further physics,
geometry, DICOM, dose, MU, normalization, treatment-scope, real-data, or
real-tool work requires a separate explicit human decision.
