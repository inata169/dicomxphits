# Windows Offline Installation Specification

## Purpose

Define the authenticated, binary-only producer bundle and fail-closed
single-entry installation contract for supported offline Windows 10/11 x64
computers without changing the dicomxphits runtime or external-tool boundary.

## Requirements
### Requirement: Versioned Windows Offline Bundle

The project SHALL provide an online Windows preparation command that creates
`dist/dicomxphits-offline-win64-<version>.zip` for Windows 10/11 x64 and Python
3.12. The bundle SHALL contain the audited Git-indexed public project blobs, the
offline entry point, documentation, the official Python 3.12.10 x64 installer,
the complete compatible wheelhouse, and integrity metadata. It MUST NOT copy
arbitrary untracked or ignored worktree content.

#### Scenario: Successful online preparation

- **WHEN** the public-tree audit passes, every required indexed source file is
  available, the Python installer is authentic, and compatible wheels resolve
- **THEN** preparation writes one versioned ZIP whose extracted root is the
  editable project root

#### Scenario: Untracked local material exists

- **WHEN** the preparation worktree contains an unrelated untracked or ignored
  file
- **THEN** source collection does not include or recursively inspect that file

#### Scenario: Indexed path has an unstaged modification

- **WHEN** a Git-indexed source path differs in the working tree after its
  indexed blob was audited
- **THEN** source collection uses the audited indexed blob and does not copy
  the unstaged bytes

#### Scenario: Required offline source is not indexed

- **WHEN** an installer, helper, or required document is absent from Git's
  indexed path set
- **THEN** preparation stops instead of adding that untracked file to the
  bundle

### Requirement: Authenticated Python Runtime Artifact

The preparation command SHALL download the exact official Python 3.12.10
64-bit Windows installer over HTTPS. It MUST accept the installer only when
Windows Authenticode validation reports a valid signature identifying the
Python Software Foundation, and SHALL record its URL, SHA-256, size, signature
status, signer subject, certificate thumbprint, and certificate validity
metadata in the bundle manifest.

#### Scenario: Valid official installer

- **WHEN** the downloaded Python 3.12.10 x64 installer has a valid expected
  Authenticode signature
- **THEN** preparation records its provenance and may add it to the staging
  bundle

#### Scenario: Missing, invalid, or unexpected signature

- **WHEN** Authenticode validation is not valid or the signer does not identify
  the Python Software Foundation
- **THEN** preparation stops and does not create a final ZIP

### Requirement: Complete Binary-Only Wheelhouse

The preparation command SHALL derive runtime requirements from
`pyproject.toml` and download wheels for CPython 3.12 on Windows x64 together
with `setuptools` and `wheel`. It MUST use binary-only dependency resolution,
MUST reject source distributions, and MUST verify that the direct runtime and
editable-build requirements are present. The NumPy artifact MUST have the
exact `cp312-cp312-win_amd64` tags.

#### Scenario: Current runtime requirements

- **WHEN** the current project metadata names `numpy` and `pydicom`
- **THEN** compatible wheels for both names, `setuptools`, `wheel`, and any
  resolved transitive dependencies are included and inventoried

#### Scenario: NumPy platform mismatch

- **WHEN** NumPy is absent or its available wheel does not carry
  `cp312-cp312-win_amd64`
- **THEN** preparation fails before ZIP creation

#### Scenario: Source archive appears

- **WHEN** dependency resolution produces a source archive instead of only
  wheels
- **THEN** preparation fails and identifies the unsupported artifact

### Requirement: Bundle Integrity Inventory

The preparation command SHALL generate `bundle-manifest.json` and
`SHA256SUMS.txt` with normalized relative paths, byte sizes, SHA-256 values,
and artifact roles for every payload, and SHALL identify the source HEAD commit
and exact Git index-entry fingerprint. `SHA256SUMS.txt` SHALL also contain the
manifest digest and, as the unavoidable self-reference exception, MUST NOT
claim to contain its own digest. Every downloaded installer and wheel MUST be
listed in both inventories.

#### Scenario: Complete inventory

- **WHEN** staging finishes successfully
- **THEN** every downloaded and source payload has matching size and SHA-256
  metadata and the checksum file includes the completed manifest

#### Scenario: Unsafe inventory path

- **WHEN** an inventory entry is absolute, duplicated, or escapes the bundle
  root
- **THEN** verification rejects the bundle before executing an installer or
  pip

#### Scenario: Payload changed after preparation

- **WHEN** any inventoried payload has a different size or SHA-256
- **THEN** offline installation stops before Python installation or dependency
  changes

### Requirement: One-Entry Offline Python Setup

The extracted bundle SHALL provide `install_offline.cmd` as the normal entry
point. It SHALL accept an existing interpreter only when it is Python 3.12
64-bit. If none is found, it SHALL install the verified bundled Python 3.12.10
x64 installer for the current user with pip, the Python Launcher, and Tcl/Tk
enabled, without changing PATH, creating Python file associations, or creating
shortcuts, then revalidate the resulting interpreter before continuing.

