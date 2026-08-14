# IEC Gantry Geometry Specification

## Purpose

Define IEC-consistent PHITS source and accelerator geometry for DICOM Gantry
Angles in the public HFS, couch-zero fixed-field workflow, including safe
provenance and recalculation boundaries.

## Requirements

### Requirement: DICOM Gantry Angles Shall Produce IEC-Consistent Patient Axes

For the public HFS, couch-zero workflow, DICOM Gantry Angle `g` SHALL define IEC-consistent patient-axis geometry. A
positive source-axis distance `S` centimetres and isocenter `I` SHALL produce
PHITS source position `q = (-S sin(g), 0, -S cos(g))` and unit beam direction
`d = (sin(g), 0, cos(g))`.

Under the accepted mapping
`P_DICOM_mm(p) = I + 10 * (-p_x, p_z, p_y)`, the source offset SHALL be
`10 * (S sin(g), -S cos(g), 0)` millimetres and the patient-coordinate beam
direction SHALL be `(-sin(g), cos(g), 0)` in DICOM LPS coordinates.

#### Scenario: Cardinal gantry angles

- **WHEN** synthetic source geometry is evaluated at gantry 0, 90, 180, and
  270 degrees with `S = 100 cm`
- **THEN** its DICOM LPS source offsets are respectively `(0, -1000, 0)`,
  `(+1000, 0, 0)`, `(0, +1000, 0)`, and `(-1000, 0, 0)` millimetres
- **AND** its DICOM LPS beam directions are respectively `(0, +1, 0)`,
  `(-1, 0, 0)`, `(0, -1, 0)`, and `(+1, 0, 0)`

#### Scenario: Nonzero oblique gantry angles

- **WHEN** synthetic source geometry is evaluated at gantry 45 and 315 degrees
- **THEN** the source and beam lateral components follow the IEC-consistent
  sine signs independently of maintained renderer output
- **AND** the mapped beam direction remains a unit vector toward isocenter

### Requirement: Source and Accelerator Transform Shall Share One Central Axis

The PHITS source and accelerator `tr3` SHALL implement one mutually consistent
geometry. The source SHALL
be `S` centimetres upstream of isocenter, its unit direction SHALL reach
isocenter after distance `S`, and `tr3` SHALL map the accelerator local `+Z`
beam axis and local `(0, 0, -S)` source point to those same global vectors.

The implementation MUST NOT correct only the source or only `tr3`.

#### Scenario: Cardinal and oblique transform consistency

- **WHEN** source and accelerator geometry is generated for each required
  cardinal and oblique anchor angle
- **THEN** source position plus `S` times source direction equals isocenter
- **AND** transformed local beam-axis and source-point vectors equal the
  independently calculated PHITS vectors

#### Scenario: Partial correction would separate the beam geometry

- **WHEN** a source or transform candidate does not share the same central
  axis and IEC-consistent gantry sign
- **THEN** synthetic validation rejects the candidate before PHITS execution

### Requirement: Gantry Zero Shall Remain Unchanged

The gantry-direction correction SHALL leave gantry-zero source position,
source direction, accelerator transform, source spectrum, aperture geometry,
transport settings, and isocenter central axis unchanged.

#### Scenario: Existing gantry-zero geometry is regenerated

- **WHEN** a supported gantry-zero segment is rendered under the corrected
  contract
- **THEN** its source remains at `(0, 0, -S)` in PHITS coordinates and points
  along `+Z` to isocenter
- **AND** no unrelated physics or runtime field changes

### Requirement: Incorrect Nonzero-Gantry Transport Shall Require Recalculation

The corrected gantry geometry SHALL carry explicit provenance sufficient to
distinguish it from the prior reversed convention. Existing PHITS transport
evidence produced for any nonzero gantry angle under the prior convention MUST
NOT be accepted as corrected transport. Ambiguous or mixed legacy evidence
MUST fail closed.

An affected workflow SHALL regenerate segment inputs and rerun PHITS,
Sumtally, and RTDOSE. It MUST NOT mirror or relabel only the final DICOM as a
substitute for transport recalculation.

#### Scenario: Prior nonzero-gantry workspace is reopened

- **WHEN** workspace evidence identifies PHITS results produced with the prior
  nonzero-gantry convention
- **THEN** recovery does not present those PHITS results as reusable corrected
  transport
- **AND** it requires PHITS and downstream recalculation

#### Scenario: Final RT Dose alone is available

- **WHEN** a final DICOM contains dose transported with the prior nonzero-angle
  geometry
- **THEN** no PixelData mirror, affine rewrite, or coordinate relabel is
  accepted as repair

#### Scenario: Proven all-zero-gantry legacy workspace

- **WHEN** bounded provenance proves every active segment used gantry zero and
  its generated geometry is unchanged by the corrected contract
- **THEN** the workflow may retain that transport evidence without implying
  that nonzero or ambiguous legacy evidence is reusable

### Requirement: Gantry Correction Shall Preserve Separate Dose and DICOM Contracts

The gantry-direction correction SHALL NOT change the accepted
PHITS-to-DICOM LPS tally mapping, final RTDOSE voxel mapping, stored or physical
dose values, `DoseGridScaling`, `DoseUnits`, PLAN-versus-fraction semantics,
MU, Sumtally normalization, public dose factors, source spectrum, field-size
guard, or aperture model.

#### Scenario: Corrected transport contract is reviewed

- **WHEN** the implementation diff is inspected
- **THEN** its behavioral change is limited to IEC gantry geometry and stale
  affected-transport handling
- **AND** dose semantics and final DICOM coordinate processing remain outside
  the change

### Requirement: Gantry Validation Shall Use Synthetic Repository Evidence

Automated validation SHALL use mathematical fixtures, synthetic plans,
temporary workspaces, and fake or mock runners. It MUST NOT run or load real
PHITS, Sumtally, phits2dicom, GPR, real DICOM, or calculation outputs.

Any external recalculation or comparison after implementation SHALL require a
separate explicit human approval and SHALL remain outside the repository's
protected-data boundary.

#### Scenario: Repository coordinate regression test

- **WHEN** source, transform, patient-axis, or stale-evidence behavior is
  tested automatically
- **THEN** only synthetic repository-safe evidence is used
- **AND** no external scientific executable or real workflow data is required
