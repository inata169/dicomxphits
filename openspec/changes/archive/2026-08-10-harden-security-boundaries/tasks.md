# Tasks

## 1. Approval

- [x] 1.1 Revalidate the three reported source-to-sink paths and existing tests.
- [x] 1.2 Inspect offline guidance, current specifications, dependency behavior,
  and the overlapping unapproved portable-recovery proposal.
- [x] 1.3 Obtain explicit human approval of this proposal and the exact root
  `SECURITY.md` draft before runtime or policy implementation.

## 2. Offline bootstrap hardening

- [x] 2.1 Replace bare-name PowerShell, Python Launcher, and Python lookup with
  trusted/validated absolute executable paths and keep executable locks through
  the verified installation child.
- [x] 2.2 Reject protected bundle reparse paths and unmanifested top-level
  executable lookalikes before running bundled code.
- [x] 2.3 Preserve checksum ordering, complete offline behavior, Python 3.12 x64,
  GUI opt-in, and quoted Unicode/space paths.
- [x] 2.4 Add static, synthetic, and Windows-native fake-executable regression
  tests.

## 3. CSV formula neutralization

- [x] 3.1 Add one common external-string CSV neutralizer without changing
  non-string values.
- [x] 3.2 Apply it to RT Plan CSV outputs without changing columns or ordinary
  BeamName values.
- [x] 3.3 Add CSV round-trip coverage for formula prefixes, controls, empty and
  Unicode/Japanese strings, quotes, commas, and embedded newlines.

## 4. Workspace output containment

- [x] 4.1 Add a shared path-component and platform-specific reparse-point guard
  with controlled user-facing errors.
- [x] 4.2 Apply guarded exclusive/atomic writes and guarded removals to existing
  workspace preparation, segment, Sumtally, and RTDOSE mutation paths.
- [x] 4.3 Add Linux symbolic-link and Windows real junction/reparse-point tests
  proving no outside create, overwrite, or delete occurs.
- [x] 4.4 Preserve successful new-workspace GUI and CLI behavior with synthetic
  workflow regression tests.

## 5. Repository and supply-chain hardening

- [x] 5.1 Add the approved root `SECURITY.md`.
- [x] 5.2 Add weekly pip and GitHub Actions Dependabot configuration.
- [x] 5.3 Set workflow `permissions: contents: read` and pin existing third-party
  actions to verified full commit SHAs with original major-version comments.
- [x] 5.4 Add reviewed runtime/test constraints and an exact hash-locked Windows
  wheel set, and make CI and offline runtime versions consistent.
- [x] 5.5 Update English/Japanese offline documentation and tests for the locked
  dependency and hardened bootstrap contracts.

## 6. Validation and completion

- [x] 6.1 Run focused security regression tests and applicable format/lint checks.
- [x] 6.2 Run compileall, the full public pytest suite, public-tree verification,
  Git diff checks, and strict OpenSpec validation.
- [x] 6.3 Run real Windows-native CMD lookup, Unicode/space, fake executable,
  symlink, junction, and reparse-point checks, or accurately record them as
  unverified with exact manual commands.
- [x] 6.4 Promote accepted deltas, archive the complete change, and strictly
  validate the resulting OpenSpec tree before completion reporting.

Windows-native execution in 6.3 remains unverified in the current WSL2
environment. Exact non-patient manual commands and pass/skip evidence to record
are in `docs/windows-security-regression-checklist.ja.md`; this is recorded as
unverified rather than inferred from Linux results.
