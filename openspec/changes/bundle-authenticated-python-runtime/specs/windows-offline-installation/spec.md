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
Before starting Windows PowerShell, the bootstrap MUST clear inherited CLR
profiling, startup-hook, and AppDomain-manager environment variables that can
load caller-selected managed or native code before the verification command.
Failure to acquire a no-delete-sharing handle for any required bundle directory
MUST stop installation; an access-denied directory MUST NOT be skipped.
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

#### Scenario: Inherited CLR startup injection

- **WHEN** the caller sets CLR profiler, startup-hook, or AppDomain-manager
  environment variables before starting the offline bootstrap
- **THEN** bootstrap clears them before its first PowerShell process and no
  caller-selected CLR startup code runs

#### Scenario: Bundle directory lock is denied

- **WHEN** a required bundle directory can be inspected but its protective
  no-delete-sharing handle cannot be acquired
- **THEN** bootstrap fails before elevation and does not skip that directory

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
point. It SHALL complete bundle verification and payload read locking before
requesting elevation. The elevated stage MUST perform only source verification
and protected runtime and bundle-source construction; Python, the helper, venv, and
pip MUST run in the original non-elevated stage after it validates the
protected receipt and runtime. It SHALL construct and use only the authenticated
installation-specific CPython 3.12.10 x64 runtime derived from the bundled
Python package and Tcl/Tk component. It MUST NOT discover, probe, repair,
install, or execute an existing host Python interpreter, registry candidate,
`py.exe`, or bare `python.exe`.

The runtime MUST be created below a protected Windows Common Application Data
root that is owned by built-in Administrators, grants mutation only to `SYSTEM`
and elevated Administrators, grants the installing user read/execute access,
and uses an inheritable `OWNER RIGHTS` rule that does not grant `WRITE_DAC`.
Before its first Python launch, the stage MUST validate the complete runtime
tree as regular non-reparse content with the exact protected owner and access
rules, compare every runtime file to its authenticated source-derived digest
while acquiring its read lock, reject any missing or additional entry, and
repeat the complete inventory while all file handles are held. Every file
handle MUST remain held through the end of installation.
The protected runtime SHALL contain an exact read-only snapshot of the
inventoried bundle. The installing user MUST NOT be able to add or replace a
source entry, and helper and pip paths MUST resolve from that snapshot while
`.venv`, the log, and the launcher remain at the extracted installation root.

#### Scenario: Elevation is denied or unavailable

- **WHEN** the verified stage cannot obtain and confirm administrator authority
- **THEN** setup stops before executing the NuGet verifier, Windows Installer,
  Python, helper, or pip and makes no runtime or dependency change

#### Scenario: Non-elevated process attempts runtime injection

- **WHEN** another process running as the installing user without elevation
  attempts to add `python312._pth`, a shadow module, or another entry after the
  authenticated runtime inventory
- **THEN** protected storage denies the addition, the final inventory remains
  complete, and no unauthenticated startup code executes

#### Scenario: Protected runtime boundary is not exact

- **WHEN** a protected parent or runtime path is existing, linked, incorrectly
  owned, has additional or writable access rules,
  or otherwise cannot prove the required protected state
- **THEN** setup stops before Python execution and does not repair, reuse,
  delete, or weaken that path

#### Scenario: Application-specific runtime is complete

- **WHEN** authenticated extraction produces the required CPython, standard
  library, venv, pip, and Tcl/Tk files under the exact protected boundary and
  every file and directory passes the final protected inventory
- **THEN** the absolute protected interpreter is probed as CPython 3.12 x64 and
  may run the verified helper

#### Scenario: Host Python is malicious

- **WHEN** an existing host installation contains signed Python binaries but a
  modified standard library or additional shadow module
- **THEN** the bootstrap does not inspect or execute that installation and uses
  only the authenticated protected runtime

#### Scenario: Current-directory Python lookalikes

- **WHEN** the extraction or current directory contains `python.exe` or
  `py.exe`
- **THEN** neither file executes during runtime construction or installation

#### Scenario: Runtime already exists or cannot be locked

- **WHEN** the protected runtime target has unexpected pre-existing content or
  any runtime path is missing, additional, changed, linked, non-regular, or
  cannot be read-locked
- **THEN** setup stops before Python execution and does not repair, reuse, or
  delete the runtime

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
