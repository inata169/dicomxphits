# Windows Offline Installation Delta

## MODIFIED Requirements

### Requirement: Bundle Integrity Inventory

The preparation command SHALL generate `bundle-manifest.json` and
`SHA256SUMS.txt` with normalized relative paths, byte sizes, SHA-256 values,
and artifact roles for every payload, and SHALL identify the source HEAD commit
and exact Git index-entry fingerprint. `SHA256SUMS.txt` SHALL also contain the
manifest digest and, as the unavoidable self-reference exception, MUST NOT
claim to contain its own digest. Every downloaded installer and wheel MUST be
listed in both inventories. Offline bootstrap verification MUST use an absolute
PowerShell executable below the Windows system directory, MUST reject a
reparse-point bundle root, checksum file, or protected payload component, and
MUST NOT execute any bundle-provided executable or Python helper until the
inventory has passed and protected payloads are read-locked.

#### Scenario: Complete inventory

- **WHEN** staging finishes successfully
- **THEN** every downloaded and source payload has matching size and SHA-256
  metadata and the checksum file includes the completed manifest

#### Scenario: Unsafe inventory path

- **WHEN** an inventory entry is absolute, duplicated, escapes the bundle root,
  or traverses a symbolic link, junction, or other reparse point
- **THEN** verification rejects the bundle before executing an installer,
  helper, or pip

#### Scenario: Payload changed after preparation

- **WHEN** any inventoried payload has a different size or SHA-256
- **THEN** offline installation stops before Python installation or dependency
  changes

#### Scenario: Current-directory PowerShell lookalike

- **WHEN** the extraction or current directory contains `powershell.exe`
- **THEN** bootstrap uses only the quoted absolute Windows system PowerShell
  path and the lookalike is not executed

### Requirement: One-Entry Offline Python Setup

The extracted bundle SHALL provide `install_offline.cmd` as the normal entry
point. It SHALL accept an existing interpreter only when a bounded absolute
installed path has a valid expected Authenticode signer, is protected against
replacement for the installation lifetime, and reports CPython 3.12 64-bit. If
none is found, it SHALL install the verified bundled Python 3.12.10 x64
installer for the current user with pip, the Python Launcher, and Tcl/Tk
enabled, without changing PATH, creating Python file associations, or creating
shortcuts, then locate, authenticate, lock, and revalidate the resulting
absolute interpreter before continuing. It MUST NOT execute `py.exe`,
`python.exe`, or another candidate by bare name.

#### Scenario: Existing supported interpreter

- **WHEN** a bounded installed interpreter has the expected valid signature and
  reports CPython 3.12 x64
- **THEN** installation locks and uses its absolute path without starting the
  bundled Python installer

#### Scenario: No supported interpreter

- **WHEN** no bounded signed CPython 3.12 x64 candidate validates
- **THEN** the bundled installer runs only after bundle verification, and its
  result is found and validated through the same absolute-path contract

#### Scenario: Python setup fails

- **WHEN** the installer returns failure or the resulting interpreter, pip, or
  tkinter validation fails
- **THEN** setup stops with a controlled error recorded in
  `offline-install.log`

#### Scenario: Current-directory Python lookalikes

- **WHEN** the extraction or current directory contains `python.exe` or
  `py.exe`
- **THEN** neither file executes during interpreter discovery or installation

### Requirement: Complete Binary-Only Wheelhouse

The preparation command SHALL obtain runtime and editable-build requirements
from a reviewed Windows x64 lock that records exact versions, expected wheel
filenames, and SHA-256 digests. It MUST use CPython 3.12 `win_amd64`, binary-only,
hash-required dependency resolution, MUST reject source distributions or any
artifact absent from the lock, and MUST verify that the captured wheel set and
hashes exactly match the lock. Normal CI SHALL install the same pinned runtime
versions so runtime dependency divergence is explicit rather than accidental.

#### Scenario: Locked runtime requirements

- **WHEN** a bundle is prepared from the reviewed lock
- **THEN** every runtime and build wheel has the exact locked version, filename,
  and SHA-256 and the manifest records the same evidence

#### Scenario: Current runtime requirements

- **WHEN** the current project metadata names `numpy` and `pydicom`
- **THEN** the exact locked wheels for both names, `setuptools`, `wheel`, and
  every locked transitive dependency are included and inventoried

#### Scenario: NumPy platform mismatch

- **WHEN** NumPy is absent or its available wheel does not carry
  `cp312-cp312-win_amd64`
- **THEN** preparation fails before ZIP creation

#### Scenario: Source archive appears

- **WHEN** dependency resolution produces a source archive instead of only
  wheels
- **THEN** preparation fails and identifies the unsupported artifact

#### Scenario: Wheel differs from lock

- **WHEN** a wheel is missing, additional, differently versioned, renamed, or
  has a different SHA-256
- **THEN** preparation fails before ZIP creation

#### Scenario: CI and offline runtime versions

- **WHEN** normal CI and Windows offline bundle preparation install runtime
  dependencies for the same revision
- **THEN** both use the reviewed pinned NumPy and pydicom versions
