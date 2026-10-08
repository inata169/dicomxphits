# Change: Add a display-language menu to the standalone ROI GUI

## Why

The user requested English and Japanese display switching in the standalone
ROI GUI. The current screen mixes both languages and has no language menu.

## What Changes

- Add a visible `表示言語 / Language` menu with Japanese and English choices.
- Start in Japanese and switch application-owned labels, buttons, headings,
  guidance, and contextual messages without resetting the session.
- Preserve entered paths, selected ROI, queued cases, results, and busy state.
- Document that DICOM names, source diagnostics, and exported schema fields
  retain their original values; native file-dialog chrome follows the OS.
- Add synthetic regression tests and exercise switching through Computer Use.

## Impact

Only the standalone ROI presentation layer, its tests, documentation, and
OpenSpec contract are affected. Analysis, units, normalization, validation,
export schemas, and the existing public workflow remain unchanged.
The user approved this proposal before implementation. The change updates the
same pull request.
