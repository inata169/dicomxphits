# Tasks

## 1. Confirm Current Boundaries

- [x] 1.1 Trace the public workspace beam-selection and PHITS-input write path
  used by both the GUI and CLI.
- [x] 1.2 Confirm whether any current `PrimaryFluenceModeSequence` or FFF
  validation exists and preserve it unchanged; otherwise record the absence in
  the completion report.
- [x] 1.3 Record baseline public-spectrum identity and representative synthetic
  6 MV PHITS-input output so unchanged physics can be compared after the guard.
  The unchanged representative input SHA-256 is
  `1e798a7dc814a9c9b56b19a8477514625d7a174a20487f355c7911328b0db24f`.

## 2. Centralize the Fixed Public Model

- [x] 2.1 Define one package-owned identity for the Elekta Precise nominal
  6 MV fixed public research model without changing spectrum bytes.
- [x] 2.2 Reuse that identity for GUI text, validation, and serialized evidence;
  do not add an energy selector or 10 MV affordance.

## 3. Add Core RT Plan Energy Validation

- [x] 3.1 Validate included treatment-beam `RadiationType` and effective
  `NominalBeamEnergy` in the common workspace path before PHITS input output.
- [x] 3.2 Implement first-control-point presence and later-control-point
  inheritance, rejecting within-beam changes and all values other than finite,
  positive 6 MV.
- [x] 3.3 Produce controlled beam-specific errors that identify the fixed model
  and confirm that no PHITS input was generated.
- [x] 3.4 Add backward-compatible `public_beam_model` evidence to the segment
  manifest and workspace-preparation summary.
- [x] 3.5 Preserve cleanup and fail-closed output behavior so rejected plans do
  not leave a public spectrum or segment PHITS input.

## 4. Clarify the Shared GUI

- [x] 4.1 Show the fixed 6 MV model and fixed nominal energy in a read-only
  shared area visible from all five workflow pages.
- [x] 4.2 Show `https://github.com/inata169/dicomxphits` and author
  `Hiroki Inata` as shared read-only text without browser-launch behavior.
- [x] 4.3 Increase only the common Activity log text area enough to keep at
  least two lines visible while retaining vertical scrolling and latest-entry
  auto-scroll.
- [x] 4.4 Preserve the existing layout, colors, fonts, stage buttons, and
  minimum-window access to primary controls except for the bounded shared-area
  adjustments required above.

## 5. Add Synthetic Regression Coverage

- [x] 5.1 Cover one 6 MV beam and multiple 6 MV beams as successful inputs.
- [x] 5.2 Cover 10 MV, mixed 6/10 MV beams, within-beam changes, missing first
  energy, malformed/non-finite/non-positive energy, and non-photon radiation as
  fail-closed inputs before PHITS input generation.
- [x] 5.3 Cover later-control-point inheritance and beam identity in controlled
  errors.
- [x] 5.4 Verify the additive manifest and workspace-summary 6 MV evidence.
- [x] 5.5 Verify shared fixed-model/provenance text, absence of an energy
  selector, Activity log sizing, retained scrolling and auto-scroll, and common
  log construction across all workflow pages.
- [x] 5.6 Compare representative valid 6 MV generated PHITS input and public
  spectrum identity with the baseline, allowing only the new JSON evidence.

## 6. Validate and Report

- [x] 6.1 Run focused unit and GUI tests using only synthetic DICOM and fake or
  mock runners.
- [x] 6.2 Run CLI help. Package build was attempted but is a deferred,
  non-blocking environment check because the installed build frontend lacks
  `wheel` and isolated build dependencies cannot be fetched without network
  access; no dependency or network change was made.
- [x] 6.3 Run `python -m compileall src`, full pytest,
  `python tools/verify_public_tree.py`, `openspec validate --all --strict`,
  `git diff --check`, `git diff --stat`, and `git status --short`.
- [x] 6.4 Accurate GUI rendering was unavailable in the Linux headless
  environment. Provide Windows manual checks at 1360 x 820 and 1120 x 720 and
  report display-scaling verification as unperformed.
- [x] 6.5 Confirm version metadata, version displays, changelog, release notes,
  historical validation records, and public version wording are unchanged.
- [x] 6.6 List README and GUI User Guide fixed-model display and energy-rejection
  explanations as later documentation recommendations without editing runtime
  documentation in this change.
- [x] 6.7 Promote accepted deltas, archive this change, and strictly validate
  the resulting OpenSpec tree only after approved implementation and required
  acceptance checks are complete.
