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
and exact Git index-entry fingerprint. Every runtime source, verifier, and wheel
MUST be listed in both inventories. Offline bootstrap verification MUST use an
absolute PowerShell executable below the Windows system directory, MUST reject
reparse-point paths, and MUST NOT execute a bundle verifier, Windows Installer,
Python executable, helper, or pip until its required input has passed the
applicable inventory and signature checks and has been read-locked.

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
regular non-reparse content and read-lock every runtime file through the end of
installation.

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
