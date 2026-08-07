# Add Windows Offline Installer

## Why

The supported Windows 10/11 workflow currently assumes that Python 3.12 and
the package dependencies can already be installed on the target computer.
That leaves an internet-disconnected research computer without a documented,
bounded way to obtain the supported Python runtime, compatible binary wheels,
and the public dicomxphits source from removable storage.

An online preparation step and a fail-closed offline installer are needed so a
reviewed USB bundle can be produced on an internet-connected Windows computer,
copied to local storage on an offline computer, and installed without allowing
pip or another step to fall back to the network.

## What Changes

- Add an online Windows PowerShell preparation command that downloads the
  official Python 3.12.10 x64 installer, validates its Authenticode signature,
  resolves the current runtime dependencies from `pyproject.toml`, downloads
  Windows CPython 3.12 wheels only, and produces a versioned ZIP.
- Build the source portion only from Git-indexed public repository paths after
  the existing public-tree audit passes; do not discover or copy arbitrary
  untracked worktree content.
- Require the wheelhouse to contain `numpy`, `pydicom`, `setuptools`, and
  `wheel`, and require the NumPy wheel to carry the
  `cp312-cp312-win_amd64` compatibility tags.
- Add a manifest and checksum inventory containing relative paths, sizes,
  SHA-256 values, artifact roles, dependency requirements, Python installer
  provenance, and Authenticode signer evidence.
- Add a root `install_offline.cmd` entry point and standard-library-only Python
  helper that verify the bundle, select or install 64-bit Python 3.12, safely
  create or reuse a matching repository-local `.venv`, install exclusively
  from the bundled wheelhouse, perform import/version checks, record a log, and
  offer GUI startup only after success and explicit user selection.
- Add English and Japanese offline preparation, installation, and
  troubleshooting documentation linked from the README.
- Add synthetic and mock tests for wheel compatibility, missing artifacts,
  checksum failures, offline pip arguments, incompatible existing virtual
  environments, Unicode/space-containing paths, and existing launcher use.

## Impact

- New capability: `windows-offline-installation`
- Likely added files: `tools/prepare_offline_bundle.ps1`, Python preparation
  and installation helpers, `install_offline.cmd`, offline documentation, and
  focused tests
- Likely modified files: `README.md` and any minimal packaging or public-tree
  allowlist metadata required by the reviewed implementation
- Generated but ignored artifacts: Python installer, dependency wheels,
  staging tree, checksum/manifest outputs, and
  `dist/dicomxphits-offline-win64-<version>.zip`
- Unchanged runtime: GUI and workflow modules, DICOM meaning, PHITS physics,
  dose/MU/normalization contracts, effective-aperture limits, and the existing
  GUI launcher's behavior
- Unchanged external boundary: PHITS, RT-PHITS, `RTphits_win.bat`,
  `HumanVoxelTable.data`, phits2dicom, GPR-comparing, real DICOM, local
  configuration, and calculation results remain external and are not bundled

## Approval Status

The primary user explicitly approved proceeding with this proposal during the
2026-08-07 work session. Implementation, authorized network downloads, local
artifact generation, specification promotion, and archival were then completed
under that approval. Generated Python installers, wheels, and ZIP files remain
uncommitted as required.
