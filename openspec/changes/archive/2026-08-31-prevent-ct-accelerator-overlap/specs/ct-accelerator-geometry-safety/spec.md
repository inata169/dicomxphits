# ct-accelerator-geometry-safety Delta

## ADDED Requirements

### Requirement: CT and Accelerator Regions Shall Be Mutually Exclusive

Every generated public fixed-field PHITS segment SHALL compose the CT wrapper
and complete transformed accelerator envelope so that they do not own the same
positive-volume region. Inside their geometric intersection, accelerator
geometry SHALL take precedence. Outside that intersection, the CT wrapper
SHALL retain its complete voxel fill, coordinate mapping, bounds, and material
semantics.

The workflow MUST NOT implement this invariant by cropping the CT, imposing a
fixed FOV threshold, moving the isocentre, changing SAD or SSD, narrowing the
source cone, or changing the accelerator, jaw, MLC, physics, tally, dose, MU,
or normalization contracts.

#### Scenario: CT wrapper intersects the transformed accelerator

- **WHEN** a synthetic CT wrapper has positive-volume intersection with the
  complete transformed accelerator envelope
- **THEN** the generated PHITS geometry assigns the intersection to the
  accelerator and excludes it from the CT wrapper
- **AND** CT voxel ownership outside the accelerator envelope is unchanged

#### Scenario: CT wrapper and accelerator are disjoint

- **WHEN** a synthetic CT wrapper does not intersect the transformed
  accelerator envelope
- **THEN** old and corrected material-region ownership is transport-equivalent
  despite the explicit exclusion in the corrected CSG

### Requirement: Overlap Prevention Shall Use Complete Transformed Geometry

Overlap prevention SHALL use the complete three-dimensional CT bounds,
isocentre placement, and supported accelerator transform. It MUST NOT infer
safety from transverse FOV, field size, gantry angle, or collimator angle alone.

#### Scenario: Equal FOVs have different upstream extent

- **WHEN** two synthetic CT volumes have the same transverse FOV but different
  isocentre-relative positions or beam transforms
- **THEN** each volume's relationship to the accelerator is determined from
  its own complete transformed geometry
- **AND** no fixed FOV-only rule decides whether the geometry is safe

#### Scenario: Nonzero gantry rotates the relationship

- **WHEN** synthetic CT and accelerator regions are evaluated at a supported
  nonzero gantry angle
- **THEN** mutual exclusion follows the transformed accelerator envelope
  rather than an untransformed axial approximation

### Requirement: Geometry Safety Validation Shall Use Synthetic Evidence

Automated geometry validation SHALL use synthetic bounds, transforms, rendered
inputs, analytical samples, and fake or mock tool boundaries. It MUST NOT load
real DICOM or calculation results or execute external scientific tools.

#### Scenario: Repository overlap regression

- **WHEN** compact, large, displaced, touching, overlapping, or rotated
  geometry is tested automatically
- **THEN** only repository-safe synthetic evidence is used
- **AND** no external PHITS-family, Sumtally, phits2dicom, or GPR execution is
  required
