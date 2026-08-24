# Configurable Dose Tally Delta

## ADDED Requirements

### Requirement: Independent Versioned Calculation Configuration

Public fixed-field 3D-CRT workspace preparation SHALL accept an optional
versioned calculation configuration independently of the machine
configuration. Schema version `dicomxphits_public_calculation_config_v1` SHALL
contain exactly one supported calculation section, `dose_tally_3d`, with
three-element x/y/z JSON-number vectors named `center_min_mm`,
`center_max_mm`, and `voxel_size_mm`; optional `$schema` editor metadata MAY
also be present. Unknown fields, booleans, numeric strings, missing fields, and
unsupported schema versions MUST be rejected.

The calculation configuration MUST NOT alter the machine model, its
calibration binding, source or accelerator physics, geometry mode, MU or dose
normalization, DICOM coordinate transform, or public fixed-field 3D-CRT scope.

#### Scenario: Independent machine and calculation files

- **WHEN** workspace preparation receives valid machine and calculation
  configuration paths
- **THEN** the machine file controls only its existing beam-model contract and
  the calculation file controls only the supported 3D tally mesh
- **AND** a tally-only choice does not change the machine-configuration digest
  used by the approved dose-factor gate

#### Scenario: Unsupported calculation field

- **WHEN** a calculation configuration contains an unknown root or
  `dose_tally_3d` field, including raw PHITS tally text or a preset name
- **THEN** preparation rejects the configuration instead of ignoring or
  executing the unsupported content

### Requirement: Inclusive Voxel-Centre Mesh Derivation

For each x/y/z axis, workspace preparation SHALL interpret
`center_min_mm` and `center_max_mm` as the inclusive first and final voxel
centres in millimetres and `voxel_size_mm` as their positive regular spacing.
It SHALL derive `n = (center_max_mm - center_min_mm) / voxel_size_mm + 1`, the
lower bin edge `(center_min_mm - voxel_size_mm / 2) / 10` centimetres, and the
upper bin edge `(center_max_mm + voxel_size_mm / 2) / 10` centimetres. It SHALL
render those counts and edges into the 3D PHITS T-Deposit mesh without asking
the user to supply PHITS bin edges or arbitrary tally syntax.

Grid divisibility and derivation MUST use the exact decimal values represented
by the JSON numbers. The quotient before adding one MUST be an integer; the
implementation MUST NOT round a near-integer quotient or silently alter a
requested centre or voxel size.

#### Scenario: Existing asymmetric-z default is derived

- **WHEN** the centre minima are `[-150, -150, -100]` mm, centre maxima are
  `[150, 150, 200]` mm, and voxel sizes are `[3, 3, 3]` mm
- **THEN** x and y use edges `-15.15` to `15.15` cm, z uses edges `-10.15` to
  `20.15` cm, and all three axes use 101 bins

#### Scenario: Generic symmetric mesh is derived

- **WHEN** all centre minima are `-150` mm, all centre maxima are `150` mm,
  and all voxel sizes are `3` mm
- **THEN** every axis uses edges `-15.15` to `15.15` cm and 101 bins without
  assigning a device-specific meaning to that mesh

#### Scenario: Anisotropic regular mesh is derived

- **WHEN** each axis has finite ordered centre endpoints and its centre span is
  an exact integer multiple of its positive voxel size
- **THEN** each axis receives its independently derived positive count and
  half-voxel-expanded centimetre edges

### Requirement: Fail-Closed Mesh Validation and Resource Limits

The calculation-config validator SHALL reject non-finite values,
`center_min_mm >= center_max_mm`, `voxel_size_mm <= 0`, a centre span that is
not an exact integer multiple of the voxel size, more than 1,000 derived bins
on any axis, or more than 10,000,000 total voxels. Total-count calculation
MUST be checked before allocating or rendering mesh-sized data. A supplied
invalid configuration MUST fail before any workspace artifact is created or
modified and MUST NOT fall back wholly or partially to the default.

