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
The bootstrap MUST authenticate and rehash the manifest-listed
`install_offline.cmd`, retain a strict read handle without delete sharing on
that file to protect the bundle root from rename, and retain that protection
through the verified stage. The bootstrap MUST acquire a no-delete-sharing
handle for every required child directory below the bundle root in each
inventoried payload parent chain. Failure to acquire or retain the root-file
protection or any required child-directory handle MUST stop installation before
elevation; an access-denied child directory MUST NOT be skipped.
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

#### Scenario: Bundle root is the caller current directory

- **WHEN** the calling PowerShell retains the extracted bundle root as its
  current directory
- **THEN** bootstrap protects the root through the authenticated, rehashed,
  strict `install_offline.cmd` read handle, protects every required child
  directory with a no-delete-sharing handle, and blocks root and child-directory
  rename through the verified stage

#### Scenario: Bundle root protection cannot be acquired

- **WHEN** the manifest-listed `install_offline.cmd` cannot be authenticated,
  rehashed, or held with the required strict read handle
- **THEN** bootstrap fails before elevation and does not execute a bundle
  verifier, Windows Installer, Python, helper, or pip

#### Scenario: Bundle directory lock is denied

- **WHEN** a required child directory can be inspected but its protective
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
and protected runtime and bundle-source construction; Python, the helper, venv,
and pip MUST run in the original non-elevated stage after it validates the
protected receipt and runtime. It SHALL construct and use only the authenticated
installation-specific CPython 3.12.10 x64 runtime derived from the bundled
Python package and Tcl/Tk component. It MUST NOT discover, probe, repair,
install, or execute an existing host Python interpreter, registry candidate,
`py.exe`, or bare `python.exe`.

The protected runtime identity MUST be deterministically derived from a
versioned encoding of both the normalized absolute extraction root and the
already verified bundle-manifest SHA-256. The verified manifest digest MUST be
carried explicitly into the elevated stage and revalidated before protected
runtime construction. Different authenticated bundle manifests at the same
fresh extraction path SHALL select distinct protected runtime targets. The same
authenticated manifest at the same normalized path SHALL select the same
target and MUST fail closed if that target already exists.

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

When protected runtime construction returns a nonzero result, the installer
SHALL report a specific elevated-stage reason when a nonce-bound diagnostic can
be read from the exact protected runtime-control boundary and validated with
the expected owner and access rules. That diagnostic MUST be display-only and
MUST NOT authorize execution, choose a runtime, skip validation, or weaken a
failure. If no valid protected diagnostic is available, the installer SHALL
retain the generic nonzero-exit failure.

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
  owned, has additional or writable access rules, or otherwise cannot prove the
  required protected state
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

#### Scenario: Updated bundle reuses an earlier extraction path

- **WHEN** a producer-created bundle with a different verified manifest is
  freshly extracted into an empty ordinary directory whose normalized absolute
  path was used by an earlier successful installation
- **THEN** setup selects a distinct protected runtime target and does not read,
  modify, reuse, repair, or delete the earlier protected runtime

#### Scenario: Exact bundle installation is repeated

- **WHEN** the same verified bundle manifest is installed again from the same
  normalized absolute extraction path and its protected target already exists
- **THEN** setup stops before Python execution and does not repair, reuse, or
  delete the target

#### Scenario: Existing installation tree is overwritten

- **WHEN** a new bundle is copied over a populated installation tree containing
  files outside its verified inventory
- **THEN** bootstrap rejects the unmanifested content before elevation rather
  than treating the tree as a fresh upgrade

#### Scenario: Elevated runtime construction fails with a valid diagnostic

- **WHEN** the elevated child fails and leaves a nonce-matching diagnostic that
  passes the protected runtime-control identity and access checks
- **THEN** the parent reports the controlled specific reason, remains failed,
  and does not use the diagnostic for any execution decision

#### Scenario: Elevated runtime diagnostic is unavailable or untrusted

- **WHEN** the elevated child returns nonzero and its diagnostic is missing,
  malformed, mismatched, linked, or not protected by the expected identity and
  access rules
