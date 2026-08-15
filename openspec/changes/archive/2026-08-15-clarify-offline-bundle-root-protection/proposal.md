# Change: Clarify Offline Bundle Root Protection

## Why

The accepted Windows bootstrap cannot always acquire a no-delete-sharing
directory handle for the extracted bundle root when the calling PowerShell
retains that directory as its current directory. The implemented and tested
design instead protects the root through an authenticated, rehashed, strict
read handle on `install_offline.cmd`, while retaining no-delete-sharing handles
for every required child directory in the payload parent chains.

The current specification refers generically to every required bundle
directory. That wording can be read as requiring the root directory handle
that the accepted Windows launch path cannot acquire. The contract must state
the two complementary protection mechanisms explicitly without weakening
fail-closed behavior.

## What Changes

- Require the bootstrap to retain an authenticated and rehashed strict read
  handle on the manifest-listed `install_offline.cmd` to protect the bundle
  root.
- Define required no-delete-sharing directory handles as the required child
  directories below the bundle root in inventoried payload parent chains.
- Require installation to stop before elevation if either the root-file
  protection or any required child-directory protection cannot be acquired or
  retained.
- Add scenarios for a caller that retains the bundle root as its current
  directory and for failure to acquire the root-file protection.
- Preserve the current runtime implementation, public physics, DICOM meaning,
  offline ownership boundaries, and protected-data boundaries.

## Impact

- Affected specification:
  `openspec/specs/windows-offline-installation/spec.md`
- Proposed delta:
  `specs/windows-offline-installation/spec.md`
- Runtime behavior is not changed by this proposal.
- Existing synthetic Windows tests and completed human Windows acceptance are
  evidence for the already implemented protection design; no real external
  tool output is part of this change.
