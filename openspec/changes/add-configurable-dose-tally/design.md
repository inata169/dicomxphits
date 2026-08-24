# Design: Configurable 3D Dose Tally Mesh

## Context

The current public runtime renderer creates two separate `[ T-Deposit ]`
sections:

1. a 3D dose grid with 101 bins on each axis; and
2. a central-axis PDD tally with one transverse bin and the existing fixed
   longitudinal sampling.

The 3D grid currently uses these PHITS bin edges and counts:

| Axis | PHITS edges (cm) | Count | Voxel centres (mm) |
| --- | --- | ---: | --- |
| x | `-15.15` to `15.15` | 101 | `-150` to `150` |
| y | `-15.15` to `15.15` | 101 | `-150` to `150` |
| z | `-10.15` to `20.15` | 101 | `-100` to `200` |

The existing downstream contract already treats PHITS tally minima and maxima
as bin edges, requires a common mesh across active segment outputs, and derives
final RTDOSE placement from the accepted Sumtally output's actual mesh and the
frozen-plan isocentre. This change should supply configurable upstream mesh
generation without replacing those independent downstream checks.

## Goals

- Provide one general, versioned calculation configuration for regular 3D dose
  tally meshes.
- Make millimetre voxel centres and voxel sizes the user-facing contract.
- Derive PHITS centimetre edges and integer bin counts deterministically.
- Preserve the legacy no-config path and existing public physics contracts.
- Reject invalid or unsafe meshes before workspace mutation or external
  execution.
- Bind one effective mesh to every active segment in a workspace.
- Preserve actual-output-based Sumtally and RTDOSE geometry validation.

## Non-Goals

- An ArcCHECK-specific mode, vendor claim, or named preset.
- A preset catalogue or automatic phantom/device detection.
- Arbitrary PHITS tally text, additional tally keys, multiple 3D meshes, or a
  general PHITS input escape hatch.
- Changing the central-axis PDD tally.
- Changing machine geometry, source spectra, transport physics, dose factors,
  MU semantics, Sumtally normalization, or DICOM coordinate transforms.
- Rewriting an existing prepared workspace in place.
- A GUI mesh editor, visualization, or broader guided-workflow redesign.
- Applying this option to the separate CT calibration-package preparation
  workflow in this first change; that workflow continues to use its reviewed
  default tallies.
- Real external-tool or real-data validation.

## Decisions

### 1. Use an independent calculation configuration

The first schema is a closed, versioned object:

```json
{
  "$schema": "dicomxphits.calculation.schema.json",
  "schema_version": "dicomxphits_public_calculation_config_v1",
  "dose_tally_3d": {
    "center_min_mm": [-150.0, -150.0, -100.0],
    "center_max_mm": [150.0, 150.0, 200.0],
    "voxel_size_mm": [3.0, 3.0, 3.0]
  }
}
```

`schema_version` and `dose_tally_3d` are required. `$schema` is optional editor
metadata. Unknown root and `dose_tally_3d` fields are rejected. Each vector
contains exactly three JSON numbers ordered as x, y, z; booleans and numeric
strings are not numbers for this contract.

Machine configuration describes the beam-producing model and is part of the
approved public dose-factor binding. The dose tally mesh describes where and
how densely a calculation samples deposited dose. Separating them prevents a
sampling-only change from modifying or invalidating the machine-model hash and
allows one machine configuration to be used with more than one calculation
mesh.

The calculation configuration does not authorize a different machine model,
calibration, geometry mode, or physics setting. Supplying both files applies
each only to its own validated responsibility.

### 2. Treat centre endpoints as inclusive user intent

For axis `a`, let:

- `c_min_a` be `center_min_mm[a]`;
- `c_max_a` be `center_max_mm[a]`; and
- `s_a` be `voxel_size_mm[a]`.

`c_min_a` and `c_max_a` are the centres of the first and final voxels, not bin
edges. The regular grid is valid only when:

```text
c_min_a < c_max_a
s_a > 0
k_a = (c_max_a - c_min_a) / s_a is an integer
```

The derived count and bin edges are:

```text
n_a            = k_a + 1
edge_min_mm_a  = c_min_a - s_a / 2
edge_max_mm_a  = c_max_a + s_a / 2
edge_min_cm_a  = edge_min_mm_a / 10
edge_max_cm_a  = edge_max_mm_a / 10
```

This convention lets users describe the voxel locations they intend, avoids
the half-voxel arithmetic and centimetre conversion in user files, and matches
the existing RTDOSE bin-centre contract exactly.

