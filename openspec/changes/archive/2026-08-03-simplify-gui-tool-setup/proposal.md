# Simplify Guided GUI Tool Setup

## Why

The guided GUI currently exposes the PHITS root, RT-PHITS root, PHITS
executable, phits2dicom executable, and per-case CT2PHITS workspace as
independent path fields. Although stable tool paths are remembered locally,
the first setup remains difficult and a stale non-empty workspace value is not
updated when the selected RT Plan or installation root changes. This makes the
documented first CT2PHITS stage difficult to configure even for the repository
maintainer and is likely to prevent new users from reaching the existing safe
validation boundary.

The Windows PHITS installation has a standard installation root and known
subdirectories. The GUI can inspect only documented candidate paths below an
explicitly selected installation folder, validate the resulting tool profile,
and derive a new case workspace without searching the computer or executing an
external tool.

## What Changes

- Replace the primary group of independent tool-path fields with one guided
  `PHITS installation folder` selection and a visible readiness result.
- Derive the PHITS root, RT-PHITS root, PHITS executable, and phits2dicom
  executable only from a bounded list of supported relative candidates below
  that explicitly selected folder.
- Validate every derived prerequisite without launching PHITS, RT-PHITS,
  CT2PHITS, or phits2dicom, and report missing or ambiguous candidates by role.
- Keep an explicit advanced custom-layout mode for installations that do not
  match the supported standard layout; custom paths remain visible, editable,
  and subject to the same validation.
- Make the normal CT2PHITS workspace a visible, automatically derived per-case
  output path rather than a required manual path setting. Recompute it when the
  source RT Plan or effective RT-PHITS root changes and continue to reject an
  existing or repository-local output.
- Persist the selected local tool profile compatibly in the ignored GUI
  settings file while continuing not to persist case inputs, safety
  confirmation, or overwrite permission.
- Update the README and GUI guidance so the normal first-run workflow requires
  one installation-folder selection, an RT Plan, and a CT DICOM folder.

## Impact

- Affected capability: `guided-gui-workflow`
- Affected runtime: `src/dicomxphits/gui.py` and, if needed, a small
  package-local tool-profile helper
- Affected tests: synthetic path-layout, migration, validation, suggestion,
  command-construction, and GUI-state tests
- Affected documentation: README platform/setup guidance and guided workflow
  documentation
- Unchanged boundaries: fixed-field 3D-CRT physics, DICOM interpretation,
  CT2PHITS input contents, external adapter execution gates, non-patient
  confirmation, and protected-data rules
- External execution: not authorized by this proposal; automated validation
  remains synthetic/mock only
