# Change: Clarify Detached Uninstall Completion

## Why

The verified Windows offline uninstaller must return from its authenticated
parent before the detached elevated finalizer can release the parent's bundle
locks and remove the exact extracted installation. Consequently, the command
can report that cleanup was scheduled and return control to the terminal while
the extracted folder still exists for a short interval.

Windows 11 acceptance exposed two superficially similar but materially
different outcomes. An earlier artifact had a real bootstrap caller-guard
defect and correctly did not schedule deletion. After that defect was fixed,
the replacement artifact reported scheduled cleanup and returned while the
folder was still present, which was initially mistaken for the same failure;
the detached finalizer then removed the exact bundle, protected runtime,
receipt, Windows Installer log, and cleanup staging successfully. The public
contract and operator instructions do not distinguish those states explicitly
enough.

## What Changes

- Define the return of the verified parent after a `cleanup scheduled` message
  as an intermediate state, not proof of either success or failure.
- Require English and Japanese offline-installation documentation to tell the
  operator to wait for the detached finalizer rather than rerun uninstall or
  manually delete an installation that is still being finalized.
- Define successful completion by the finalizer's verified absence of every
  exact installation-owned target and disappearance of its bounded cleanup
  staging.
- Define failed completion by retained bounded cleanup staging containing the
  reported `failure.json` with a non-pending error and exact remaining-path
  evidence.
- Distinguish the exact `Final cleanup staging removal is pending.` sentinel
  from terminal failure, and classify a missing, malformed, unreadable, or
  non-progressing pending report as indeterminate evidence to preserve.
- Record the Windows 11 acceptance observations and the distinction between a
  pre-scheduling refusal and post-scheduling finalizer progress in the
  development handoff so future release work does not repeat the diagnosis.
- Record that an offline ZIP built before this indexed documentation and
  specification change is a pre-change artifact and must be regenerated and
  revalidated from the eventual merged HEAD before release.
- Preserve the current uninstall implementation, deletion target set, security
  checks, public physics, DICOM meaning, external-tool boundary, and protected
  data boundary.

## Impact

- Affected specification:
  `openspec/specs/windows-offline-installation/spec.md`
- Proposed delta:
  `specs/windows-offline-installation/spec.md`
- Affected documentation:
  - `docs/windows-offline-installation.md`
  - `docs/windows-offline-installation.ja.md`
  - `docs/development-handoff-2026-08-15.md`
- Runtime behavior is not changed by this proposal, and the existing ignored
  local ZIP is not modified as part of this change. Because the affected
  documents and specification are indexed bundle sources, a later release ZIP
  must be regenerated and revalidated from the eventual merged HEAD.
- Validation uses only repository tests and synthetic or mock inputs; it does
  not run PHITS-related tools or inspect real DICOM or calculation results.
