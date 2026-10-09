## ADDED Requirements

### Requirement: Explicit Source Volume Bounds

The system SHALL represent a single axis-aligned clipping box using one-based,
inclusive integer source indices: Nx min/max for columns, Ny min/max for rows,
and First/Last slice in validated ascending physical Z order. It SHALL require
`1 <= nx_min <= nx_max <= Columns`,
`1 <= ny_min <= ny_max <= Rows`, and
`1 <= first <= last <= source_slice_count`. It MUST NOT interpret these
values as millimetres, canvas coordinates, filenames, or InstanceNumber.
The default SHALL retain the complete source volume.

#### Scenario: Numeric selection

- **WHEN** six valid source bounds are applied
- **THEN** the box includes both endpoints and every source voxel between them

#### Scenario: Invalid range

- **WHEN** a supplied range is incomplete, noninteger, reversed, or out of bounds
- **THEN** the system rejects it without silent rounding, swapping, or clamping

### Requirement: Verified Clipped Geometry Contract

Non-default CT2PHITS conversion SHALL be enabled only after supported-version
endpoint, coarse-graining, and generated-coordinate behavior is established.
The frontend MUST reject a selection it cannot map and verify under that
contract before external execution. It SHALL preserve the accepted physical
placement of retained material and MUST NOT invent a crop-origin shift,
rounding rule, physical tolerance, or coordinate correction.

#### Scenario: Established supported crop

- **WHEN** selected pixel and slice ranges satisfy the established tool contract
- **THEN** generated counts, retained extent, and downstream position agree with
  independently established expected geometry, including skipped leading slices

#### Scenario: Unresolved external behavior

- **WHEN** range or output-coordinate behavior is not established
- **THEN** non-default conversion remains unavailable with a clear reason

### Requirement: Original Source and Selection Evidence

The frontend SHALL retain ALL original CT and RT Plan snapshots and existing
integrity checks. It SHALL record effective bounds separately in
`ct2phits_input.clipping` and `ct2phits_input.slice_range`. It MUST NOT
renumber a source subset, rewrite original geometry/identities, or substitute
cropped counts/origin for source-series evidence. Clipping MUST NOT replace
existing accelerator mutual-exclusion or field-size safety guards.

#### Scenario: Cropped handoff

- **WHEN** a selected box completes conversion and preparation
- **THEN** input/manifest bounds agree, complete source snapshots retain original
  hashes and geometry, and existing safety and coordinate-binding checks apply

#### Scenario: Full-volume compatibility

- **WHEN** bounds are omitted or explicitly cover the complete source
- **THEN** current input behavior, coarse graining `8 8 2`, coordinate mode
  `1`, and frozen-reference handoff remain unchanged
