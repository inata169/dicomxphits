# IEC Gantry Geometry Specification

## Purpose

Define IEC-consistent PHITS source and accelerator geometry for DICOM Gantry
and Beam Limiting Device Angles in the public HFS, couch-zero fixed-field
workflow, including safe provenance and recalculation boundaries.
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
substitute for transport recalculation. A gantry-only compatibility argument
MUST NOT override a stricter current combined beam-geometry contract.

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

#### Scenario: Prior all-zero-gantry workspace meets the old gantry exception

- **WHEN** prior evidence proves every active segment used gantry zero but the
  current combined beam-geometry contract rejects its geometry version
- **THEN** recovery follows the stricter current contract and requires
  recalculation

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

### Requirement: DICOM Collimator Angles Shall Produce IEC-Consistent Patient Axes

For the public workflow, the DICOM Beam Limiting Device Angle `c` SHALL remain
unchanged in plan state, segment manifests, summaries, and public reporting.
The PHITS accelerator
`tr2` transform SHALL apply that value with the patient-axis collimator
rotation sign defined by this contract for head-first-supine fixed fields at
zero couch angle.

At gantry zero, the DICOM LPS MLCX and MLCY unit axes SHALL be respectively
`(cos(c), 0, sin(c))` and `(-sin(c), 0, cos(c))`. The axes SHALL remain unit
length, mutually perpendicular, and perpendicular to the central beam axis.

#### Scenario: Positive non-cardinal collimator angle

- **WHEN** synthetic accelerator geometry is evaluated at gantry zero, couch
  zero, and collimator 30 degrees
- **THEN** its DICOM LPS MLCX axis is
  `(+sqrt(3)/2, 0, +1/2)`
- **AND** its DICOM LPS MLCY axis is
  `(-1/2, 0, +sqrt(3)/2)`

#### Scenario: Cardinal collimator angles

- **WHEN** synthetic accelerator geometry is evaluated at collimator 0, 90,
  180, and 270 degrees with gantry and couch zero
- **THEN** the DICOM LPS MLCX axes are respectively `(1, 0, 0)`, `(0, 0, 1)`,
  `(-1, 0, 0)`, and `(0, 0, -1)`
- **AND** the DICOM LPS MLCY axes are respectively `(0, 0, 1)`, `(-1, 0, 0)`,
  `(0, 0, -1)`, and `(1, 0, 0)`

#### Scenario: DICOM angle evidence is retained

- **WHEN** a synthetic plan carries a nonzero Beam Limiting Device Angle
- **THEN** state, interpolation, manifest, and summary evidence retain the
  DICOM value without negation or private relabeling
- **AND** only its application inside PHITS accelerator geometry uses the
  required transform convention

### Requirement: Collimator Correction Shall Preserve Other Geometry Contracts

The collimator-direction correction SHALL leave source position, source
direction, gantry `tr3`, isocenter, MLC leaf positions, jaw positions, and the
accepted PHITS-to-DICOM LPS mapping unchanged. It SHALL compose with the
current IEC gantry and MLCX patient-axis contracts without adding a second
gantry or leaf reflection.

#### Scenario: Corrected collimator transform is composed with beam geometry

- **WHEN** a synthetic segment is rendered with supported gantry and
  collimator angles
- **THEN** its source and central beam axis match the current gantry contract
- **AND** its beam-limiting axes use the corrected collimator sign
- **AND** its leaf and jaw values retain their existing meanings

#### Scenario: Collimator zero is regenerated

- **WHEN** a supported collimator-zero segment is rendered under the corrected
  contract
- **THEN** its accelerator `tr2` geometry is unchanged
- **AND** no unrelated runtime or physics field changes

### Requirement: Collimator Validation Shall Anchor Asymmetric Feature Orientation

Synthetic validation SHALL use a labeled asymmetric aperture or equivalent
feature whose patient-coordinate orientation distinguishes positive from
negative DICOM collimator rotation. Orthonormality or unlabeled axis-set
equality alone MUST NOT establish correct direction.

#### Scenario: Positive and negative rotations are compared

- **WHEN** a labeled asymmetric synthetic feature is transformed at equal
  positive and negative collimator angles
- **THEN** its DICOM LPS orientations are distinct
- **AND** the positive-angle orientation matches the independent patient-axis
  anchor rather than a maintained renderer string

### Requirement: Pre-v4 Collimator Transport Shall Require Recalculation

The corrected combined beam geometry SHALL carry explicit v4 provenance that
distinguishes it from the v3 gantry/MLCX contract. PHITS transport evidence
produced under v3 or any older geometry contract MUST NOT be accepted as
corrected transport regardless of recorded collimator angle. Missing, mixed,
or ambiguous geometry provenance MUST fail closed.