- **THEN** the parent reports the generic nonzero-exit failure and does not
  weaken or retry the failed operation

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
The project SHALL declare the setuptools PEP 660 build backend so editable
metadata and wheel construction use pip/setuptools temporary storage and do
not require mutation of the protected source snapshot.
Missing or incompatible artifacts MUST fail without URL or index fallback.

#### Scenario: Complete wheelhouse

- **WHEN** all compatible dependency and build wheels are present
- **THEN** the repository-local environment is populated and editable
  dicomxphits installation completes without network access

#### Scenario: Protected source is read-only

- **WHEN** editable installation uses the protected source snapshot
- **THEN** build metadata is created outside that source tree and installation
  completes without adding or changing a protected source entry

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

### Requirement: Verified Offline Uninstallation

Each produced Windows offline bundle SHALL include an authenticated
`uninstall_offline.cmd` normal entry point and authenticated uninstall helper.
The entry point MUST use only the absolute Windows system PowerShell and MUST
verify and read-lock its checksum inventory, manifest, entry point, lock helper,
and uninstall helper before executing uninstall logic or requesting elevation.
It SHALL require explicit user confirmation and UAC approval before deletion.

The uninstaller MUST derive the exact protected runtime identity from the
normalized current bundle root and verified manifest SHA-256. It MUST validate
the matching protected receipt's identity schema, bundle root, runtime root,
protected source root, manifest digest, installing-user SID, ordinary-file
status, owner, and exact ACL. It MUST NOT enumerate candidate runtime IDs,
infer identity from existing runtime bytes, or accept another installation's
receipt.

Before any deletion, the non-elevated and elevated stages MUST reject an active
process associated with the selected GUI, `.venv`, protected runtime,
installer, or scientific execution. They MUST reject any reparse point in a
target or bounded ancestry, any modified authenticated bundle payload, and any
path below the extraction root that is neither an authenticated payload nor an
explicitly documented installer-generated path. The generated-path allowlist
MUST be closed and MUST NOT include arbitrary globs, case folders, DICOM,
scientific results, external tools, or user-selected paths.

Immediately before mutation, the elevated finalizer MUST open every existing
exact deletion target with Windows `DELETE` access and read/write/delete
sharing and retain those handles through exact target removal. If any target
cannot be opened, including an extraction root retained as a terminal's current
directory, uninstallation MUST stop before deleting any target and identify
that the installation remains in use.

After every pre-deletion check succeeds, the elevated cleanup SHALL remove only
the exact extraction root and its installer-generated `.venv`, launchers and
logs, the exact protected runtime and source snapshot, its matching receipt and
Windows Installer log, and its bounded cleanup staging. It MUST NOT recursively
delete a shared product parent, another runtime ID, a sibling directory, a case
folder, an external tool, or per-user GUI settings. Successful uninstallation
SHALL perform a final elevated absence check for every installation-owned
target. A partial failure SHALL remain failed and report every exact remaining
installation-owned target without guessing, broadening, or automatically
repairing the target set.

#### Scenario: User cancels verified uninstallation

- **WHEN** the user does not explicitly confirm deletion or denies the
  administrator prompt
- **THEN** uninstallation stops without deleting or changing installation
  content

#### Scenario: Exact installed bundle is safely removed

- **WHEN** the entry point and helper are authenticated, the protected receipt
  exactly binds the normalized root and manifest, no associated process is
  active, every target is ordinary and expected, and the user confirms UAC
- **THEN** uninstallation removes and verifies absence of only that extraction
  root, its generated local environment and logs, its exact protected runtime
  and control files, and its bounded cleanup staging

#### Scenario: Another installation is present

- **WHEN** another protected runtime ID, sibling extracted bundle, case folder,
  external tool, or per-user GUI settings exist
- **THEN** successful uninstallation leaves every such non-target path
  unchanged

#### Scenario: Installation contains unknown or modified content

- **WHEN** an authenticated payload is modified or the extraction root contains
  a path outside the authenticated inventory and closed generated-path allowlist
- **THEN** uninstallation stops before every deletion and identifies the
  refusing path so the user can preserve or remove it explicitly

#### Scenario: Uninstall target crosses a reparse point