Before parsing or rendering, the validator SHALL reject a calculation-config
file larger than 65,536 bytes, any JSON numeric token longer than 64 ASCII
characters, any source number whose canonical plain-decimal representation
would exceed 64 ASCII characters, or any derived PHITS edge or spacing whose
canonical plain-decimal token would exceed 64 ASCII characters. It MUST
determine each source token's canonical length from its lexical coefficient
and exponent before decimal arithmetic, and each derived token's length from
bounded decimal metadata, without first materializing an oversized expansion.
Every derived PHITS edge and spacing MUST convert to a finite binary64 value
compatible with the existing downstream tally parser while preserving strict
minimum-to-maximum ordering and positive spacing. Failure of any representation
or compatibility guard MUST occur before workspace mutation or external
execution.

#### Scenario: Reversed or empty centre interval

- **WHEN** any axis has its minimum centre greater than or equal to its maximum
  centre
- **THEN** preparation fails before workspace mutation or external execution

#### Scenario: Non-positive or non-finite value

- **WHEN** any voxel size is zero or negative or any mesh value is non-finite
- **THEN** preparation fails closed without rendering a PHITS input

#### Scenario: Fractional number of centre steps

- **WHEN** an axis centre span divided by its voxel size has a fractional part
- **THEN** preparation rejects the mesh without rounding, clipping, or moving
  an endpoint

#### Scenario: Resource-unsafe mesh

- **WHEN** any derived axis count exceeds 1,000 or their product exceeds
  10,000,000
- **THEN** preparation rejects the mesh before workspace mutation or mesh-sized
  allocation

#### Scenario: Compact exponent would expand excessively

- **WHEN** a short JSON exponent value such as `1e100000000` would have a
  canonical plain-decimal source representation longer than 64 ASCII
  characters
- **THEN** validation rejects it from its lexical coefficient and exponent
  before decimal arithmetic or materializing the expanded token

#### Scenario: Source representation is oversized

- **WHEN** the calculation-config file exceeds 65,536 bytes or any numeric
  token exceeds 64 ASCII characters
- **THEN** validation rejects it before unbounded parsing or rendering

#### Scenario: Derived geometry is incompatible with downstream binary64

- **WHEN** a derived edge or spacing converts to a non-finite binary64 value or
  binary64 conversion loses strict edge ordering or positive spacing
- **THEN** preparation rejects the mesh before PHITS input generation

### Requirement: Legacy Default Geometry Preservation

When no calculation configuration is supplied, workspace preparation SHALL use
the current public 3D dose tally geometry: x/y centre ranges `-150 mm` through
`150 mm`, z centre range `-100 mm` through `200 mm`, `3 mm` voxel size on each
axis, 101 bins on each axis, and PHITS edges `[-15.15, 15.15]`,
`[-15.15, 15.15]`, and `[-10.15, 20.15]` centimetres. The complete legacy 3D
T-Deposit block, including its non-mesh settings and output role, SHALL remain
byte-for-byte unchanged on the omitted-config path.

An explicitly supplied configuration applies only while preparing a new
workspace and MUST NOT rewrite an existing prepared workspace when the path or
file later changes.

#### Scenario: Calculation configuration is omitted

- **WHEN** a caller uses the existing workspace-preparation interface without
  a calculation configuration
- **THEN** every active segment retains the pre-change 3D T-Deposit block and
  geometry

#### Scenario: Explicit invalid file does not become default

- **WHEN** a caller explicitly supplies an unreadable or invalid calculation
  configuration
- **THEN** preparation fails and does not continue with the legacy default

### Requirement: One Evidence-Bound Mesh Per Workspace

Workspace preparation SHALL load and normalize one effective calculation
configuration before rendering active segments and SHALL apply the identical
3D tally mesh to every active segment. It MUST NOT accept per-beam or
per-segment mesh overrides. Preparation evidence SHALL record whether the
source was the built-in legacy default or user supplied, the source-file
SHA-256 when supplied, the normalized centre and size vectors, derived counts
and edges, and a canonical semantic digest bound to every active segment.