For the built-in default, x and y produce `n = 101` and edges
`-15.15 cm` to `15.15 cm`; z produces `n = 101` and edges `-10.15 cm`
to `20.15 cm`. A generic symmetric z centre range of `-150 mm` to `150 mm`
with `3 mm` voxels likewise produces 101 bins and edges `-15.15 cm` to
`15.15 cm`, without introducing a device-specific preset.

### 3. Use decimal semantics for grid construction

Configuration numbers will be interpreted from their JSON decimal spelling,
not rounded through binary floating-point before divisibility is decided. The
loader will use exact decimal arithmetic for subtraction, division, half-voxel
edge construction, and millimetre-to-centimetre conversion.

`k_a` must have no fractional part in that arithmetic. The implementation will
not silently round a near-integer quotient or add a tolerance that changes the
requested centre coordinates. Canonical plain-decimal PHITS values and integer
counts will be rendered from the validated result. Existing downstream tally
parsing and its approved geometry comparison remain authoritative for actual
outputs.

This supports ordinary JSON decimal and exponent notation while rejecting
non-JSON values such as NaN and Infinity. The schema and semantic validator
both participate, but the semantic validator remains mandatory because JSON
Schema alone cannot prove exact grid divisibility or safe voxel products.

### 4. Validate fail-closed before workspace mutation

The complete calculation configuration is loaded and semantically validated
before the preparation stage creates or modifies workspace artifacts. It
rejects:

- an unreadable file, malformed JSON, wrong or missing schema version, missing
  field, unknown field, wrong vector length, boolean, or numeric string;
- any non-finite value;
- `center_min_mm[a] >= center_max_mm[a]`;
- `voxel_size_mm[a] <= 0`;
- a centre span that is not an exact integer multiple of the voxel size;
- a derived count outside the supported positive PHITS integer range;
- more than 1,000 bins on any axis; or
- more than 10,000,000 total voxels, with checked multiplication used before
  allocating or rendering mesh-sized data.

The per-axis and total limits are conservative public v1 guardrails rather
than claims about the maximum capability of PHITS. They accept both the legacy
and example symmetric 101-cube meshes. Raising them later requires evidence
and a separately reviewed contract change; a user cannot bypass them with raw
PHITS text.

Validation failure produces a controlled error and no PHITS, Sumtally, or
RTDOSE execution. No partial fallback to the default or to a per-axis subset is
allowed when a configuration was explicitly supplied.

### 5. Make the omitted configuration exactly backward compatible

The workspace-preparation API and CLI gain an optional calculation-config path.
When omitted, they construct one built-in normalized calculation configuration
whose derived 3D T-Deposit block matches the current geometry:

```text
xmin/xmax/nx = -15.15 / 15.15 / 101
ymin/ymax/ny = -15.15 / 15.15 / 101
zmin/zmax/nz = -10.15 / 20.15 / 101
```

The no-config path must retain the current rendered 3D tally block byte for
byte, including the existing output role and other non-mesh tally settings.
Regression tests will compare this path with the pre-change rendering.

An explicitly supplied invalid configuration never falls back to the default.
Changing a selected path after preparation does not rewrite an existing
workspace; a new workspace preparation is required.

Preparation evidence distinguishes `built_in_legacy_default` from
`user_supplied`. It records the raw user file SHA-256 when present and a
canonical semantic digest over the schema version, centre vectors, voxel-size
vector, derived counts, and derived edges. `$schema` editor metadata is not
part of the semantic digest.

### 6. Bind one mesh across all active segments

The calculation configuration is loaded once at the workspace boundary. One
immutable normalized mesh value is passed to every active segment renderer;
there is no per-beam or per-segment override. The preparation summary records
that common value and its digest, and each generated segment's evidence binds
to the same digest.

Preparation fails before publishing a prepared workspace if any generated
active segment does not contain the exact derived 3D tally geometry. Existing
segment output paths and the separate PDD output role are unchanged.

The omitted-config path retains the current 3D tally title exactly. On a
custom-mesh path, the renderer generates a factual title from the validated
derived counts and voxel sizes so it does not continue to claim
`101x101x101` or `3 mm` when those values differ. The schema accepts no
user-supplied PHITS title.

### 7. Keep actual tally output authoritative downstream

The calculation configuration is generation intent and provenance, not proof
of external output geometry. Sumtally continues to parse the actual active
segment tally outputs and fail when their complete supported mesh geometry is
missing, ambiguous, or unequal. It does not reconcile inconsistent outputs by
choosing the configuration or the first segment.