- **WHEN** an extraction, runtime, receipt, log, cleanup-staging target, or its
  bounded ancestry contains a symbolic link, junction, mount point, or other
  reparse point
- **THEN** uninstallation stops before every deletion and does not follow or
  remove the redirected target

#### Scenario: Associated process remains active

- **WHEN** the selected GUI, `.venv` Python, protected runtime Python,
  installer, or scientific process associated with the installation remains
  active
- **THEN** uninstallation stops before every deletion and identifies that the
  process must be closed

#### Scenario: Exact target is held without delete sharing

- **WHEN** a terminal, File Explorer window, editor, or other process retains
  an exact uninstall target without allowing Windows delete sharing
- **THEN** uninstallation stops before every deletion, preserves all exact
  targets, and instructs the user to close processes using the installation

#### Scenario: Protected receipt does not identify this installation

- **WHEN** the receipt is missing, malformed, linked, incorrectly protected,
  or does not exactly match the normalized bundle root, manifest digest,
  runtime identity, and installing-user SID
- **THEN** uninstallation stops before every deletion and does not search for,
  infer, or remove another protected runtime

#### Scenario: Cleanup is only partially successful

- **WHEN** an operating-system failure prevents one or more exact targets from
  being removed after mutation has begun
- **THEN** uninstallation remains failed, reports each exact remaining
  installation-owned path, and does not widen the target set or claim complete
  removal

#### Scenario: Per-user settings remain after uninstall

- **WHEN** verified uninstallation succeeds and per-user GUI settings exist
- **THEN** those settings remain unchanged and documentation identifies their
  separate exact optional cleanup path

### Requirement: Observable Detached Uninstall Completion

English and Japanese offline-installation documentation SHALL state that the
verified parent's `cleanup scheduled` message and return of control to the
calling terminal indicate an intermediate handoff to the detached elevated
finalizer, not completed removal and not failure. The documentation SHALL
instruct the operator to allow that finalizer to reach a terminal outcome and
MUST NOT advise rerunning uninstall or manually deleting targets while cleanup
is still in progress.

The documentation SHALL identify the exact protected `failure.json` message
`Final cleanup staging removal is pending.` as a pending sentinel written after
the installation-owned targets pass their absence check and before the child
removes bounded cleanup staging. Retained staging with that exact sentinel MUST
remain classified as in progress, not failed. Successful completion SHALL mean
that the bounded cleanup staging also disappears. Failed completion SHALL mean
that retained bounded cleanup staging contains a different error message with
the exact remaining installation-owned paths. A missing, unreadable, malformed,
or non-progressing pending report SHALL be classified as indeterminate and
preserved for investigation without rerunning uninstall, manually deleting
targets, or broadening cleanup. Observation of the extracted bundle immediately
after the parent returns MUST NOT by itself be described as uninstall failure.

#### Scenario: Cleanup is still in progress after prompt return

- **WHEN** the verified parent reports that cleanup was scheduled and returns
  control while the extracted installation still exists
- **THEN** documentation identifies that state as detached cleanup in progress
  and instructs the operator to wait rather than retry or delete targets

#### Scenario: Detached cleanup succeeds

- **WHEN** the detached finalizer removes every exact installation-owned target,
  verifies their absence, and its child removes bounded cleanup staging
- **THEN** documentation identifies the uninstall as successfully completed

#### Scenario: Cleanup staging self-removal is pending

- **WHEN** installation-owned targets are absent but retained cleanup staging
  contains the exact `Final cleanup staging removal is pending.` message
- **THEN** documentation identifies cleanup as still in progress and does not
  describe the pending report as terminal failure

#### Scenario: Detached cleanup fails

- **WHEN** the detached cleanup cannot remove one or more exact targets and
  retains bounded cleanup staging after replacing the pending sentinel with a
  different error message
- **THEN** documentation identifies the uninstall as failed and directs the
  operator to the exact remaining-path evidence without broadening cleanup

#### Scenario: Cleanup outcome is indeterminate

- **WHEN** retained cleanup staging has no readable well-formed report or its
  pending sentinel does not progress to disappearance or a different error
- **THEN** documentation identifies neither success nor terminal failure and
  instructs the operator to preserve evidence without retry or manual deletion
