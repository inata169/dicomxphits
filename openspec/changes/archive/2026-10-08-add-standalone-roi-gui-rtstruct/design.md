# Standalone ROI GUI and RT Structure mapping design

## Separation and selections

Implement a separate desktop UI, not another page in the public workflow
GUI. Reuse the independent pair/evidence validation and scalar statistics.
The UI may enumerate candidate ZIP members and suggest an unambiguous
canonical layout as specified by `add-guided-roi-file-selection`. The user
can replace every suggestion. It must never decide among multiple candidate
cases, retained run directories, RT Plans, CT series, or ROIs by name. Show an
invalid/missing input state
before enabling analysis. GUI selections are not workflow authority.

Each row in a batch binds one case snapshot and one region selection. Sphere
and RT Structure rows remain visibly distinct. Do not call a sphere
`Chamber` merely because the user enters that display label. A Structure row
requires a selected RT Structure, RT Plan, and matching CT series/reference.
The UI lists ROIName and ROINumber together and requires an explicit
ROINumber selection. Duplicate or absent numbers, inconsistent ROIContour
references, and unsupported contour types fail closed.

## Coordinate chain

Use the accepted fixed-field geometry semantics already documented in the
repository as the reference. Validate the canonical case manifest, mesh
binding, frozen CT-series evidence, RT Plan isocenter, and the DICOM frame
relationships before interpreting contours. Convert the PHITS cell centres
to DICOM patient coordinates using the validated placement, then determine
membership from the selected RT Structure contour on the matching CT
geometry. Require an unambiguous centre-to-cell mapping; reject unsupported
orientation, frame mismatch, missing references, and boundary ambiguity.
No nearest-name selection, silent interpolation, resampling, or altered
physical inclusion tolerance is permitted. The resulting mask is transient
and has the standalone script's native `(x, y, z)` ordering and exact mesh
edges. Do not write real DICOM-derived masks into the repository.

The existing post-completion Structure evaluator is a format/geometry
reference only. The adapter reuses its read-only frozen-CT and cell-mapping
helpers, but never invokes the evaluator or its workflow-control functions.
Its terminal-success authority, 50% global-Dmax threshold,
and GUI result records do not carry over. The standalone report uses all
selected native cells for dose summaries and only positive-dose,
positive-r.err cells for voxel-error summaries, as already specified.

## Display and reports

Show each case's status, region type, label, native count and volume, mean,
minimum, maximum, spatial standard deviation, and separate voxel r.err
statistics. The old `voxel_dose_sum_cgy` field remains a sum; the GUI calls
it `sum of selected cell doses (cGy)` and explains why it changes with grid
count. A one-cell selection has equal sum and mean. Missing or invalid
Structure geometry must not fall back to a sphere. Real-data reports are
new-only and kept outside the source and public repository.

## Validation boundary

First test the selectors, identity binding, coordinate mapping, and UI
states with project-authored synthetic PHITS grids, CT, RT Plan, and RT
Structure sets. Focus on a Structure that selects one cell, multiple cells,
no cells, an offset mesh, a frame mismatch, and a centre on a mapping
boundary. Run all public checks. Read-only local examples may be examined
only for their explicitly selected inputs; unresolved identities or
geometry remain unverified, not guessed. No clinical or commissioning
claim follows from a passing synthetic or local check.

## Approved presentation refinement

The user requested the established dicomxphits navy/cyan palette and desktop
interaction testing on 2026-10-08. The standalone window uses that palette,
clearer title hierarchy, readable fixed-width result columns, and a vertical
viewport for smaller screens. These presentation changes preserve the accepted
input, geometry, statistics, and report contracts. During analysis, case
removal and export are disabled so the case list stays aligned with results.
Malformed ZIP input produces a recoverable dialog. Changing the case list
clears stale result details.
