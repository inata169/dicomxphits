# Harden Security Boundaries

## Why

Three reachable security boundaries are incomplete in the current public
repository:

- `install_offline.cmd` starts `powershell.exe`, `py.exe`, and `python.exe` by
  name, so an executable placed in the extraction/current directory can run
  before it has been authenticated or selected as an installed CPython 3.12
  interpreter.
- DICOM-originated strings such as `BeamName` are written directly to CSV and
  may be interpreted as spreadsheet formulas.
- workspace-local writers validate some lexical or resolved paths, but they do
  not consistently reject symbolic links, Windows junctions, or other reparse
  points from the case root through every output parent before creating,
  replacing, or removing an artifact.

The repository also lacks a disclosure policy and routine dependency/action
update configuration. Its CI actions use mutable major tags, and normal CI and
offline bundle preparation resolve unbounded runtime dependency versions at
different times.

## What Changes

- Bootstrap the offline installer only with an absolute Windows system
  PowerShell path, use an absolute system command processor for the verified
  child stage, and select only an absolute, signature-checked, locked CPython
  3.12 x64 executable from bounded installed locations or the just-installed
  verified Python package.
- Reject relevant bundle-root reparse points and unmanifested top-level
  executable lookalikes, and preserve checksum verification and read locks
  before any bundled executable or helper runs.
- Neutralize spreadsheet-active and control-character-leading external strings
  at the shared CSV serialization boundary while leaving non-string values and
  ordinary strings unchanged.
- Add a shared fail-closed workspace output guard that validates containment,
  rejects symbolic links, junctions, and Windows reparse points in every
  existing path component, and uses exclusive or atomic file creation for
  workspace-local writes. Apply it to existing workspace preparation, segment,
  Sumtally, and RTDOSE mutation paths without changing physics or DICOM meaning.
- Add root `SECURITY.md`, Dependabot configuration, least-privilege workflow
  permissions, and immutable full-SHA pins for the existing checkout and Python
  setup action major versions.
- Introduce reviewed runtime/test constraints and a Windows x64 offline wheel
  lock that records exact versions, filenames, and SHA-256 values. Make normal
  CI install the same pinned runtime versions used by the offline bundle, while
  retaining Python 3.12-only and no-network offline installation.
- Add synthetic cross-platform regression tests plus Windows-only tests and a
  manual Windows validation procedure for real CMD lookup behavior, junctions,
  and reparse points.

## Impact

- Affected runtime: offline bootstrap, CSV serialization, and workspace-local
  output creation/replacement/removal guards.
- Affected capabilities: `windows-offline-installation`; new capabilities
  `csv-export-security` and `workspace-output-security`.
- Affected automation and policy: `.github/workflows/ci.yml`, Dependabot,
  dependency lock inputs, and root vulnerability-reporting guidance.
- Existing normal BeamName values, CSV columns, numeric cell types, documented
  fixed-field 3D-CRT physics, DICOM semantics, and external-tool boundaries
  remain unchanged.
- The active, unapproved `support-portable-workspace-recovery` change remains
  separate and is neither implemented nor archived by this work.

## Approval Status

This proposal records the requested security remediation. Runtime, workflow,
dependency, and policy implementation remains unapproved until the human
reviews and explicitly approves this proposal and the exact `SECURITY.md` draft
in `design.md`.
