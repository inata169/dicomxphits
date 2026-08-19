# dicomxphits v1.0.3 Release Notes

dicomxphits v1.0.3 publishes the reviewed post-v1.0.2 geometry corrections and
their fail-closed workspace-recovery boundary for the fixed-field 3D-CRT
education-and-research workflow. It does not extend the supported
treatment-technique, clinical, physics, dose, MU, machine, or DICOM scope.

## Highlights

- Corrects the patient-axis reflection of DICOM IEC MLCX leaf intervals while
  preserving the existing leaf-pair ordering and public aperture boundary.
- Corrects the IEC collimator rotation direction applied by the PHITS
  accelerator transform while retaining the recorded DICOM angle.
- Advances prepared-workspace geometry provenance to the accepted v4 contract
  and rejects all pre-v4, missing, mixed, or ambiguous PHITS transport evidence.
- Aligns the README and workflow guidance with v4-only transport reuse and the
  public companion-comparison description.
- Adds the reviewed sanitized guided-workflow animation without local paths,
  identifiers, result locations, runtime values, or Activity log content.

## Validation boundary

The public automated suite uses synthetic or mock inputs and does not execute
PHITS, RT-PHITS, CT2PHITS, Sumtally, `phits2dicom`, external GPR software, or
real DICOM. The human operator reported completion of the bounded external GUI
workflow through the GPR visual-comparison stage and marked the v1.0.3 GUI
release gate as passed. The repository does not contain, duplicate, or
independently assess the external workspace, DICOM, images, numerical values,
comparison results, or generated outputs. The durable boundary for the
human-reported visual acceptance remains in the
[project status](project-status.md).

This evidence is a bounded human release decision for education-and-research
software. It is not clinical validation, commissioning, patient QA, vendor
certification, or a general dose-accuracy claim.

## Preserved contracts

- Python 3.12 remains the supported Python runtime for v1.
- The guided external-tool workflow remains supported only on a Windows host
  with user-supplied licensed tools and confirmed non-patient inputs.
- Final RTDOSE voxel coordinates, DICOM patient axes, dose, MU, normalization,
  source spectrum, effective-aperture semantics, and the fixed-field 3D-CRT
  treatment scope are unchanged.
- PHITS transport may be reused only when the current v4 geometry provenance
  validates; a final-DICOM coordinate correction cannot repair older transport.

## Upgrade

Prepare a new v4 workspace and rerun PHITS, Sumtally, and RTDOSE for any case
whose transport evidence is v3, older, missing, mixed, or ambiguous. Do not
empirically adjust an older result to compensate for the corrected MLCX or
collimator convention.

For installation and operation, see the [README](../README.md), [GUI User
Guide](gui-user-guide.md), [workflow stage guide](workflow_stages.md), and
[Windows Offline Installation Guide](windows-offline-installation.md).

## Windows offline release asset

The v1.0.3 GitHub Release does not include a Windows offline ZIP. A local
candidate passed the bounded human installation and GUI-startup checks, but
behavior-based endpoint protection blocked the verified uninstaller. Because
the complete lifecycle did not pass, that candidate is not a final release
artifact and must not be uploaded or represented as a supported v1.0.3 asset.
Its local path, checksum, size, and endpoint-product details are intentionally
not published here.

The relevant installer and uninstaller implementation is unchanged from the
v1.0.2 tag. The v1.0.2 custom offline ZIP was therefore withdrawn and removed;
its tag, GitHub Release, source archives, and historical integrity record are
retained.

The repository retains the offline-bundle builder for maintainer evaluation,
without changing its runtime or specification contract. Users should not
disable endpoint protection or exclude system PowerShell as a workaround. A
future public offline asset requires separate review and a newly built
exact-HEAD candidate that passes installation, GUI startup, and verified
uninstallation under the intended endpoint protection environment.
