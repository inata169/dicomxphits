# Windows Offline Installation Specification

## Purpose

Define the authenticated, binary-only producer bundle and fail-closed
single-entry installation contract for supported offline Windows 10/11 x64
computers without changing the dicomxphits runtime or external-tool boundary.
## Requirements
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
mode using only the protected snapshot of the bundled wheelhouse and source.
Missing or incompatible artifacts MUST fail without URL or index fallback.

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
and extracting the ZIP on a local disk, running `install_offline.cmd`, and
approving its administrator prompt. It SHALL explain why protected runtime
storage and administrator approval are required, how a denied prompt fails
without starting Python, that the protected runtime persists as the `.venv`
base, and that removal is a separate explicit administrator action. It SHALL
explain that PHITS, RT-PHITS, phits2dicom, and GPR-comparing remain separately
obtained external tools and SHALL preserve the education/research, non-patient
phantom, and fixed-field 3D-CRT boundaries. It MUST NOT instruct users to run
the editable environment from USB or imply clinical suitability.

#### Scenario: Offline user follows the primary instructions

- **WHEN** a user reads either language's primary offline procedure
- **THEN** the required steps are local-disk ZIP extraction, execution of
  `install_offline.cmd`, and approval of the verified administrator stage

#### Scenario: User denies administrator approval

- **WHEN** the user declines or cannot satisfy the administrator prompt
- **THEN** documentation states that installation stops before Python and does
  not advise weakening access controls or substituting a host interpreter

#### Scenario: External workflow tools are absent

- **WHEN** Python package installation completes without PHITS-related tools
- **THEN** documentation presents package setup as successful while explaining
  that separately and legitimately obtained external tools are still required
  for their explicit stages

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
