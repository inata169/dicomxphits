# Three-plane CT clipping design

## Current implementation evidence

- `run_ct2phits.select_ct_series()` validates a single axial HFS series,
  uniform adjacent Z spacing, matching dimensions, and consistent PixelSpacing,
  then orders slices by physical Z.
- `render_ct2phits_input()` currently writes `1 slice_count` and
  `1 Columns 1 Rows`. The manifest records those same full-volume ranges;
  neither the CLI nor main Tk GUI has clipping controls or an image viewer.
- `ct2phits_datfiles.prepare_ct2phits_assets()` derives translation from the
  original CT origin and RT Plan isocenter, overwrites c91/c92/c93, copies
  CTsurf/CTvoxel unchanged, and writes CTtrans.inp. Generated CTtrans.dat is
  inventory-only.
- GUI handoff uses `CT/CT000001.dcm`. The origin reader examines the entire
  frozen CT directory and uses minimum Z; changing that reference filename
  alone does not establish the cropped origin.
- `structure_relative_error.py` checks original source dimensions, slice
  count, and origin. Keep source-series evidence distinct from cropped mesh
  dimensions. Existing mock outputs do not prove external clipping geometry.

## Proposed interaction

1. Select the CT directory and an explicit series when needed. Require the
   existing non-patient phantom confirmation before decoding preview pixels.
2. Open **CT preview / Clipping range** from the CT2PHITS page. Display Axial,
   Coronal, and Sagittal images together, with plane navigation, linked
   crosshairs, direction labels, readable contrast, one-index stepping, and
   optional enlargement of one plane. Omit demographics.
3. In browse mode, inspect the candidate source volume without changing its
   bounds. Enter six bounds, or activate **Select two corners** and click
   opposite corners within one view. Show the first point immediately and a
   rectangle after the second. Pointer readout identifies original pixel and
   slice indices. Return to browse mode after a completed pair.
4. Update the shared box, all numeric fields, and all three overlays. Shade
   excluded regions lightly. Show retained column, row, and slice counts.
   Identify a viewed plane outside the box as outside; do not imply that a
   rectangle on that plane is retained.
5. **Apply** commits the validated box to this case; **Cancel** discards edits;
   **Reset to full volume** chooses the original full bounds. The main stage
   displays the applied bounds before its existing execution action.

Two clicks affect only the current view's two axes:

| View | Axes changed | Bounds preserved |
| --- | --- | --- |
| Axial | Nx and Ny | First/Last slice |
| Coronal | Nx and First/Last slice | Ny |
| Sagittal | Ny and First/Last slice | Nx |

Initially all three axes cover the full volume. Changing viewing position,
navigation crosshairs, or contrast never edits the box. Numeric input is a
complete keyboard-accessible path. Invalid fields or an incomplete active
corner pair disable Apply. Closing without Apply preserves the previous
selection. Switching views during a corner pair cancels that unfinished pair.
Preview actions never launch conversion.

The human decides what material belongs inside the box. The preview does not
recognize a couch or other unwanted material and cannot remove voxels inside
the selected box by semantic class. Enlargement and single-index stepping
make visual review easier; neither changes selected bounds.

## Coordinate model

Proposed bounds are one-based, inclusive original source indices, not patient
millimetres or canvas pixels. Nx denotes DICOM columns; Ny denotes rows; slice
numbers follow validated ascending physical Z, not filenames or InstanceNumber.

A source array has order `volume[z, y, x]`. The selected region is
`volume[first-1:last, ny_min-1:ny_max, nx_min-1:nx_max]`.
Source counts are `max - min + 1` on every axis.

For the already-supported HFS orientation, propose these explicit display
mappings, with direction labels derived from validated metadata:

| View | Array displayed | Horizontal / vertical directions |
| --- | --- | --- |
| Axial | `volume[z, :, :]` | X increases right / Y increases down |
| Coronal | `volume[::-1, y, :]` | X increases right / superior is up |
| Sagittal | `volume[::-1, :, x]` | Y increases right / superior is up |

Z reversal is display-only. Mouse mapping must invert it explicitly. Preserve
physical aspect ratio using column/row PixelSpacing and actual adjacent Z
positions. Each view has one reversible source-to-canvas transform, including
resize and letterboxing. Clicks select the source pixel containing the point;
outside-image clicks are ignored. Draw overlays on included pixels' outer
edges. Normalize either mouse click order; reject reversed numeric bounds.

Coronal/Sagittal are orthogonal display reformats, not new DICOM series or
physical resampling. Single-slice sources have no adjacent Z spacing: retain
Axial and numeric controls and label the other views unavailable, without
inventing thickness from another metadata field.

## Loading and state

Reuse Tk, numpy, pydicom, and the existing series validator. Prefer a small
`ct_pixel_clipping.py` model/mapping module and `ct_preview.py` dialog over
embedding imaging logic in the main GUI. These filenames are proposed.
An in-memory Tk PhotoImage raster avoids a new plotting/imaging dependency.

Three-plane preview requires the stack's pixels. Load in a background worker
under a documented memory limit with progress and cancellation. Estimate
allocation before loading and bound temporary/cached arrays. Apply each
slice's rescale values and contrast for display without rewriting source
pixels or retaining an unnecessary second floating-point volume. Validate
decoded shape and supported monochrome single-frame representation.

