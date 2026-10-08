# standalone-phits-roi-statistics Specification

## Purpose
Provide independent, read-only statistics for explicitly selected completed
PHITS Sumtally dose/error pairs and coordinate-bound regions, with separate
dose, geometry, and voxel statistical-error definitions.

## Requirements

### Requirement: Independent explicitly selected analysis

The script SHALL run with Python 3.12 and NumPy without an installed
dicomxphits package, GUI, DICOM input, or external-tool execution. It SHALL
read only explicitly selected source files or ZIP members for a completed
combined dose/error snapshot, with a single-case interface and an equivalent
explicit JSON batch interface. It MUST NOT change source cases, execute a
calculation, select another case implicitly, or grant GUI/workflow authority.

#### Scenario: A previous calculation is selected

- **WHEN** a user explicitly identifies a supported existing combined pair
  and its required evidence in a directory or ZIP
- **THEN** analysis can run independently of the GUI version without
  RTDOSE conversion, source mutation, or external-tool execution

#### Scenario: A Structure is requested by name alone

- **WHEN** a requested Structure has no coordinate-bound input mask
- **THEN** the script reports missing geometry without inventing a contour
  or silently substituting a sphere

### Requirement: Complete pair and normalization validation

The script SHALL initially support only reviewed PHITS 3.35 T-Deposit
uniform xyz/xy combined dose/error outputs with `isumtally=2`.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** It SHALL validate array completeness, finite non-negative values, axis/slice order, matching geometry, output roles, source weights, and sumfactor before using any value. It SHALL bind consumed bytes to digests and validate consistent generation, successful execution, manifest, and normalization evidence proving the one-fraction Gy basis. The output header alone MUST NOT establish cGy.  For explicitly selected retained error input, the script SHALL require the co-located retained dose to be byte-identical to the explicitly selected official dose and terminal dose digest. It MUST NOT scan for retained directories, repair evidence, or substitute per-segment errors.

#### Scenario: A legacy retained pair is explicitly selected

- **WHEN** the retained pair passes supported-format checks, both selected
  doses match exactly, and saved evidence proves the one-fraction Gy basis
- **THEN** it is available for the independent report without a recovery
  write or change to the GUI's evidence requirements

#### Scenario: Pairing or absolute-dose meaning is unproved

- **WHEN** metadata, values, recorded digest, source weights, or normalization
  do not match, or the output format is unsupported
- **THEN** the case fails with a specific reason instead of partial parsing,
  a guessed unit, a GUI-version assumption, or an external rerun

### Requirement: Safe snapshot input

The script SHALL reject unsafe or ambiguous source paths, linked or reparse
paths, duplicate selected ZIP members, traversal, unsupported entries, and
inputs changing during a read. ZIP reads SHALL be bounded and SHALL NOT
extract files. Saved historical absolute paths MUST NOT be followed as
implicit current inputs. Array input MUST NOT permit pickle execution.

#### Scenario: A selected archive entry is ambiguous or unsafe

- **WHEN** the selected member is duplicated, traverses outside the selected
  container, or is not a supported ordinary entry
- **THEN** analysis fails without extraction or a substitute selection

### Requirement: Distinct sphere geometry and sampling populations

The script SHALL interpret sphere centres in PHITS isocenter-relative xyz cm
and accept exactly one positive finite radius in cm or analytic volume in
cm3.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** It SHALL report analytic volume `4*pi*r**3/3`, centre-anchored sampling Points at explicit spacing h, sampling volume `Points*h**3`, native Grid Points, and selected native-cell volume separately. Sampling spacing SHALL default to 1 mm. Inclusion SHALL use cell/point centres at distance no greater than the radius without a new physical tolerance or partial-volume weighting. Only selected native cells SHALL contribute to numerical dose/error summaries. An out-of-mesh sphere MUST NOT be silently clipped.

#### Scenario: The approved radius example is evaluated

- **WHEN** radius is 0.25 cm and sampling spacing is 1 mm
- **THEN** Points is 81, sampling volume is 0.081 cm3, and analytic volume
  is approximately 0.06544985 cm3, with distinct names and units

#### Scenario: Native spacing and offset differ

- **WHEN** that sphere is centred on a 2 mm native lattice
- **THEN** Grid Points is 7 and selected native volume is 0.056 cm3
- **AND** a different native spacing or offset is counted from its actual
  centres, never forced to reproduce 7 or 81

#### Scenario: Analytic volume is supplied instead of radius

- **WHEN** the sphere input is analytic volume 0.25 cm3
- **THEN** radius is approximately 0.39079632 cm and the input is not treated
  as radius 0.25 cm or sampling volume 0.25 cm3

### Requirement: Explicit same-grid Structure membership

The NPZ Structure path SHALL require an explicitly supplied Boolean NPZ mask
with shape `(nx, ny, nz)`, ascending x/y/z edge arrays in cm, and an explicit
PHITS coordinate-system marker.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** Shape, edge arrays, axis order, and frame SHALL match the dose grid. That path MUST NOT infer contours, interpolate, resample, or convert DICOM coordinates. It SHALL report a supplied label, region type, native counts, and selected cell volume. Sphere-only geometric and sampling quantities SHALL be null for arbitrary masks.

