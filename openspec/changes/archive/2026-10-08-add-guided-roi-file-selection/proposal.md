# Add guided file selection to the standalone ROI GUI

## Why

The current source-member controls are read-only drop-downs with no per-field
picker. A user cannot type a relative member name or browse for a member, and
the labels do not explain which generated file belongs in each field. The
separate RT Structure DICOM picker is easy to confuse with the preparation
summary, which is a JSON member of the selected case.

## What Changes

- Make every case-member field editable and give it a picker for a directory
  file or ZIP member. Clearly separate case-internal evidence from external
  RT Structure, RT Plan, and frozen CT files.
- When the selected case follows an unambiguous dicomxphits output layout,
  suggest the unique canonical combined dose, paired error and retained dose,
  generation/execution summaries, segment manifest, and preparation summary.
  Show the suggested state. The user can replace every suggestion. Leave a
  field empty when candidates conflict or the canonical match is absent.
- Keep the independent analysis validator as the final authority. Suggestions
  do not accept a case, establish DICOM identity, or trigger analysis.
- Add a Japanese usage guide explaining each input and the missing frozen
  CT2PHITS evidence case.

## Impact

- Changes only the standalone GUI's selection behavior and documentation.
- No change to the standalone statistics formulas, DICOM coordinate chain,
  public workflow GUI, PHITS execution, or clinical claims.
- Automated tests use only synthetic directory and ZIP layouts.

## Approval

Status: approved by the primary user on 2026-10-08 for the unique canonical
suggestions described here. The prior approved GUI contract required manual
selection of source members; this approved change permits only unambiguous,
editable suggestions and retains all final validation.