Report unsupported encoding, missing pixels, oversize allocation, or load
failure clearly; do not install codecs or create persistent caches. The
existing unpreviewed full-volume path remains available when preview is
unused. Discard stale worker results after case changes or dialog close.

Bind applied bounds to inspected source identity and geometry; CT directory
or series changes invalidate the selection. Revalidate before conversion and
require reinspection if files or geometry changed. Keep bounds out of global
preferences and unrelated existing-case recovery. Preserve the immutable
request of an active stage.

## Coarse-graining controls

Expose three positive integer factors in the CT2PHITS case page, defaulting
to `8 8 2`. Pass them as an explicit CLI triple and record the effective
triple in the input and manifest. Reject missing, noninteger, zero, or
negative factors before workspace creation. Keep the default input bytes
unchanged. The current external conversion gate applies to any non-default
factor until the supported tool's averaging and geometry contract is checked.
The numeric fields do not change the source preview or the manually selected
source-index clipping box.

## Frontend and snapshot integration

Proposed CLI groups are `--pixel-clipping NX_MIN NX_MAX NY_MIN NY_MAX`,
`--slice-range FIRST LAST`, and `--coarse-graining NXC NYC NZC`. Omitted
values retain the current input bytes.
Validate complete integer ranges and established external-tool constraints
before workspace creation, using a shared GUI/CLI contract.

Retain ALL original source slices and their existing Z-ordered snapshot names,
hashes, identities, dimensions, and origin. Do not copy only the selected
subset or rebase its numbering. Keep the frozen reference at CT000001.dcm.
Write selected bounds only to the appropriate CT2PHITS input lines and to
`ct2phits_input.clipping` / `ct2phits_input.slice_range`. Preserve existing
integrity, frame checks, new-workspace protection, and external execution gates.

## Required contract evidence before enabling clipped conversion

The screenshot and full-volume code do not establish arbitrary crop behavior.
Confirm from authoritative supported-version documentation:

1. Inclusive original pixel/slice endpoints and axis/order meaning.
2. X/Y coarse factor 8: small widths, remainder widths, and unaligned minima.
   Z factor 2: one slice, odd selected depth, and odd/even first indices.
   Repeat the contract check for any user-entered factor triple before that
   triple is eligible for external conversion.
3. Where generated geometry represents skipped leading columns, rows, and
   slices: local CTsurf/lattice bounds, c91/c92/c93, or other parameters.
4. Whether the current full-origin handoff preserves physical placement, and
   how generated counts/extents/placement can be checked independently.

Do not guess crop-origin shifts, rebase coordinates, silently expand/shorten
ranges, snap indices, or alter physical tolerances. If current handoff is
incompatible, stop for a separately reviewed coordinate-contract change.
Similarly, a new restriction requires an evidence-backed proposal update.

Real CT2PHITS execution or real non-patient inputs require a separate explicit
request with designated external paths. The original planning phase did not
inspect an installation or execute a tool, and no official distribution file
may be copied into the repository.

### 2026-10-09 synthetic tool finding and pending decision

An explicitly authorized run of the installed CT2PHITS batch on generated
non-patient CT established inclusive bounds, floor-truncation of incomplete
coarse groups, selected-slice DICOM shift, and loss of material data for
unequal X/Y factors in this installed version. See `validation.md`.

The current handoff uses the full source-series origin in its IEC translation.
For a Z crop beginning after slice one, that discards the tool's selected-slice
translation. A proposed, not yet approved, correction is to derive the
translation from the frozen selected first slice, cross-check it against the
generated raw DICOM shift, and retain the full-series origin and count as
separate source evidence. The geometry of unselected source snapshots and
the HFS-to-IEC axis/sign transform would remain unchanged. Any conversion
restriction for non-divisible source dimensions or unequal X/Y factors also
requires an explicit human decision before the gate can be removed.

## Acceptance and validation

- Default omitted and explicit full-volume selections reproduce current input
  and source/handoff behavior.
- Bounds errors fail before workspace creation; valid GUI selection and
  external conversion eligibility are distinguished where tool limits apply.
- An asymmetric synthetic 3D pattern with unequal X/Y/Z spacing, nonzero
  origin, and shuffled filenames/InstanceNumber detects axis swaps, Z display
  inversion, wrong sorting, and one-pixel mistakes.
- Test all views, reverse click order, outer edges, resizing/letterboxing,
  synchronized fields/overlays, preserving the third axis, outside-box
  viewing, navigation independence, Apply/Cancel/reset, and keyboard input.
- Test per-slice rescale, single-slice fallback, decoding/memory failures,
  cancellation, stale workers, changed sources, and stage locking.
- Test XY-only, Z-only, and combined off-centre crops with independently
  established counts, extents, and position; include first greater than 1 and
  last less than source count. Do not validate a guessed formula against itself.
- GUI arguments, input, and manifest must agree. Source hashes, count, and
  metadata remain unchanged. Existing geometry guards and downstream
  Structure coordinate binding remain valid; do not silently redefine an ROI
  to conceal clipping coverage.
- Use synthetic pixel fixtures and mock runners, plus a synthetic Tk
  interaction check. Update both GUI manuals, run focused/full public checks,
  and report unverified real-tool behavior explicitly.

Planning completion leaves this draft active. Promote accepted deltas and
archive only after approved implementation and required verification finish.
