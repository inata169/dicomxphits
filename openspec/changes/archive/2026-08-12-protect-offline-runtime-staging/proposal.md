# Protect Offline Runtime Staging

## Why

The authenticated runtime currently retains non-write-sharing handles for
every validated file, but its final recursive inventory is only a snapshot.
Another process that can write the bundle-local `.python-runtime` directories
can add a new entry after that snapshot without modifying any locked file. In
particular, an added `python312._pth` can change CPython startup paths before
`-I`, `-S`, the version probe, or the verified helper can establish policy.

Windows directory R/RH oplocks do not close this gap because directory-content
changes may proceed without an oplock-break acknowledgment. A normal
same-user DACL is also insufficient because an object's owner otherwise has
implicit `WRITE_DAC`. The runtime therefore needs an operating-system access
boundary that a concurrent non-elevated process cannot rewrite.

## What Changes

- Keep `install_offline.cmd` as the normal entry point and complete the current
  bundle verification and read locking before requesting UAC elevation.
- Use elevation only to verify runtime sources and construct protected storage.
  The original non-elevated stage revalidates the protected receipt and runtime
  before executing Python, the helper, or pip.
- Construct the authenticated runtime in a fresh installation-specific
  directory below a protected `%ProgramData%` root instead of in the writable
  extracted bundle.
- Create and validate a protected, non-inheriting runtime ACL that grants
  mutation only to `SYSTEM` and elevated Administrators, grants the installing
  user read/execute access, and uses the Windows `OWNER RIGHTS` SID so object
  ownership does not restore implicit `WRITE_DAC` to the non-elevated user.
- Reject an existing, linked, incorrectly owned, incorrectly permissioned, or
  otherwise unverifiable protected root rather than repairing or reusing it.
- Re-run the complete inventory after the protected ACL and authenticated file
  read locks are established and before the first Python process starts.
- Retain the protected runtime because the repository-local `.venv` records it
  as its base interpreter, and document the elevation, failure, and manual
  cleanup boundary.
- Add Windows regressions proving a non-elevated same-user injection cannot add
  `python312._pth` or start the malicious marker before the verified runner.

## Impact

- Affected capability: `windows-offline-installation`
- Affected consumer: `install_offline.cmd` and
  `tools/install_offline_verified.ps1`
- Affected tests: bootstrap ordering, elevation failure, protected-directory
  identity and permissions, post-inventory injection, and the official CPython
  3.12 x64 acceptance probe
- Affected documentation: README, English and Japanese offline installation
  instructions, security regression checklist, and development handoff
- User-visible contract change: offline installation requires a UAC-approved
  administrator stage and retains an installation-specific protected runtime
  below `%ProgramData%`
- Unchanged: public physics, DICOM meaning, coordinates, dose, MU,
  normalization, machine model, field-size guard, supported treatment
  techniques, external-tool execution, and the repository-local `.venv`

## Approval Status

The primary user approved this strictly validated proposal and its runtime
implementation on 2026-08-12.
