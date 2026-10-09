# Add three-plane CT volume clipping to the guided GUI

## Why

The CT2PHITS frontend currently converts the complete CT volume. The user
requests Axial, Coronal, and Sagittal previews and selection by numeric bounds
or clicking points. Both methods should describe the same clipping volume.

The supplied screenshot is a visual reference. The follow-up request expands
the preview to three planes; this proposal includes first/last slice selection.
The user's follow-up request on 2026-10-09 explicitly adds numeric X/Y/Z
coarse-graining controls to this active change.
The user's 2026-10-09 clarification confirms that a human, not an automatic
classifier, chooses an arbitrary-size axis-aligned box after visually judging
which source voxels to retain and which equipment or other material to exclude.

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
- Make manual review explicit: a browse mode cannot change bounds, a corner
  selection mode changes only the chosen view's two axes, and each plane can
  be enlarged and stepped one source index at a time.
- Pass explicit pixel/slice bounds through the current GUI-to-CLI path, validate
  them again in the frontend, and record them in the existing manifest.
  Retain complete, unmodified source CT and RT Plan snapshots.
- Preserve the full-volume default and coarse-graining default `8 8 2`, while
  allowing explicit positive X/Y/Z factors. Preserve coordinate mode `1` and
  existing safety gates. Every clipped or non-default-factor result is checked
  against the frozen CT and conversion table before downstream use. The known
  unequal-factor Y material loss may be corrected only in the CT voxel include.
- For clipped conversion, retain complete coarse groups and warn before
  execution when incomplete high-end groups will be discarded. Record both
  requested and retained bounds. Reject a box that yields zero voxels on any
  axis. Preserve the complete source snapshots.
- Place a clipped output using the selected first frozen slice's DICOM origin,
  while retaining the full-series origin as source evidence. Check that the
  raw tool origin and generated voxel counts match the selected contract.

## Impact

- New proposed capability: `ct-pixel-clipping`; proposed deltas also affect
  `ct2phits-frontend` and `guided-gui-workflow`.
- Expected implementation: GUI state/command integration, small preview and
  selection modules, frontend input/manifest validation, synthetic tests, and
  English/Japanese GUI manual updates. No new imaging dependency is planned.
- Orthogonal Coronal/Sagittal views derive from the already-supported uniform
  axial HFS source stack. Arbitrary oblique resampling, 3D surface rendering,
  source DICOM rewriting and Structure selection
  are outside this proposal.
- A user-selected smaller calculation volume can affect results; explain that
  only the selected box is retained. This is not an automatic crop to address
  accelerator overlap. Existing mutual-exclusion geometry, aperture guards,
  physics, dose/MU meanings, and education/research scope remain in force.

## Approval and unresolved evidence

Status: approved for implementation by the user's 2026-10-09 request sending
the saved implementation prompt, extended by the same day's explicit numeric
coarse-graining request. The separately approved synthetic CT2PHITS experiment
established the default-factor crop behavior described in `validation.md`.
The change remains active while independent material/geometry verification and
required validation are completed. Unequal X/Y factors lost material in the
installed version; the user separately approved verifying and correcting only
the resulting CT voxel material include on 2026-10-09. Real-patient data and
PHITS transport remain outside the approval.

The user's subsequent approvals authorize the selected-first-slice coordinate
handoff and warning rather than rejection for incomplete high-end coarse
groups. The user reconfirmed `8 8 2` for clipped conversion because `1 1 1`
would take longer. These approvals do not authorize guessing geometry or
running PHITS transport or real-patient data.
