# dicomxphits v1.0.1 Release Notes

dicomxphits v1.0.1 completes the documented v1.0.x guided workflow for
education and research use with fixed-field 3D-CRT. It does not extend the
supported treatment-technique, clinical, physics, geometry, dose, MU, machine,
or DICOM scope.

## Highlights

- Adds the Windows CT2PHITS frontend as the first explicit GUI stage and keeps
  its verified frozen handoff separate from the mutable source RT Plan.
- Provides separately gated Workspace, PHITS, Sumtally Generate/Run, and RTDOSE
  Prepare/Run stages with persistent local tool settings and auditable summary
  records.
- Corrects PLAN-dose provenance, active-treatment MU normalization, Sumtally
  `sumfactor`, SETUP-beam exclusion, and the fail-closed digest chain used by
  the GUI and RTDOSE conversion. The `phits2dicom` factor remains `1.0`.
- Corrects RTDOSE isocenter translation and preserves the accepted DICOM
  geometry and coordinate-placement contract.
- Adds Windows and Ubuntu synthetic/mock CI, the v1.0.x GUI user guide, and
  bounded links to the companion GPR and anonymized non-patient DICOM
  repositories.

## Validation boundary

The public automated suite uses synthetic or mock inputs and does not execute
PHITS, RT-PHITS, CT2PHITS, Sumtally, `phits2dicom`, external GPR software, or
real DICOM. An explicitly authorized external non-patient workflow was reported
complete through the GUI and external GPR comparison. Exact paths, DICOM,
numeric results, screenshots, result files, and generated outputs remain
outside this repository.

This evidence is one bounded education-and-research workflow. It is not
clinical validation, commissioning, patient QA, vendor certification, or a
general dose-accuracy claim.

## Supported environment and scope

- Python 3.12 is the supported Python runtime for v1.
- The guided external-tool workflow is supported only on a Windows host with
  user-supplied licensed tools and confirmed non-patient inputs.
- Linux and the Dev Container support public development, synthetic/mock
  validation, and the public-tree audit, not the real-tool workflow.
- The public scope remains fixed-field 3D-CRT within the documented centered
  `20 x 20 cm2` effective-aperture boundary. IMRT, dynamic MLC delivery, and
  VMAT remain unsupported.

The active `support-portable-workspace-recovery` OpenSpec change remains an
unapproved proposal and is not implemented in v1.0.1.

## Upgrade

Reinstall the package from the v1.0.1 source or release artifact in a Python
3.12 environment. No automated workspace migration or portable-workspace
recovery is provided. Use a new workspace for release validation, or follow the
documented in-place stage restart and overwrite rules. Do not assume that a
relocated or partially completed workspace can resume automatically.

For installation and operation, see the [README](../README.md) and
[GUI User Guide](gui-user-guide.md).
