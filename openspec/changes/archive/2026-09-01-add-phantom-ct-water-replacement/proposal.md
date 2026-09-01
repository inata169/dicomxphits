# Add Non-Patient Phantom CT Water Replacement

## Why

The documented research workflow sometimes uses a reusable physical phantom CT
whose two-centimetre water-equivalent layer contains a CC13 chamber, cable, and
associated imaging artefacts. Re-scanning the phantom without the chamber is
not always practical. Leaving those features in CT2PHITS makes them part of the
transport geometry even when the intended calculation is a chamber-free
water-equivalent layer.

The repository has no tool that creates an auditable derived CT series from an
explicit RTSTRUCT target and a clean water reference. Manual pixel editing
risks changing pixels outside the intended layer, losing per-slice rescale
semantics, or retaining source SOP Instance UIDs after Pixel Data changes.

## What Changes

- Add an independent command-line helper for education and research with
  non-patient phantoms only. It requires an explicit acknowledgement flag,
  source CT directory, RTSTRUCT, uniquely named target and reference ROIs, and
  a new output directory.
- Replace only target-ROI stored pixel samples. For each slice, use the median
  HU of that slice's clean reference ROI; when the reference ROI has no pixels
  on that slice, use the global reference-ROI median and record the fallback.
- Respect each slice's rescale slope/intercept and native stored-pixel bit
  representation. Preserve every sample outside the target mask byte-for-byte.
- Rasterize closed planar RTSTRUCT contours in patient coordinates, including
  parallel oblique CT series, and reject inconsistent or ambiguous geometry.
- Write a new derived CT series without modifying the source CT or RTSTRUCT.
  Preserve study/frame geometry, generate a new series UID and new SOP UID for
  every derived slice, synchronize file-meta SOP UIDs, and add derivation
  metadata.
- Produce machine-readable JSON, a readable text report, and representative
  before/after/difference/mask PNG evidence without recording patient identity.
- Fail closed on structural DICOM errors, ambiguous ROIs, reference mismatch,
  unsafe output paths, unsupported Pixel Data encoding, or inverse-rescale
  overflow. Treat suspicious water statistics, outside-air intersection, and
  a target thickness outside 15--25 mm as explicit QC warnings; do not publish
  a completed derived series unless the operator also supplies an explicit QC
  warning acceptance flag.
- Keep RTSTRUCT and RTPLAN rewriting out of scope. Documentation will state
  that the source RTSTRUCT references the source CT and that TPS import,
  reassociation, and independent verification are required before downstream
  use.
- Add only synthetic automated tests. The supplied phantom folders and any
  licensed CT2PHITS/PHITS tools remain outside repository automation and are
  used only under separate, explicit real-data execution approval.

## Impact

- New capability: `phantom-ct-derivation`.
- Expected implementation areas after approval: a new module under
  `src/dicomxphits/`, a thin script under `tools/`, one console entry point,
  focused synthetic DICOM tests, README guidance, and a dedicated handoff
  document.
- Existing CT2PHITS, PHITS geometry, beam model, field definition, MU,
  calibration factor, RTDOSE, and absolute-dose behavior are not changed.
- Derived slices intentionally change density only inside the approved target
  ROI. Their calculated dose may therefore differ from calculations using the
  chamber-containing source CT; no dose-invariance claim is made.
- The current CT2PHITS frontend remains limited to its documented axial HFS
  input geometry. Supporting oblique contour rasterization in this helper does
  not expand downstream CT2PHITS eligibility.
- This is proposal-only. No runtime or public DICOM behavior changes before
  human approval.
