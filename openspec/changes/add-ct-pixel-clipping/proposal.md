# Add three-plane CT volume clipping to the guided GUI

## Why

The CT2PHITS frontend currently converts the complete CT volume. The user
requests Axial, Coronal, and Sagittal previews and selection by numeric bounds
or clicking points. Both methods should describe the same clipping volume.

The supplied screenshot is a visual reference. The follow-up request expands
the preview to three planes; this proposal includes first/last slice selection.
Its coarse-graining values do not authorize changing the existing settings.

## What Changes

- Add a clipping dialog to the existing CT2PHITS page with linked Axial (X-Y),
  Coronal (X-Z), and Sagittal (Y-Z) views, plane navigation, contrast controls,
  direction labels, pointer coordinates, and a shared box overlay.
- Use six one-based, inclusive source-index fields: Nx min/max for columns,
  Ny min/max for rows, and First/Last slice for the validated Z-ordered series.
- Two clicks in one view select opposite corners on that view's two axes and
  preserve the third axis. Either click order produces the same bounds.
  Numeric edits update all views, and mouse selection updates the numbers.
- Keep viewing position/crosshairs separate from clipping. Provide Apply,
  Cancel, and Reset to full volume; show applied bounds before conversion.
- Pass explicit pixel/slice bounds through the current GUI-to-CLI path, validate
  them again in the frontend, and record them in the existing manifest.
  Retain complete, unmodified source CT and RT Plan snapshots.
- Preserve the full-volume default, coarse graining `8 8 2`, coordinate mode
  `1`, and existing safety gates.
- Establish supported-version clipping/coarse-graining and output-coordinate
  behavior before enabling non-default conversion. Do not guess offsets,
  silently snap indices, or infer real-tool compatibility from mock tests.

## Impact

- New proposed capability: `ct-pixel-clipping`; proposed deltas also affect
  `ct2phits-frontend` and `guided-gui-workflow`.
- Expected implementation: GUI state/command integration, small preview and
  selection modules, frontend input/manifest validation, synthetic tests, and
  English/Japanese GUI manual updates. No new imaging dependency is planned.
- Orthogonal Coronal/Sagittal views derive from the already-supported uniform
  axial HFS source stack. Arbitrary oblique resampling, 3D surface rendering,
  source DICOM rewriting, coarse-graining controls, and Structure selection
  are outside this proposal.
- A user-selected smaller calculation volume can affect results; explain that
  only the selected box is retained. This is not an automatic crop to address
  accelerator overlap. Existing mutual-exclusion geometry, aperture guards,
  physics, dose/MU meanings, and education/research scope remain in force.

## Approval and unresolved evidence

Status: approved for implementation by the user's 2026-10-09 request sending
the saved implementation prompt. Real-data/tool execution and inferred
coordinate or physics changes remain outside that approval. Implementation is
active while the supported-tool crop geometry contract remains unresolved.

Before enabling clipping, establish inclusive pixel/slice endpoint behavior,
small/unaligned/remainder selections with `8 8 2`, and crop-offset placement
in generated geometry. The current handoff replaces c91/c92/c93 using the
original full-series origin. See `design.md`.

If evidence requires changing that coordinate handoff or adding a selection
restriction, revise the proposal and obtain the required separate decision.
Plan approval does not authorize guessed geometry or real external execution.
