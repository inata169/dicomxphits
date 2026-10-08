# Guided standalone ROI file selection design

## Source-member selection

List all safe relative members of the chosen directory or ZIP. Each field has
an editable path and a picker over that source; directory pickers return a
relative path only if the chosen file is inside the source. A ZIP picker shows
its members with filtering. The per-field candidate list highlights familiar
extensions but never prevents selecting another existing member. The reader
still rejects duplicates, links, malformed paths, and incompatible pairs.

## Canonical suggestions

Use only filenames and path suffixes within the selected source. Do not read
historical absolute paths from summaries as selectors. Suggest an official
combined dose only for one `sumtally/<combined-name>.out` match. Prefer an
error in the same directory; otherwise suggest error plus retained dose from
one co-located saved Sumtally run. If there are multiple viable saved runs,
leave the affected fields empty. Suggest each JSON evidence member only when
its expected `analysis/` or `segments/` path suffix has one match. Keep all
suggestions visible and editable; clear stale fields when the source changes.

No external RT Structure, RT Plan, CT snapshot, or ROI number is inferred from
names. The GUI labels the preparation summary as JSON inside the source and
the RT Structure as an external DICOM file. DICOM binding remains subject to
the original fail-closed validator.

## Validation

Synthetic tests cover a standard case, an error preserved in one saved run,
multiple saved runs, missing evidence, manual replacement, member browsing,
source changes, and no automatic DICOM or ROI selection. Hidden Tk checks
verify controls are available without running external tools.
