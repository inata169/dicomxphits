# Windows Offline Installation Delta

## MODIFIED Requirements

### Requirement: Versioned Windows Offline Bundle

The project SHALL provide an online Windows preparation command that creates
`dist/dicomxphits-offline-win64-<version>.zip` for Windows 10/11 x64 and Python
3.12. The bundle SHALL contain the audited Git-indexed public project blobs,
the offline entry point, documentation, an authenticated application-local
CPython 3.12.10 x64 NuGet package, an authenticated CPython Tcl/Tk component,
a pinned authenticated NuGet signature verifier, the complete compatible
wheelhouse, and integrity metadata. It MUST NOT copy arbitrary untracked or
ignored worktree content.

#### Scenario: Successful online preparation

- **WHEN** the public-tree audit passes, every required indexed source file is
  available, all Python runtime sources are authentic, and compatible wheels
  resolve
- **THEN** preparation writes one versioned ZIP whose extracted root is the
  editable project root and whose authenticated sources can construct the
  complete application-local Python runtime without host Python installation

#### Scenario: Runtime source is not authentic

- **WHEN** the NuGet verifier, Python package, or Tcl/Tk component lacks its
  expected valid signature or identity
- **THEN** preparation stops and does not create a final ZIP

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

The preparation command SHALL download the exact official application-local
CPython 3.12.10 x64 NuGet package and exact official CPython 3.12.10 x64 Tcl/Tk
MSI component over HTTPS. It MUST validate the Python package's NuGet repository
signature, MUST validate a Python Software Foundation Authenticode signature
on the Tcl/Tk component, and MUST validate the expected Microsoft
Authenticode signature on the pinned NuGet verifier. It SHALL record artifact
URLs, SHA-256 values, sizes, signature status and signer evidence, package
identity, and versions in the bundle manifest.

#### Scenario: Valid application-local runtime sources

- **WHEN** all three artifacts have the expected valid signatures and the
  Python package identifies version 3.12.10
- **THEN** preparation records their provenance and may add them to the bundle

#### Scenario: Missing, invalid, or unexpected runtime signature

- **WHEN** any signature validation fails or reports an unexpected signer,
  package identity, or version
- **THEN** preparation stops and does not create a final ZIP

### Requirement: Bundle Integrity Inventory

The preparation command SHALL generate `bundle-manifest.json` and
`SHA256SUMS.txt` with normalized relative paths, byte sizes, SHA-256 values,
and artifact roles for every payload, and SHALL identify the source HEAD commit
and exact Git index-entry fingerprint. `SHA256SUMS.txt` SHALL also contain the
manifest digest and, as the unavoidable self-reference exception, MUST NOT
claim to contain its own digest. Every runtime source, verifier, and wheel MUST
be listed in both inventories. Offline bootstrap verification MUST use an
absolute PowerShell executable below the Windows system directory, MUST reject
reparse-point paths, and MUST NOT execute a bundle verifier, Windows Installer,
Python executable, helper, or pip until its required input has passed the
applicable inventory and signature checks and has been read-locked.
The bootstrap MUST reject any unmanifested file in the extracted source tree.
Before helper or pip execution, the elevated stage SHALL copy only inventoried
payloads into protected storage, and the non-elevated stage MUST use that exact
protected snapshot for bundle verification, wheel installation, and editable
source installation.

#### Scenario: Complete inventory

- **WHEN** staging finishes successfully
- **THEN** every downloaded and source payload has matching size and SHA-256
  metadata and the checksum file includes the completed manifest

#### Scenario: Unsafe inventory path

- **WHEN** an inventory entry is absolute, duplicated, escapes the bundle root,
  or traverses a symbolic link, junction, or other reparse point
- **THEN** verification rejects the bundle before executing a verifier,
  Windows Installer, Python, helper, or pip

#### Scenario: Payload changed after preparation

- **WHEN** any inventoried payload has a different size or SHA-256
- **THEN** offline installation stops before runtime extraction or dependency
  changes

#### Scenario: Unmanifested build source

- **WHEN** the extracted bundle contains `setup.py` or another file absent from
  the integrity inventories
- **THEN** bootstrap rejects it, the protected source snapshot excludes it,
  and neither helper nor pip executes it

#### Scenario: Current-directory PowerShell lookalike

- **WHEN** the extraction or current directory contains `powershell.exe`
- **THEN** bootstrap uses only the quoted absolute Windows system PowerShell
  path and the lookalike is not executed

#### Scenario: Runtime artifact changed after preparation

- **WHEN** the verifier, Python package, Tcl/Tk component, or another payload
  differs from its inventory
- **THEN** offline installation stops before extracting or executing runtime
  content

#### Scenario: Unsafe runtime extraction path

- **WHEN** a runtime archive entry is absolute, drive-relative, duplicated,
  escaping, link-like, non-regular, or traverses a reparse point
- **THEN** extraction fails before any Python process starts

### Requirement: One-Entry Offline Python Setup

The extracted bundle SHALL provide `install_offline.cmd` as the normal entry
point. It SHALL construct and use only the authenticated application-local
CPython 3.12.10 x64 runtime derived from the bundled Python package and Tcl/Tk
component. It MUST NOT discover, probe, repair, install, or execute an existing
host Python interpreter, registry candidate, `py.exe`, or bare `python.exe`.
Before its first Python launch, it MUST validate the complete runtime tree as
regular non-reparse content, compare every runtime file to its authenticated
source-derived digest while acquiring its read lock, reject any additional
file, and retain every lock through the end of installation.

#### Scenario: Host Python is malicious

- **WHEN** an existing host installation contains signed Python binaries but a
  modified standard library or additional shadow module
- **THEN** the bootstrap does not inspect or execute that installation and uses
  only the authenticated application-local runtime

#### Scenario: Application-local runtime is complete

- **WHEN** authenticated extraction produces the required CPython, standard
  library, venv, pip, and Tcl/Tk files
- **THEN** the locked absolute application-local interpreter is probed as
  CPython 3.12 x64 and may run the verified helper

#### Scenario: Runtime already exists or cannot be locked

- **WHEN** the runtime target has unexpected pre-existing content or any
  runtime path is missing, additional, changed, linked, non-regular, or cannot
  be read-locked
- **THEN** setup stops before Python execution and does not repair or delete the
  runtime

#### Scenario: Current-directory Python lookalikes

- **WHEN** the extraction or current directory contains `python.exe` or
  `py.exe`
- **THEN** neither file executes during runtime construction or installation

### Requirement: Synthetic Offline-Installer Validation Boundary

Automated tests SHALL use temporary synthetic paths, fabricated wheel and
runtime packages, mock or fake subprocesses, synthetic metadata, and copied
signed test binaries when Windows signature behavior is required. They MUST NOT
install or modify a host Python product, access the network, run PHITS-related
tools, or process real DICOM.

#### Scenario: Automated runtime trust test

- **WHEN** runtime provenance, extraction, locking, or malicious-host behavior
  is tested
- **THEN** the test remains in controlled temporary storage and no host Python
  installation or external scientific tool is changed or executed

#### Scenario: Automated installer failure test

- **WHEN** wheel, checksum, virtual-environment, path, or launcher behavior is
  tested
- **THEN** the test remains in controlled temporary storage and uses no real
  installer, network, licensed external tool, or patient data
