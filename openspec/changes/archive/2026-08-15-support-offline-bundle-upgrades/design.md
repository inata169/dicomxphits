# Design: Content-Bound Offline Installation Identity

## Observed Failure

The elevated protected-runtime leaf is currently the SHA-256 of the normalized
absolute bundle root alone. The reproduced path identity matched the retained
runtime referenced by the earlier installed GUI. A freshly extracted updated
bundle at that same absolute path therefore reached the existing-runtime stop,
while the parent displayed only `Protected runtime construction failed with
exit code 1`.

This is not the earlier bundle-file sharing violation. Initial manifest and
SHA-256 verification, bundle path locking, and elevation all completed before
the current failure.

## Identity Contract

The bootstrap already authenticates `bundle-manifest.json` and retains its
SHA-256 in the locked checksum inventory. That digest covers the manifest,
which identifies the exact source HEAD and inventories every protected payload.
The verified parent will pass this digest to the elevated stage as explicit
verified state alongside the bundle root, stage nonce, and installing-user SID.

The protected runtime ID will be the lowercase SHA-256 of an unambiguous,
versioned byte encoding containing:

1. an identity-schema marker;
2. the normalized uppercase absolute bundle root; and
3. the verified lowercase manifest SHA-256.

The elevated child will reject a missing or malformed manifest digest and will
recompute the same runtime ID from the passed verified state. A changed
authenticated manifest at the same root therefore selects a new leaf. The same
manifest at the same root selects the same leaf and preserves the current
one-entry fail-closed behavior.

The identity is a collision-resistant namespace selector, not a substitute for
the existing manifest, signature, protected ACL, source-copy, receipt, complete
inventory, or retained-handle validation. All those controls remain required.

## Fresh Extraction Boundary

This change supports a new producer-created ZIP extracted into an empty normal
directory whose absolute path was used by an older installation. It does not
support copying new payloads over a populated installed tree. The bootstrap
continues to reject unmanifested `.venv`, logs, launchers, or other leftover
files before elevation.

The prior protected runtime remains in `ProgramData` because an existing
environment may still reference it as its base interpreter. Cleanup remains a
separate, explicit administrator operation after the corresponding installation
is confirmed abandoned.

## Elevated Failure Diagnostic

The elevated child will record a bounded diagnostic for its verified-stage
nonce below the protected runtime-control parent. The record will contain only
the nonce, stable failure category, and controlled exception message. It will
receive the same protected owner and exact ACL used for runtime control files.

On a nonzero child exit, the parent may validate and read that protected record
only to improve the displayed error. It must not use the record to select a
path, skip a check, accept a runtime, or authorize Python execution. A missing,
malformed, mismatched, linked, or incorrectly protected diagnostic falls back
to the existing generic exit-code message. Successful construction removes no
historical runtime content and leaves no failure diagnostic for that stage.

## Failure Atomicity

Existing runtime and control paths remain immutable. The installer will not
delete a collided target or retry with a random name. A construction failure
may leave a protected incomplete target exactly as today; repeating that exact
bundle remains fail closed and requires an explicit administrator cleanup or a
new fresh path. A different authenticated bundle can use its different
content-bound identity without touching that failed target.

## Verified Uninstall Entry Point

Every produced offline bundle will contain `uninstall_offline.cmd` and a
PowerShell uninstall helper in the authenticated manifest and checksum
inventory. The normal uninstall entry point will use only the absolute Windows
system PowerShell. Before requesting elevation it will verify and read-lock the
checksum inventory, manifest, uninstall entry point, required lock helper, and
uninstall helper. It will not execute a helper merely because it is present in
the writable extraction directory.

The uninstaller will compute the content-bound runtime ID from the normalized
current bundle root and verified manifest SHA-256, locate only that ID's
protected receipt, and validate the receipt's owner, exact ACL, ordinary-file
identity, bundle root, runtime root, protected source root, installing-user SID,
manifest digest, and identity-schema version. It will not search for candidate
runtimes, infer identity from directory contents, or accept a receipt belonging
to another bundle root or user.

Uninstallation requires an explicit local confirmation before UAC. Denial or
failure to obtain administrator authority makes no change.

## Pre-Deletion Safety Gate

Before any deletion, both the non-elevated and elevated stages will establish
the exact target set and reject:

- a GUI, `.venv` Python, protected runtime Python, installer, or scientific
  process associated with the selected installation that is still running;
- any exact deletion target that cannot first be opened with `DELETE` access
  and read/write/delete sharing, including an extraction root retained as a
  terminal's current directory;
- any symbolic link, junction, mount point, or other reparse point in a target
  or its bounded path ancestry;
- a missing, mismatched, malformed, incorrectly protected, or ambiguous
  protected receipt;
