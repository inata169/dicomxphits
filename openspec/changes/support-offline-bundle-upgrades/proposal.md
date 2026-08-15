# Support Offline Bundle Upgrades at a Reused Local Path

## Why

The protected Windows offline runtime identity is currently derived only from
the normalized absolute extraction path. After one bundle has installed from a
path, a later authenticated bundle freshly extracted at that same path maps to
the retained protected runtime from the earlier bundle and fails during the
elevated stage. The non-elevated installer then reports only exit code 1, so the
user cannot distinguish this deterministic identity collision from another
runtime-construction failure.

The protected runtime must remain immutable, must not be inferred from existing
bytes, and must not be repaired or deleted automatically. A new authenticated
bundle nevertheless needs a distinct installation identity even when the user
reuses the same ordinary local extraction path after replacing its contents
with a fresh extraction.

## What Changes

- Derive the protected runtime identity from both the normalized absolute
  bundle root and the already verified bundle-manifest SHA-256.
- Give different authenticated bundle contents distinct protected runtime
  targets even when they are freshly extracted at the same absolute path.
- Keep an exact repeat of the same bundle at the same path deterministic and
  fail closed when its protected target already exists.
- Do not reuse, repair, replace, or automatically remove any existing
  protected runtime, receipt, log, or source snapshot.
- Preserve a specific, human-readable elevated-stage failure reason for the
  non-elevated installer while treating that diagnostic as display-only input
  that cannot authorize execution or weaken verification.
- Include a verified offline uninstaller that identifies its own protected
  runtime through the authenticated receipt and removes only installation-owned
  content after explicit user confirmation and UAC approval.
- Make uninstallation fail before deletion when a related process is active,
  an expected path is linked or redirected, the installation identity is not
  exact, or the extracted root contains unknown or modified user content.
- Remove the exact protected runtime, receipt, Windows Installer log, local
  `.venv`, generated launchers and logs, authenticated extracted bundle, and
  bounded cleanup staging on successful uninstallation without touching case
  folders, external tools, other installations, or per-user GUI settings.
- Add synthetic Windows regressions for changed-bundle identity, exact-repeat
  rejection, protected-runtime preservation, elevated error reporting, exact
  uninstall targeting, unknown-content refusal, and successful cleanup.
- Update the English and Japanese offline installation guidance to distinguish
  a fresh extraction at a reused absolute path from overwriting a populated
  installation directory.

## Impact

- Affected capability: `windows-offline-installation`
- Affected runtime:
  - `install_offline.cmd`
  - `tools/install_offline_verified.ps1`
  - new `uninstall_offline.cmd`
  - new `tools/uninstall_offline_verified.ps1`
  - producer bundle inventory and required-payload declarations
- Affected tests: `tests/test_offline_install.py`
- Affected documentation:
  - `docs/windows-offline-installation.md`
  - `docs/windows-offline-installation.ja.md`
- Existing protected runtimes remain untouched and may continue to serve their
  existing installed virtual environments.
- Successful uninstallation removes only the runtime bound to that exact
  installed bundle and refuses ambiguous or partially identifiable targets.
- The current fixed-6-MV GUI integration and settings correction remain
  unchanged except that a later exact-HEAD ZIP can install from a previously
  used absolute extraction path after a fresh extraction.
- Public physics, DICOM meaning, coordinates, dose, MU, normalization, machine
  model, GUI stage gating, external-tool execution, package version metadata,
  tags, and release state are unchanged.
- Automated validation uses only synthetic paths, bundles, subprocesses, and
  protected test directories. It does not run PHITS-related tools or read real
  DICOM or calculation results.

## Approval Status

The primary user approved creation and strict validation of this proposal on
2026-08-15. Runtime implementation remains pending explicit approval of this
completed proposal and its delta specification.
