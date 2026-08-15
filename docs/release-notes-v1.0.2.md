# dicomxphits v1.0.2 Release Notes

dicomxphits v1.0.2 strengthens the documented Windows GUI and verified offline
lifecycle for the fixed-field 3D-CRT education-and-research workflow. It does
not extend the supported treatment-technique, clinical, physics, geometry,
dose, MU, machine, or DICOM scope.

## Highlights

- Adds a fixed Elekta Precise 6 MV safety guard and presents the fixed machine
  and nominal energy in the GUI without permitting an unsupported selection.
- Improves the guided GUI with version and author information, a Web site help
  action, minimum-window vertical scrolling, reachable primary actions on all
  five pages, and a more compact Activity log.
- Keeps the accepted non-zero-gantry geometry correction, course-dose contract,
  recovery behavior, workflow stage gating, and OpenSpec safety boundaries.
- Stores per-user GUI settings outside the protected offline runtime.
- Supports verified offline-bundle upgrades and exact-installation uninstall,
  including fail-before-mutation handling for Windows directory locks, a closed
  generated-environment inventory, retained identity-bound deletion handles,
  and protected detached cleanup staging.

## Validation boundary

The public automated suite uses synthetic or mock inputs and does not execute
PHITS, RT-PHITS, CT2PHITS, Sumtally, `phits2dicom`, external GPR software, or
real DICOM. The human operator reported that the current integrated GUI
completed the bounded external workflow from CT2PHITS through RTDOSE. Exact
paths, DICOM identifiers, numeric results, screenshots, result files, and
generated outputs remain outside this repository.

This evidence is one bounded education-and-research workflow. It is not
clinical validation, commissioning, patient QA, vendor certification, or a
general dose-accuracy claim.

## Supported environment and scope

- Python 3.12 remains the supported Python runtime for v1.
- The guided external-tool workflow remains supported only on a Windows host
  with user-supplied licensed tools and confirmed non-patient inputs.
- Linux and the Dev Container remain public development and synthetic/mock
  validation environments, not real-tool runtimes.
- The public scope remains fixed-field 3D-CRT within the documented centered
  `20 x 20 cm2` effective-aperture boundary. IMRT, dynamic MLC delivery, and
  VMAT remain unsupported.

## Upgrade

Build or install v1.0.2 from one exact verified source or release artifact. The
Windows offline installer can replace the matching verified runtime for the
same extracted bundle location, while the verified uninstaller removes only
that exact installation. Preserve case folders, external tools, and per-user
GUI settings outside the extraction root.

For installation and operation, see the [README](../README.md), [GUI User
Guide](gui-user-guide.md), and [Windows Offline Installation
Guide](windows-offline-installation.md).