- any bundle payload whose current bytes no longer match the authenticated
  manifest, except documented installer-generated paths; or
- any path below the extraction root that is neither an authenticated bundle
  payload nor a documented installer-generated path.

The generated-path allowlist will be closed and structural. It may include the
repository-local `.venv`, installer log, and generated launcher artifacts. It
will not include arbitrary glob patterns, case folders, DICOM, scientific
outputs, or user-selected paths. Every generated directory will be recursively
checked for reparse points before deletion. Users must move intentional edits
or additional files elsewhere before retrying an uninstall that refuses them.

## Bounded Elevated Cleanup

The verified parent will stage only the authenticated uninstall logic and
nonce-bound exact target description into a freshly created protected cleanup
directory below the product's `ProgramData` boundary. The elevated Windows
system PowerShell will revalidate that staging, receipt, runtime identity,
target ancestry, process gate, and extraction-root inventory before mutation.

After all gates pass, cleanup will remove:

1. the exact installation root, including its generated `.venv`, launchers,
   installer log, and authenticated bundle payloads;
2. the exact content-bound protected runtime and source snapshot;
3. the matching receipt and Windows Installer log; and
4. its own bounded cleanup staging through a detached, exact-path finalizer.

The helper will never recursively delete the product root, the
`offline-runtimes` parent, a wildcard-selected path, another runtime ID, a case
folder, an external tool, or per-user GUI settings. Empty shared product
parents may remain because they are common administrative boundaries rather
than installation-owned leaves.

Cross-volume deletion cannot be transactional. The implementation will order
and verify steps, retry only bounded sharing failures, report every exact
remaining installation-owned path on partial failure, and never broaden the
target set during recovery. A successful result requires a final elevated
absence check for every installation-owned target and cleanup staging path.

Windows 11 acceptance exposed one process-lifetime defect in the first
implementation: `Start-Process -Wait` waited for the elevated stage's detached
finalizer as well as the direct stage process, while that finalizer correctly
waited for the verified parent to release its bundle locks. The resulting
circular wait timed out before any deletion. The parent therefore starts the
same verified elevated stage with `-PassThru` and calls the returned process's
`.WaitForExit()` method, which waits for only that direct process. The detached
finalizer can then outlive the stage, observe the parent exit, and perform the
already specified revalidation and exact cleanup.

A subsequent Windows 11 uninstall exposed a separate sharing boundary: a
long-lived Windows Terminal opened with the extraction root as its working
directory could retain that directory without appearing as an executable from
the installation. The first recursive removal deleted the root's contents and
then failed to remove the held root. The finalizer now opens every existing
exact deletion target with `DELETE` access while allowing read, write, and
delete sharing before any mutation. A conflicting handle therefore refuses the
entire cleanup before deletion. The successful preflight handles remain open
through exact target removal, preventing a new incompatible handle from being
introduced between the check and mutation.

Per-user GUI settings below `LOCALAPPDATA` are intentionally retained because
they may be shared by a later installation and are user preferences rather
than installation-owned runtime content. Documentation will identify their
separate exact optional cleanup path without deleting it automatically.

## Validation Strategy

Synthetic Windows tests will prove that:

- equal normalized roots and equal manifest digests produce equal IDs;
- equal roots and different manifest digests produce different IDs;
- case-only path differences normalize to the same ID;
- a missing or malformed verified manifest digest is rejected before protected
  runtime construction;
- an exact-repeat collision remains fail closed without mutation;
- a changed bundle at the same fresh path does not select or modify the prior
  protected target;
- a protected, nonce-bound child failure is reported by the parent;
- an untrusted or invalid diagnostic cannot affect execution and degrades to
  the generic failure message; and
- uninstall identity is bound to the exact normalized root and manifest;
- unknown, modified, linked, redirected, ambiguous, or active installation
  state prevents every deletion;
- a synthetic delete-sharing conflict on the extraction root refuses cleanup
  before every exact target and succeeds after the conflicting handle closes;
- a synthetic successful uninstall removes only its exact extraction root,
  protected runtime, receipt, MSI log, and cleanup staging;
- other runtime IDs, sibling directories, cases, external tools, and per-user
  settings remain unchanged; and
- existing bundle locks, signatures, ACLs, complete runtime inventory, host
  Python exclusion, no-index installation, and import checks still pass.

No test will run PHITS, Sumtally, phits2dicom, GPR, real DICOM, or real
calculation results.

## Release Boundary

This change does not update `__version__`, create or modify a Git tag, publish
an artifact, or create a GitHub release. A v1.0.2 decision can be made only
after implementation, automated validation, a newly built exact-HEAD ZIP, and
human Windows installation and GUI acceptance succeed.