#### Scenario: A compatible Structure mask is supplied

- **WHEN** a nonempty mask is explicitly bound to the exact PHITS mesh
- **THEN** all and only its true cells contribute to the Structure summary
  and its volume is the sum of their native cell volumes

#### Scenario: A mask is displaced or a sphere has a Structure-like label

- **WHEN** mask geometry differs from the dose grid
- **THEN** evaluation fails instead of resizing or guessing its position
- **AND** a sphere carrying a Structure-like display label remains explicitly
  typed as a sphere and is not asserted to be an imported Structure

### Requirement: Defined one-fraction dose statistics

The script SHALL convert validated one-fraction Gy to cGy by multiplying by
100 only.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** It MUST NOT reapply MU, source calibration, or planned fractions. Across all selected native cells, including zero-dose cells, it SHALL report the voxel-dose sum, arithmetic mean, minimum, maximum, and population spatial standard deviation (`ddof=0`). Total Dose SHALL be explicitly labelled a grid-dependent voxel-dose sum, not an energy integral or ROI mean. The standard deviation SHALL be identified as spatial variation, not Monte Carlo standard error. Empty selections SHALL have null statistics and a reason.

#### Scenario: A uniform nonempty region is evaluated

- **WHEN** N selected native cells each have dose d in cGy
- **THEN** voxel-dose sum is N*d, mean/minimum/maximum are d, and spatial
  standard deviation is zero, independently of sampling Points

#### Scenario: Planned fractions exist in metadata

- **WHEN** the saved plan includes more than one planned fraction
- **THEN** this report still identifies and summarizes the one-fraction
  Sumtally input without applying a course-dose multiplier

### Requirement: Separate voxel statistical-error summaries

The script SHALL use selected native cells with positive dose and positive
r.err as its statistical-error population, with no low-dose threshold.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** It SHALL report unweighted mean, median, P95, and maximum of r.err in percent; quantiles SHALL use linear interpolation at `q*(n-1)`. It SHALL separately report mean and maximum absolute voxel standard error `D_i*r_i` in cGy. These summaries MUST NOT be labelled the exact uncertainty of an ROI mean or computed with an unreported independence assumption.  The script SHALL report eligible count, zero-dose count, positive-dose zero-r.err count, and total exclusions. Zero r.err MUST NOT be presented as proof of zero uncertainty. One eligible voxel SHALL be labelled with count one; no eligible voxels SHALL give null error summaries with an explanation while preserving otherwise valid dose summaries. Invalid array values MUST invalidate the case rather than be silently excluded.

#### Scenario: Only one native cell has usable r.err

- **WHEN** the pair and nonempty region are valid and one selected cell has
  positive dose and positive r.err
- **THEN** that cell defines the reported voxel-error summaries with eligible
  count one, regardless of sampling Points

#### Scenario: All selected r.err values are zero

- **WHEN** dose statistics are valid but no selected cell has eligible r.err
- **THEN** dose summaries remain available, error summaries are null, and
  the exclusion counts and reason identify the partial result

### Requirement: Reviewable independent reports

The script SHALL provide console summaries and explicit new-only CSV/JSON
exports in a separately selected analysis directory.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** Reports SHALL include case/region labels, statuses, definitions and units, geometry, spacing, population counts, one-fraction basis, scalar results, and versioned provenance with source digests. Missing quantities SHALL be null or empty with reasons. Exports MUST NOT contain automatic DICOM identifiers, absolute source paths, raw grids, or GUI authority records. External CSV strings SHALL follow the accepted spreadsheet-neutralization contract; numbers SHALL remain numeric. Output writes SHALL be guarded, atomic per file, and new-only.

#### Scenario: An independent report is written

- **WHEN** the explicitly selected safe output directory is separate from
  source cases and report destinations are absent
- **THEN** the report is written without altering any input or existing
  result, and it claims no completion, stopping, clinical, or recovery authority

#### Scenario: A batch contains an invalid case or publication fails

- **WHEN** at least one case is invalid/empty or an export cannot be published
- **THEN** the invocation reports a nonzero overall status, identifies the
  failures and any already published reports, and does not imply full success

### Requirement: Synthetic validation and bounded compatibility claims

Automated tests SHALL use synthetic files, masks, and archives only.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** They SHALL verify parsing, axis order, normalization, region populations, approved volume examples, scalar statistics, diagnostics, input immutability, and safe exports. Compatibility claims SHALL name the validated file formats and test scope; simulated v1.0.3/v1.1.1 layouts MUST NOT be represented as real-output validation. Real calculation data and reports MUST remain outside the public repository and SHALL NOT be used by ordinary tests or CI.

#### Scenario: Compatibility is tested without installed external tools

- **WHEN** supported legacy retained-pair and current saved-pair layouts are
  exercised using synthetic data
- **THEN** the standalone script works without external execution and the
  results describe synthetic format compatibility only