RTDOSE Prepare and Run continue to derive and verify placement from the exact
accepted Sumtally/PHITS tally output, frozen-plan isocentre, and existing
PHITS/IEC-to-DICOM mapping. They do not calculate final DICOM geometry directly
from the calculation configuration. The optional recorded configuration
binding may be cross-checked as additional provenance, but cannot replace or
weaken the existing output-based geometry consistency and digest gates.

This preserves support for asymmetric bounds and anisotropic spacing already
covered by the current RTDOSE geometry contract.

### 8. Keep the PDD tally independent

The existing implementation shares some constants and rendering code between
the 3D grid and the central-axis PDD tally. The implementation will separate
the 3D mesh arguments at that boundary so only the first 3D `[ T-Deposit ]`
section consumes `dose_tally_3d`.

The PDD transverse bounds, one-bin transverse counts, longitudinal bounds and
count, reference depth, output filename, Sumtally include behavior, and title
remain unchanged even when the configurable 3D z range or voxel size differs.
No `dose_tally_pdd` key is accepted in schema v1.

### 9. Add only a minimal GUI handoff

The Workspace page gains one optional `Calculation config` path field and
Browse action near the existing optional machine configuration. A blank value
omits the CLI option and selects the legacy default. A nonblank value must
resolve to an existing regular file and is passed as one CLI argument; the
canonical calculation-config loader performs full semantic validation before
workspace mutation.

The GUI will not expose nine numeric mesh cells, PHITS edges, raw tally text,
device names, presets, or automatic selection. The selected path is not added
to persistent GUI settings in this first change, which keeps the new path
explicit for each new workspace and limits migration work. Downstream stage
commands do not receive the calculation-config path because they consume the
prepared workspace evidence and actual outputs.

### 10. Leave a narrow path for future presets

The normalized mesh representation and loader are independent of the GUI and
machine model. A future approved preset catalogue could produce the same
three centre/size vectors and then pass through the identical validator and
provenance path.

Schema v1 does not accept a `preset` key and the GUI contains no device-specific
labels. This avoids prematurely defining vendor compatibility or allowing a
preset to bypass explicit mesh validation. Future preset support would require
a new schema version or OpenSpec delta.

## Validation Strategy

1. Validate the public example and built-in default through the same semantic
   validator and prove they normalize to the same mesh.
2. Prove the legacy no-config 3D tally block remains byte-for-byte unchanged.
3. Test exact conversion for asymmetric and anisotropic synthetic meshes,
   including the symmetric 101-cube example.
4. Reject malformed JSON, schema mismatches, unknown keys, wrong vector sizes,
   booleans, strings, non-finite values, reversed/equal ranges, non-positive
   sizes, fractional grid steps, per-axis overflow, and total-voxel overflow.
5. Prove validation happens before any workspace artifact is created or
   modified.
6. Prove every active segment receives one identical mesh and configuration
   digest and that no per-segment override exists.
7. Prove the PDD tally is identical with and without a custom 3D mesh.
8. Retain and extend synthetic Sumtally and RTDOSE tests proving mismatched
   actual outputs fail and accepted output geometry, rather than configuration
   intent, controls RTDOSE placement.
9. Test blank, valid, missing, directory, and space-containing GUI paths and
   prove downstream commands do not receive the new option.
10. Run focused tests and the full public validation suite without external
    scientific tools or real DICOM.

## Risks and Mitigations

- **Half-voxel or unit errors move the final grid.** Specify inclusive centre
  endpoints and exact formulae, use decimal arithmetic, and test asymmetric,
  anisotropic examples independently.
- **A refactor changes the public default.** Keep a built-in legacy default and
  byte-level regression coverage for the rendered 3D tally block.
- **Segments are prepared with different meshes.** Load once, pass an immutable
  normalized value, bind its digest, and keep actual-output equality checks.
- **A huge grid consumes excessive memory, disk, or parser time.** Enforce
  checked per-axis and total-voxel limits before workspace mutation.
- **Configuration evidence masks changed external output.** Preserve actual
  PHITS/Sumtally output as downstream geometry authority.
- **Changing 3D z sampling accidentally changes PDD.** Separate renderer inputs
  and assert the complete PDD block is unchanged.
- **A generic feature is read as vendor validation.** Ship no device preset or
  compatibility claim and retain the education/research boundary.

## Rollback

Before acceptance, rollback is a normal revert of the calculation-config
loader, optional handoff, rendering parameter, evidence, tests, documentation,
and OpenSpec delta. Existing workspaces remain unchanged. No migration or
external artifact rewrite is required because the feature applies only while
preparing a new workspace.
