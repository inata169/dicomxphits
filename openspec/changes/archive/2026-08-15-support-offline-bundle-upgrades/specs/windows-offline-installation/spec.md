## MODIFIED Requirements

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

## ADDED Requirements

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
