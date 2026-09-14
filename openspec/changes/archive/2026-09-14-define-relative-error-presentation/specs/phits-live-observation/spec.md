## MODIFIED Requirements

### Requirement: Descriptive Current-Segment Relative Error

Observation SHALL use only a complete matching dose/error pair for the current
manifest-selected primary 3D dose tally. Mesh, tally role, particle, output mode
and available history/restart metadata MUST agree. It SHALL locate the unique
mesh cell whose bin interior contains `(0, 0, 0)` in the existing PHITS
isocenter-origin coordinate system and report that cell's finite positive
relative error as percent only when its paired dose is also finite and positive.

The observer MUST NOT interpolate, select a nearest cell, add a coordinate
tolerance or change the existing mesh/coordinate mapping. If isocenter is
outside the mesh or lies on a bin boundary, the pair is incomplete or
mismatched, or the selected dose/error value is zero, negative, malformed or
non-finite, the relative-error detail SHALL be unavailable. The observer MUST
NOT substitute a value from `deposit-pdd.out`, compute full-mesh minimum,
maximum, median, mean, standard deviation or coverage, inspect DICOM RT
Structure contours, or calculate structure-based statistics.

The displayed value SHALL be identified as a provisional single Isocenter-voxel
reference, not whole-volume, ROI, combined-dose or clinical uncertainty and not
completion, convergence or automatic-stopping evidence. Tally and variance
settings MUST NOT change. Any future RT Structure relative-error evaluation
SHALL remain a separate post-completion capability and MUST NOT replace or
augment this live observation.

#### Scenario: Unique Isocenter-containing voxel is evaluable

- **WHEN** a complete matching primary 3D dose/error pair has one mesh-bin
  interior containing `(0, 0, 0)` with finite positive dose and relative error
- **THEN** observation reports only that cell's provisional `r.err` percentage
  and identifies it as an Isocenter-voxel reference

#### Scenario: Isocenter is not inside one voxel

- **WHEN** isocenter is outside the primary 3D mesh or lies on a bin boundary
- **THEN** relative-error detail is unavailable without interpolation, nearest-
  cell selection, coordinate tolerance or another-source fallback

#### Scenario: Incomplete or mismatched pair

- **WHEN** a slice is missing or dose and error metadata disagree
- **THEN** no new relative-error value is published

#### Scenario: Isocenter value is not evaluable

- **WHEN** the Isocenter voxel dose or relative error is zero, negative,
  malformed or non-finite
- **THEN** relative-error detail is unavailable and not represented as zero

#### Scenario: Other statistical sources are present

- **WHEN** PDD relative error, other mesh cells or RT Structure data are present
- **THEN** they do not replace or augment the single primary 3D Isocenter-voxel
  live reference

#### Scenario: Post-completion Structure evaluation exists

- **WHEN** a separately approved post-completion Structure evaluation is
  available
- **THEN** its statistics remain outside the live observation and do not alter
  live progress, convergence, stopping, completion, or downstream authority