Preparation MUST fail before publishing success when any generated active
segment lacks or differs from that effective 3D mesh.
The omitted-config path SHALL retain the existing 3D tally title. A custom-mesh
path SHALL use only renderer-generated, validated mesh facts in its title and
MUST NOT accept user-supplied PHITS title text.

#### Scenario: Multi-segment workspace is prepared

- **WHEN** a valid calculation configuration is used for a workspace with
  multiple active segments
- **THEN** every segment contains the same derived 3D mesh and binds the same
  canonical calculation-geometry digest

#### Scenario: Generated segment mesh differs

- **WHEN** any generated active segment does not match the one normalized
  workspace mesh
- **THEN** workspace preparation fails rather than publishing mixed geometry

#### Scenario: Custom dimensions differ from the legacy title

- **WHEN** a valid custom mesh does not have 101 bins and 3 mm spacing on every
  axis
- **THEN** its renderer-generated title describes the effective validated mesh
  without retaining a false legacy size or accepting user-authored title text

### Requirement: Actual-Output Geometry Remains Authoritative Downstream

Sumtally SHALL continue to parse the actual active-segment PHITS tally outputs
and require their complete supported mesh geometries to match before accepting
a combined dose. A calculation configuration or preparation summary MUST NOT
substitute for missing actual geometry or reconcile mismatched output meshes.

RTDOSE preparation, coordinate correction, and completion validation SHALL
continue to derive final dose placement from the accepted actual PHITS and
Sumtally tally geometry, the frozen-plan isocentre, and the existing reviewed
coordinate mapping. They MUST NOT use calculation-config intent as the sole
source of final RTDOSE geometry or weaken existing geometry/digest consistency
checks.

#### Scenario: Actual segment outputs disagree despite common intent

- **WHEN** active segment outputs contain different tally bounds or counts even
  though preparation recorded one calculation configuration
- **THEN** Sumtally fails closed instead of trusting the configuration or
  selecting one output mesh

#### Scenario: RTDOSE consumes a custom accepted mesh

- **WHEN** Sumtally accepts matching active outputs produced with a valid
  custom 3D mesh
- **THEN** RTDOSE placement is derived and validated from that accepted output
  mesh using the existing bin-edge, bin-centre, axis, and isocentre contracts

#### Scenario: Configuration and output evidence disagree

- **WHEN** recorded calculation intent is missing, stale, or inconsistent with
  the actual accepted output geometry
- **THEN** downstream processing fails according to the existing provenance
  and geometry gates rather than replacing actual geometry with config values

### Requirement: PDD Tally Preservation

The configurable 3D dose mesh SHALL affect only the 3D dose T-Deposit section.
The existing PDD tally's transverse bounds and counts, longitudinal bounds and
count, voxel spacing, reference depth, title, output role, and Sumtally include
behavior MUST remain unchanged for both the omitted-config and custom-3D-mesh
paths. Schema v1 MUST NOT accept a PDD mesh setting.

#### Scenario: Custom 3D z range is selected

- **WHEN** a valid calculation configuration changes the 3D z centre range or
  voxel size
- **THEN** the PDD T-Deposit block remains identical to the pre-change block

### Requirement: Synthetic Validation Boundary

Automated validation of configurable 3D dose tally behavior SHALL use
synthetic values, temporary workspaces, synthetic DICOM where needed, and fake
or mock external-tool runners. It MUST NOT run real PHITS, RT-PHITS, Sumtally,
phits2dicom, GPR, real DICOM, or facility-specific workflows.

#### Scenario: Configurable mesh integration is tested

- **WHEN** configuration, rendering, Sumtally consistency, or RTDOSE placement
  behavior is tested automatically
- **THEN** only repository-safe synthetic inputs and fake or mock runners are
  used