An affected workflow SHALL regenerate segment inputs and rerun PHITS,
Sumtally, and RTDOSE. It MUST NOT mirror, rotate, relabel, or rewrite only the
final DICOM as a substitute for transport recalculation.

#### Scenario: Prior v3 workspace is reopened

- **WHEN** workspace evidence identifies PHITS results produced under the v3
  geometry contract
- **THEN** recovery does not present its PHITS results as reusable v4
  transport
- **AND** it requires regenerated inputs and PHITS and downstream
  recalculation

#### Scenario: Prior v3 workspace records only collimator zero

- **WHEN** every active segment explicitly records collimator zero but the
  workspace carries the v3 geometry contract
- **THEN** recovery still rejects its PHITS evidence for v4 reuse
- **AND** it requires newly prepared v4 inputs and complete recalculation

#### Scenario: Final RT Dose alone is available

- **WHEN** a final DICOM contains dose transported with the prior nonzero
  collimator convention
- **THEN** no PixelData mirror, rotation, affine rewrite, or angle relabel is
  accepted as repair

### Requirement: Collimator Correction Shall Preserve Dose and Scope Contracts

The collimator-direction correction SHALL NOT change final RTDOSE voxel
mapping, DICOM identity, stored or physical dose values, `DoseGridScaling`,
`DoseUnits`, PLAN-versus-fraction semantics, MU, Sumtally normalization,
public dose factors, source spectrum, transport settings, supported treatment
scope, or clinical claims.

#### Scenario: Corrected transport contract is reviewed

- **WHEN** the implementation diff is inspected
- **THEN** its behavioral change is limited to collimator geometry and stale
  affected-transport handling
- **AND** dose, DICOM-output, physics, and treatment-scope contracts remain
  outside the change

### Requirement: Collimator Validation Shall Use Synthetic Repository Evidence

Automated validation SHALL use mathematical fixtures, synthetic plans,
temporary workspaces, and fake or mock runners. It MUST NOT run or load
external PHITS, Sumtally, phits2dicom, GPR, real DICOM, or calculation
results.

Any external recalculation or comparison after implementation SHALL require a
separate explicit human approval and SHALL remain outside the repository's
protected-data boundary.

#### Scenario: Repository collimator regression test

- **WHEN** transform direction, patient axes, asymmetric orientation, or stale
  evidence behavior is tested automatically
- **THEN** only synthetic repository-safe evidence is used
- **AND** no external scientific executable or real workflow data is required

### Requirement: V5 Transport Geometry Shall Bind CT and Accelerator Topology

Newly prepared public fixed-field workspaces SHALL carry one current v5
combined transport-geometry contract that includes IEC gantry, MLCX,
collimator, and mutually exclusive CT/accelerator topology semantics. The v5
identity SHALL be recorded consistently in workspace, segment, and transport
evidence.

PHITS evidence created under v4, v3, or any older contract MUST NOT be accepted
as v5 transport. Missing, mixed, or ambiguous geometry provenance MUST fail
closed. No field-size, FOV, gantry-angle, collimator-angle, or analytical
non-overlap exception SHALL permit reuse of pre-v5 transport.

#### Scenario: V4 workspace is opened after the topology correction

- **WHEN** workspace evidence identifies PHITS results produced under the v4
  gantry/MLCX/collimator contract
- **THEN** the workflow does not present those results as reusable v5 transport
- **AND** it requires newly prepared v5 inputs and PHITS and downstream
  recalculation

#### Scenario: Prior workspace appears non-overlapping

- **WHEN** a pre-v5 workspace records geometry that appears disjoint or uses
  zero gantry and collimator angles
- **THEN** the workflow still rejects its PHITS evidence for v5 reuse because
  it lacks corrected topology and geometry-clean runtime evidence

### Requirement: V5 Topology Correction Shall Preserve Independent Geometry Contracts

The v5 topology correction SHALL NOT change the existing IEC gantry or
collimator direction, source position and direction, accelerator transform,
jaw or MLC aperture, CT coordinate mapping, SAD/SSD interpretation, source
spectrum, materials, transport settings, tally definitions, MU semantics,
Sumtally normalization, or RTDOSE mapping, except that an actual overlapping
CT region is removed from accelerator ownership conflict.

#### Scenario: V5 implementation diff is reviewed

- **WHEN** the implementation and synthetic outputs are compared with v4
- **THEN** unrelated beam, DICOM, dose, and coordinate contracts remain
  unchanged
- **AND** overlapping cases are identified as corrected calculations whose
  field shape and dose may differ from invalid pre-v5 transport
