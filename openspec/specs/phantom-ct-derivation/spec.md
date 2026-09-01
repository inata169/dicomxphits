# phantom-ct-derivation Specification

## Purpose
Define the fail-closed creation and verification of a calculation-only derived
CT series that replaces one explicitly selected layer in a confirmed
non-patient research phantom with water-equivalent values from a separate
reference-water ROI.

## Requirements

### Requirement: Explicit non-patient phantom invocation

The system SHALL expose an independent CT water-replacement command that
requires explicit source CT, RTSTRUCT, target ROI name, reference ROI name,
new output directory, and non-patient phantom acknowledgement. The system MUST
NOT infer an RTSTRUCT, process patient data, or modify source files.

#### Scenario: Missing non-patient acknowledgement

- **WHEN** the command is invoked without the required non-patient phantom
  acknowledgement
- **THEN** it fails before reading Pixel Data or creating output

#### Scenario: Existing or unsafe output

- **WHEN** the output exists, aliases the input, overlaps the input hierarchy,
  or traverses a link or reparse point
- **THEN** the command fails without overwriting either tree

### Requirement: Explicit CT and RTSTRUCT geometry binding

The system SHALL select one conventional CT series, validate a consistent
parallel image geometry, and bind every used closed-planar RTSTRUCT contour to
an explicitly referenced source CT SOP Instance UID in the same frame and
series. It SHALL rasterize axial or oblique contours in patient coordinates at
pixel centres using an even-odd fill rule.

#### Scenario: Valid oblique contour

- **WHEN** a closed planar contour references a slice in a consistent parallel
  oblique CT series and lies on its plane
- **THEN** the target or reference mask is derived from patient-coordinate
  projection rather than an axial-only coordinate assumption

#### Scenario: Ambiguous ROI or reference mismatch

- **WHEN** an ROI name is absent or duplicated, a required ROI contour is
  absent or duplicated, a contour is not closed planar, the frame or series
  differs, or a referenced SOP instance is not in the selected CT
- **THEN** the command fails before creating a derived series

### Requirement: Reference-water HU replacement

The system SHALL compute HU using each slice's finite nonzero rescale slope and
intercept. It SHALL use the median HU of the reference ROI on each slice and
SHALL use the global reference median only for a target slice with no reference
voxels, recording every fallback.

#### Scenario: Per-slice reference exists

- **WHEN** a target slice also contains reference-mask voxels
- **THEN** every target sample on that slice receives the inverse-rescaled
  stored value corresponding to that slice's reference median HU

#### Scenario: Per-slice reference is absent

- **WHEN** a target slice contains no reference-mask voxels but the global
  reference is valid
- **THEN** the global reference median is used and the slice is reported as a
  fallback

### Requirement: Stored-pixel preservation and representability

The system SHALL support native single-frame monochrome CT Pixel Data with
8- or 16-bit allocation, signed or unsigned representation, and valid
`BitsStored` and `HighBit`. It SHALL update only target-mask stored-value bits,
preserve every outside-target allocated sample byte exactly, and fail if an
inverse-rescaled value is not representable.

#### Scenario: Target-only update

- **WHEN** a valid derived slice is written
- **THEN** target samples contain the selected water-equivalent value and every
  outside-target sample's original allocated bytes are unchanged

#### Scenario: Unsupported or overflowing representation

- **WHEN** Pixel Data is compressed, encapsulated, multi-frame, color,
  floating-point, structurally inconsistent, or the desired stored value is
  outside its declared representation
- **THEN** the command fails rather than silently converting or clipping it

### Requirement: Distinct derived CT identity

The system SHALL write a new derived CT series that preserves study, frame, and
image geometry; assigns one new Series Instance UID and a new SOP Instance UID
to every slice; synchronizes every media-storage SOP UID; and records derivation
and source-image metadata. It MUST NOT retain a source SOP Instance UID for a
slice whose Pixel Data is rewritten.

#### Scenario: Successful derived series

- **WHEN** all slices are written and reread successfully
- **THEN** geometry matches the source, all required derived UIDs differ from
  their source identities, file meta matches each dataset, and the series is
  marked derived and secondary

### Requirement: Fail-closed preprocessing QC

The system SHALL calculate and report reference voxel counts and statistics,
target principal extents and whole-layer dimensionality, target boundary
contact, and target overlap with
boundary-connected air-like pixels. Structural errors SHALL always fail. QC
warnings SHALL prevent completed publication unless an explicit warning
acknowledgement is supplied.

#### Scenario: Suspicious reference or target geometry

- **WHEN** configured QC defaults identify too few reference voxels,
  non-water-like reference statistics, image-boundary contact,
  boundary-connected air-like overlap, target thickness outside the documented
  expected range, or other than exactly one thickness-like target extent
- **THEN** the command reports every finding and stops without a completed
  derived series unless QC warnings were explicitly acknowledged

### Requirement: Identity-safe QC evidence

The system SHALL produce JSON and readable text reports plus a representative
PNG showing before, after, HU difference, masks, and contour boundaries. The
evidence SHALL include DICOM identities, geometry, voxel counts and volume,
water and target statistics, per-slice replacement values, fallbacks, warnings,
UID checks, and source-integrity results without reading or emitting patient
demographics.

#### Scenario: Completed derivation

- **WHEN** a derived series passes post-write and source-integrity verification
- **THEN** the reports and PNG are stored with the output and identify the
  result as complete

#### Scenario: Source RTSTRUCT remains unchanged

- **WHEN** completion evidence is produced
- **THEN** it states that the original RTSTRUCT still references the source CT
  and that downstream TPS reassociation and independent verification are
  required
