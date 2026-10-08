# Standalone ROI GUI validation

This record covers the independent tools, not the public calculation GUI or
clinical suitability. All desktop test data was generated from the existing
synthetic pytest fixtures. No PHITS, Sumtally, or DICOM converter was run.

## Desktop interaction checks

Windows Computer Use exercised these user flows:

- Open a ZIP with the native picker and inspect unique editable suggestions.
- Open the ZIP member picker and replace the selected dose member.
- Edit the source path, observe the reload gate, and reload its members.
- Add and analyse invalid and valid sphere cases in the same table.
- Inspect selected-row geometry details and scroll to the report controls.
- Save new CSV and JSON reports outside the repository and inspect their
  scalar contents.
- Remove a selected case and observe report invalidation.
- Select a case directory and reselect its dose with the native member picker.
- Select RTSTRUCT analysis, supply synthetic workspace/CT/RT Plan inputs,
  browse for RT Structure, list ROI names, and explicitly select an ROI.
- Run a bound synthetic Structure case through the GUI to a successful
  one-native-cell result. Incomplete normalization evidence was rejected
  before the complete synthetic fixture was supplied.

The shared selector callbacks and failure paths additionally have automated
Tk tests, including extensionless RT Structure files, source replacement,
ambiguous suggestions, malformed ZIPs, and analysis-busy state. Desktop
interaction is bounded evidence, not a claim that every possible file,
display scale, or operating-system dialog variation was tested.

## Corrections from validation

- Disable removal and export while a worker owns the case snapshot.
- Report malformed ZIP input without an uncaught callback exception.
- Clear detail text when the case list changes.
- Preserve readable column widths with horizontal scrolling and format
  displayed volumes to six significant digits; exported precision is unchanged.

## OpenSpec validation

The final Python checks passed: `python -m compileall src`, independent tool
`py_compile`, and `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
(1495 passed, 15 skipped, one intentional duplicate-ZIP-member warning).
The public-tree audit and Git whitespace checks also passed. The focused Tk
suite passed all 11 tests; an earlier combined focused run had a transient
Tk-display skip and was followed by this successful run.

OpenSpec CLI 1.14.1 was installed. All three ROI changes passed strict
validation before archive; both promoted ROI specifications also pass strict
validation after requirement prose was organized into scenarios without
changing the contract. Whole-tree strict validation also reports existing
warnings in unrelated specifications (long requirement bodies and one
placeholder purpose). Those accepted specifications are outside this diff;
their warnings are not represented as fixed or as a passing strict audit.
Archived-task validation passes for all three ROI changes. Its whole-archive
run also reports one pre-existing incomplete task in
`2026-08-07-add-windows-offline-installer`; that historical task was not edited.

## English and Japanese display menu

The approved language-menu addition was tested with synthetic data only.
Computer Use switched the live Windows GUI from Japanese to English, loaded
a synthetic ZIP with editable standard-path suggestions, added and analysed
a sphere case, selected its result row, and switched back to Japanese.
The selected row, file paths, numeric results, sphere parameters, and report
stem were retained. Labels, suggestions, headings, status, and result guidance
changed language. No external calculation tool or real DICOM was run.

The focused GUI suite passed all 13 tests, including new checks for ROI and
case preservation, busy guards, completion messages in the current language,
unchanged result payloads, literal diagnostic braces, and translation template
placeholders. An initial focused run had one transient Tk-display skip; the
subsequent run passed every GUI test.

After the language change, the full command
`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` reported **1496 passed,
16 skipped, one intentional duplicate-ZIP warning**. The full run includes a
Tk-display skip already covered by the successful focused run. Compilation
(`python -m compileall src` and tool `py_compile`), public-tree audit, and
Git whitespace checks passed. The language proposal passed strict OpenSpec
validation. Source diagnostics and native OS dialog controls retain their
original language. Other display scales and OS locales were not exhaustively
tested. The numerical and public workflow contracts were unchanged.