#### Scenario: Existing supported interpreter

- **WHEN** an existing Python reports version 3.12 and 64-bit architecture
- **THEN** installation uses it without starting the bundled Python installer

#### Scenario: No supported interpreter

- **WHEN** no Python 3.12 x64 candidate validates
- **THEN** the bundled installer runs for the current user with pip, Launcher,
  and Tcl/Tk enabled and its result is revalidated

#### Scenario: Python setup fails

- **WHEN** the installer returns failure or the resulting interpreter, pip, or
  tkinter validation fails
- **THEN** setup stops with a controlled error recorded in
  `offline-install.log`

### Requirement: Safe Repository-Local Virtual Environment

Offline installation SHALL create `.venv` at the extracted repository root.
It MAY reuse an existing `.venv` only when its interpreter executes and reports
Python 3.12 x64. It MUST NOT delete, rename, overwrite, or automatically repair
an existing incompatible or malformed `.venv`.

#### Scenario: No existing virtual environment

- **WHEN** `.venv` is absent and the selected Python is valid
- **THEN** the installer creates the repository-local environment

#### Scenario: Existing compatible virtual environment

- **WHEN** `.venv` contains a working Python 3.12 x64 interpreter
- **THEN** the installer may reuse it and revalidate its packages

#### Scenario: Existing incompatible virtual environment

- **WHEN** `.venv` uses another Python minor version, is 32-bit, or cannot be
  validated
- **THEN** installation stops without changing that directory and explains
  the manual remove-or-rename-and-rerun procedure

### Requirement: No-Network Editable Installation

Every pip install subprocess SHALL use `--no-index`,
`--find-links <bundled-wheelhouse>`, and `--no-build-isolation`, and the
installer SHALL also set a no-index pip environment guard. It SHALL install
`setuptools`, `wheel`, the runtime requirements, and dicomxphits in editable
mode using only the bundled wheelhouse. Missing or incompatible artifacts MUST
fail without URL or index fallback.

#### Scenario: Complete wheelhouse

- **WHEN** all compatible dependency and build wheels are present
- **THEN** the repository-local environment is populated and editable
  dicomxphits installation completes without network access

#### Scenario: Required wheel missing

- **WHEN** a direct or transitive requirement cannot be satisfied from the
  wheelhouse
- **THEN** pip fails locally and the installer reports the missing offline
  dependency without contacting an index

#### Scenario: Path contains spaces and Japanese text

- **WHEN** the extracted local path contains spaces or Japanese characters
- **THEN** interpreter, wheelhouse, editable source, log, and launcher paths
  are passed without truncation or shell reinterpretation

### Requirement: Verified Completion and Optional GUI Launch

The installer SHALL verify imports of `tkinter`, `numpy`, `pydicom`, and
`dicomxphits`, record Python, NumPy, and pydicom versions and installation
results in `offline-install.log`, and display the existing GUI launcher command
after success. It MUST start the GUI only after an explicit affirmative user
choice and MUST NOT start PHITS or any other calculation.

#### Scenario: Installation verification succeeds

- **WHEN** all required imports succeed in the repository-local environment
- **THEN** the log records the versions and the user sees the existing GUI
  launcher command

#### Scenario: User declines GUI startup

- **WHEN** installation succeeds and the user does not explicitly choose yes
- **THEN** the installer exits successfully without starting the GUI

#### Scenario: User chooses GUI startup

- **WHEN** installation succeeds and the user explicitly chooses yes
- **THEN** the installer invokes the existing repository-local GUI launcher
  and does not invoke a PHITS-related workflow stage

### Requirement: Documented Safety and Transfer Boundary

English and Japanese documentation SHALL reduce offline operation to copying
and extracting the ZIP on a local disk and running `install_offline.cmd`. It
SHALL explain that PHITS, RT-PHITS, phits2dicom, and GPR-comparing remain
separately obtained external tools and SHALL preserve the education/research,
non-patient phantom, and fixed-field 3D-CRT boundaries. It MUST NOT instruct
users to run the editable environment from USB or imply clinical suitability.

#### Scenario: Offline user follows the primary instructions

- **WHEN** a user reads either language's primary offline procedure
- **THEN** the only required steps are local-disk ZIP extraction and execution
  of `install_offline.cmd`

#### Scenario: External workflow tools are absent

- **WHEN** Python package installation completes without PHITS-related tools
- **THEN** documentation presents package setup as successful while explaining
  that separately and legitimately obtained external tools are still required
  for their explicit stages

### Requirement: Synthetic Offline-Installer Validation Boundary

Automated tests SHALL use temporary synthetic paths, fabricated wheel files,
mock or fake subprocesses, and synthetic metadata. They MUST NOT perform actual
Python installation, network access, PHITS-related execution, or real DICOM
processing.

#### Scenario: Automated installer failure test

- **WHEN** wheel, checksum, virtual-environment, path, or launcher behavior is
  tested
- **THEN** the test remains in controlled temporary storage and uses no real
  installer, network, licensed external tool, or patient data
