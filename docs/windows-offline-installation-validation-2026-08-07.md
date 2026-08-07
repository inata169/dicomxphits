# Windows Offline Installation Validation - 2026-08-07

This dated record summarizes bounded, human-reported Windows checks of the
offline installation workflow. It is installation evidence only. It is not
clinical validation, commissioning, patient QA, vendor certification, or a
claim that dicomxphits is suitable for clinical use.

For Japanese, see the
[Japanese validation record](windows-offline-installation-validation-2026-08-07.ja.md).

## Scope and authorization

The human first tested on a lower-importance offline Windows computer before
using an offline workstation associated with a TPS. The human reported that
facility IT, medical-information personnel, the TPS vendor, and the responsible
local authority had approved installing Python and the separately managed
external tools on that workstation. No approval evidence, facility identity,
workstation path, patient data, DICOM, external-tool payload, or calculation
output is stored in this repository.

The dicomxphits bundle did not install Visual Studio, PHITS, RT-PHITS,
phits2dicom, or GPR-comparing and did not start a PHITS calculation.

## Observed sequence and corrections

The first offline host had no CPython 3.12. The bundled official Python
3.12.10 installer completed, but a pre-correction CMD failed to rediscover the
new current-user interpreter. The standard-library helper was then run
directly and completed bundle verification, `.venv` creation, binary-wheel-only
installation, editable installation, and import verification. Its supplied log
recorded Python 3.12.10, NumPy 2.5.1, pydicom 3.0.2, and dicomxphits 1.0.1.

Two further CMD boundary defects were identified during the staged human test:

- a trailing directory separator could escape the closing quote of the bundle
  root passed to Python, leaving an extra `"` in the log path; and
- on a host with the Python Launcher but no CPython 3.12, launcher output
  `Python 3.12 not found!` could be captured as though it were an executable.

The corrections normalize the bundle root without a trailing separator,
directly validate the normal current-user Python location, and accept captured
launcher/PATH output only when it names an existing executable. Windows
`cmd.exe` regression tests cover the Unicode/space-path argument and the
launcher-not-found message.

## Final human-reported result

The final corrected artifact exercised by the human was:

```text
dicomxphits-offline-win64-1.0.1.zip
SHA-256: 143603e20d90d839cb2da775497d3d6f50d99753eff35f213ad14f30d0f83675
Size: 42,892,882 bytes
```

The human reported that `install_offline.cmd` then completed successfully on
the authorized offline workstation. The agent did not access that workstation
or independently inspect its final log. The report therefore supports only
the bounded conclusion that the corrected one-entry installation completed in
the manually exercised environment.

The producer-side checks for that artifact recorded a valid Python Software
Foundation Authenticode signature, 158 manifest-protected files, exact NumPy
`cp312-cp312-win_amd64` compatibility, five required wheels, and no named
forbidden external-tool payloads.

## Automated evidence

After the final launcher-output correction, the local checks reported:

```text
Focused Windows offline-install tests: 13 passed
Full public suite: 614 passed, 1 skipped
Python compileall: passed
Windows offline OpenSpec strict validation: passed
Public-tree audit: 152 tracked files passed
Git diff checks: passed
```

The full OpenSpec tree also retained a pre-existing unrelated strict-format
failure in `rtdose-dicom-semantics`; the Windows offline installation
specification itself passed strict validation.

## Evidence boundary

- No patient or non-public DICOM was used or recorded in this validation
  record.
- No PHITS calculation, dose comparison, physics result, or clinical workflow
  was validated by the installer check.
- The public non-patient-phantom, education/research, fixed-field 3D-CRT safety
  boundary remains unchanged.
- The artifact SHA-256 above identifies the exact human-reported bundle. A
  later rebuild, even with documentation-only changes, has a different ZIP
  digest and must be identified by its own producer output.
