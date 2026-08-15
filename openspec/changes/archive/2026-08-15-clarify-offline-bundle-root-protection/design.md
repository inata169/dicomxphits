# Design: Offline Bundle Root Protection Contract

## Context

The offline bootstrap must prevent verified bundle content from being renamed
or replaced between verification and use. Required child directories can be
held with no-delete-sharing directory handles. On Windows, however, a parent
PowerShell whose current directory is the extracted bundle root can prevent
acquisition of that same directory handle even though launching
`install_offline.cmd` from that location is a supported user path.

The accepted implementation retains a strict read handle without delete
sharing on the authenticated and rehashed `install_offline.cmd`. That open file
prevents renaming the containing bundle root. It separately retains
no-delete-sharing handles for the required child directories in every
inventoried payload parent chain.

## Goals

- State the accepted root and child-directory protection mechanisms exactly.
- Keep failure to acquire or retain any required protection fail-closed.
- Preserve the supported current-directory PowerShell launch path.
- Avoid any runtime, physics, DICOM, dose, or external-tool behavior change.

## Non-Goals

- Changing the bootstrap implementation.
- Weakening inventory verification, rehashing, strict file locking, or child
  directory locking.
- Expanding the offline installer scope or changing installation ownership.
- Re-running or inspecting real PHITS, Sumtally, phits2dicom, GPR, DICOM, or
  calculation output.

## Decision

The bundle root protection SHALL be the retained strict read handle on the
manifest-listed `install_offline.cmd`, acquired only after authentication and
rehashing. Required directory-handle protection SHALL apply to required child
directories below the root in inventoried payload parent chains. The bootstrap
MUST stop before elevation if it cannot acquire or retain either class of
protection.

This is one combined protection invariant:

1. the strict authenticated file handle prevents bundle-root rename;
2. child-directory handles prevent payload-parent directory rename; and
3. strict read locks on verified payloads prevent replacement before use.

## Alternatives Considered

### Require a no-delete-sharing handle on the bundle root

Rejected because a legitimate parent PowerShell can retain the root as its
current directory and make that handle unavailable. Restoring this behavior
would reintroduce the Windows error that the pull request fixes.

### Skip protection when a handle is unavailable

Rejected because it weakens fail-closed behavior and permits a verification to
use race.

### Protect only the bundle root

Rejected because child payload-parent directories also require retained
identity and rename protection.

## Verification Strategy

- Strictly validate this OpenSpec change before implementation approval.
- Confirm the focused synthetic Windows tests cover root and child-directory
  rename blocking and failure behavior.
- Run the repository's required compilation, full synthetic test suite, public
  tree audit, and Git checks after promotion.
- Do not run or inspect real external tools or real calculation results.
