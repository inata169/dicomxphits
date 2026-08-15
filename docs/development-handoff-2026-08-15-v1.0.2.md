# Development handoff - 2026-08-15 v1.0.2 release closeout

This document is the final same-day closeout for the v1.0.2 development and
release session. It supersedes the restart and future-release instructions in
the earlier
[`development-handoff-2026-08-15.md`](development-handoff-2026-08-15.md),
which remains a historical checkpoint from before the pull requests and
release were completed.

`dicomxphits` remains education and research software for the documented
fixed-field 3D-CRT workflow. Nothing in this closeout establishes clinical
commissioning, patient QA, vendor certification, or general dose accuracy.

## Final repository and GitHub state

- Final release commit: `efb0dace568fbcb12019f3d320a468dcfb446e34`.
- `main` and `origin/main` matched that commit at closeout.
- Annotated tag `v1.0.2` dereferences to that exact commit.
- [GitHub Release v1.0.2](https://github.com/inata169/dicomxphits/releases/tag/v1.0.2)
  is published, is the latest release, and is neither a draft nor a
  prerelease.
- Tags `v1.0.1` and `v1.0.0` were not moved or replaced.
- The release work was reviewed and merged in order through pull requests
  [#38](https://github.com/inata169/dicomxphits/pull/38),
  [#39](https://github.com/inata169/dicomxphits/pull/39),
  [#40](https://github.com/inata169/dicomxphits/pull/40),
  [#41](https://github.com/inata169/dicomxphits/pull/41), and
  [#42](https://github.com/inata169/dicomxphits/pull/42).
- Their merge commits are `72605fe`, `18495fe`, `942194d`, `1480066`, and
  `efb0dac`, respectively. Their temporary remote feature branches were
  deleted after merge.
- No active OpenSpec change remains.

## Completed v1.0.2 scope

The release integrates the fixed Elekta Precise nominal 6 MV guard and GUI
presentation, Help and Web site actions, author and version presentation,
minimum-window scrolling, five-page primary-action reachability, and the
compact Activity log. It preserves the accepted non-zero-gantry geometry
correction, course-dose contract, recovery behavior, GUI stage gating, and
fixed-field scope.

The Windows offline lifecycle now stores GUI settings outside the protected
runtime, supports verified bundle upgrades and exact-installation uninstall,
preflights Windows directory locks before mutation, closes the generated
environment inventory, and uses identity-bound detached cleanup staging. The
documentation and accepted OpenSpec contract distinguish scheduled cleanup,
the exact pending sentinel, final success, terminal failure, and indeterminate
retained evidence.

No release work changed the supported physics, spectrum bytes, effective
aperture boundary, gantry convention, DICOM coordinates or meaning, dose, MU,
normalization, or treatment-technique scope.

## Human Windows acceptance

The primary user reported successful Windows installation and GUI startup from
the final offline ZIP. The fixed 6 MV presentation, Help menu, Web site action,
author and version, minimum-window scrolling, and all five primary workflow
actions were accepted.

The user also reported completion of the bounded non-patient workflow from
CT2PHITS through RTDOSE and separately reported no abnormal dose distribution
or absolute dose in the external GPR comparison. The agent did not execute or
inspect PHITS, Sumtally, phits2dicom, GPR, real DICOM, or real calculation
results.

For the final release candidate, the user reported that installation and GUI
startup succeeded and that verified uninstall completed when `uninstall.cmd`
was launched from Windows Explorer. This is human-reported operational
acceptance, not clinical validation.

## Published Windows offline artifact

The custom GitHub Release asset is:

```text
dicomxphits-offline-win64-1.0.2.zip
SHA-256 6b957e1ff236ef787d791db0921edabd18ea459a27fbe745f7c2d98979e86217
size 36,937,317 bytes
manifest source HEAD efb0dace568fbcb12019f3d320a468dcfb446e34
ZIP files 241
manifest file records 239
public source files 231
validated wheels 5
```

GitHub reported the asset state as `uploaded` and the same SHA-256 digest and
size as the independently validated local file. The ZIP was reopened without
extracting it and passed duplicate-name, CRC, complete inventory, per-file
size and SHA-256, manifest membership, and `SHA256SUMS.txt` binding checks.
The authenticated CPython 3.12.10, Tcl/Tk, and NuGet source checks passed during
the build.

## Automated validation record

Before the release tag, the exact reviewed source tree passed:

- focused offline bundle, installer, and uninstaller tests: 86 passed and
  1 skipped;
- full public pytest: 843 passed and 11 skipped;
- Python source compilation;
- public-tree verification with 231 tracked files;
- all 10 current OpenSpec specifications under strict validation;
- the relevant archived OpenSpec changes under strict validation; and
- Git diff and status checks.

The release-closeout documentation branch was then revalidated with 3 focused
release-evidence tests, Python source compilation, the full public suite
(843 passed and 11 skipped), a 232-file public-tree audit, all 10 current
OpenSpec specifications, and the four v1.0.2-related archives. OpenSpec CLI
1.6.0 does not expose an aggregate `--archived` option, so those archives were
validated as active changes in a temporary isolated OpenSpec root; all four
passed and the temporary root was removed.

The aggregate archived OpenSpec validation still has one known, unrelated
historical failure: archive `2026-08-07-add-windows-offline-installer` contains
one unchecked historical task. It was not changed merely to make the aggregate
count green. The v1.0.2 OpenSpec archives themselves pass.

## OpenSpec closeout

The accepted behavior is promoted into the current specifications. The
v1.0.2-related archived changes are:

- `2026-08-15-clarify-offline-bundle-root-protection`;
- `2026-08-15-support-offline-bundle-upgrades`;
- `2026-08-15-integrate-safety-ui`; and
- `2026-08-15-clarify-detached-uninstall-completion`.

The current normative contracts remain under `openspec/specs/`. This release
closeout changes project and release records only; it does not add or modify a
normative requirement.

## Stopping boundary

The v1.0.2 development, review, merge, tag, release, asset upload, and readback
are complete. There is no known merge-blocking defect and no required v1.0.2
release action remains.

Do not create a follow-up capability, change public physics or DICOM behavior,
modify tags, replace the release asset, or run real external tools without a
new explicit human-approved task. The unapproved
`add-rtdose-coordinate-output-choice` proposal was not recreated and remains
outside the repository.

At the next development session, begin with read-only repository and GitHub
state checks. Treat `v1.0.2` at
`efb0dace568fbcb12019f3d320a468dcfb446e34` as the release baseline unless a
later reviewed pull request has been explicitly approved and merged.
