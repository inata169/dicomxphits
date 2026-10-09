# CT Pixel Clipping Specification

## Purpose

Define manual source-voxel selection, retained CT geometry, and evidence required before a clipped CT2PHITS result is accepted.

## Requirements

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
- **THEN** the requested box includes both endpoints and every source voxel
  between them; conversion coverage is reported separately

#### Scenario: Invalid range

- **WHEN** a supplied range is incomplete, noninteger, reversed, or out of bounds
- **THEN** the system rejects it without silent rounding, swapping, or clamping

### Requirement: Verified Clipped Geometry Contract

CT2PHITS conversion SHALL accept equal positive integer X/Y factors and a Z
factor from `1` through `4` that yield at least one complete voxel on each
selected axis. The frontend MUST independently
verify generated geometry and material identity before accepting a non-default
or clipped output. It SHALL preserve the accepted physical
placement of retained material and MUST NOT invent a crop-origin shift,
rounding rule, physical tolerance, or coordinate correction.

#### Scenario: Established supported crop

- **WHEN** selected pixel and slice ranges satisfy the established tool contract
- **THEN** generated counts, retained extent, and downstream position agree with
  independently established expected geometry, including skipped leading slices

#### Scenario: Incomplete high-end coarse groups

- **WHEN** a clipped selection with valid factors contains an incomplete high-end
  group on any axis and at least one complete group on every axis
- **THEN** the GUI warns before conversion, the frontend reports the exact lost
  source counts and retained bounds, and conversion proceeds without changing
  the requested bounds

#### Scenario: No complete coarse group

- **WHEN** a clipped selection has fewer source indices than its factor on any
  axis
- **THEN** the frontend rejects it before workspace creation because no output
  voxel can be produced on that axis

#### Scenario: External output cannot be verified

- **WHEN** the external tool fails or output geometry/materials cannot be
  independently verified
- **THEN** the conversion is not accepted and the reason is recorded

### Requirement: Original Source and Selection Evidence

The frontend SHALL retain ALL original CT and RT Plan snapshots and existing
integrity checks. It SHALL record requested bounds in
`ct2phits_input.clipping` and `ct2phits_input.slice_range`, and actual retained
source bounds separately. It MUST NOT
renumber a source subset, rewrite original geometry/identities, or substitute
cropped counts/origin for source-series evidence. Clipping MUST NOT replace
existing accelerator mutual-exclusion or field-size safety guards.

#### Scenario: Cropped handoff

- **WHEN** a selected box completes conversion and preparation
- **THEN** input/manifest bounds agree, complete source snapshots retain original
  hashes and geometry, the full-series origin remains source evidence, and the
  selected first frozen slice provides the placement origin

#### Scenario: Downstream 3D-CRT preparation

- **WHEN** a clipped CT2PHITS result is used to prepare the public 3D-CRT
  workspace
- **THEN** the preparation verifies the completed frontend evidence and frozen
  selected slice, uses the same placement origin, and retains the full-series
  origin as source-series evidence

#### Scenario: Full-volume compatibility

- **WHEN** bounds and coarse-graining factors are omitted or explicitly equal
  the complete source and `8 8 2` defaults
- **THEN** current input behavior, coarse graining `8 8 2`, coordinate mode
  `1`, and frozen-reference handoff remain unchanged
