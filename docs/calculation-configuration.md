# Calculation Configuration

The optional calculation configuration controls only the regular 3D PHITS
dose tally mesh created by workspace preparation. It does not change the
machine model, source spectrum, transport settings, dose factor, MU semantics,
central-axis PDD tally, Sumtally normalization, or DICOM coordinate transform.

This is education and research software for confirmed non-patient phantom
data. A custom mesh does not establish clinical commissioning, patient-specific
QA, treatment suitability, or vendor certification.

## Schema

Use the closed v1 schema in
`config/dicomxphits.calculation.schema.json`. The tracked example is
`config/dicomxphits.calculation.example.json`:

```json
{
  "$schema": "dicomxphits.calculation.schema.json",
  "schema_version": "dicomxphits_public_calculation_config_v1",
  "dose_tally_3d": {
    "center_min_mm": [-150, -150, -100],
    "center_max_mm": [150, 150, 200],
    "voxel_size_mm": [3, 3, 3]
  }
}
```

The three values in each vector are x, y, and z. They must be JSON numbers;
booleans and numeric strings are rejected. Unknown fields are rejected.
`$schema` is optional editor metadata and does not affect the semantic digest.

## Inclusive voxel-centre semantics

`center_min_mm` and `center_max_mm` are the centres of the first and last
voxels, inclusive. For each axis:

```text
count       = (center_max_mm - center_min_mm) / voxel_size_mm + 1
edge_min_cm = (center_min_mm - voxel_size_mm / 2) / 10
edge_max_cm = (center_max_mm + voxel_size_mm / 2) / 10
```

The centre span must be an exact multiple of the positive voxel size. Decimal
values are interpreted from their JSON spelling and derived with exact decimal
arithmetic. For example, centres `-1.25` through `1.25` mm at `0.25` mm
spacing produce 11 bins with PHITS edges `-0.1375` and `0.1375` cm.

When no calculation configuration is supplied, dicomxphits uses the legacy
101 x 101 x 101 mesh: x/y centres `-150` through `150` mm, z centres `-100`
through `200` mm, and 3 mm spacing. Its existing 3D tally text remains
unchanged. The separate PDD tally is unchanged for both default and custom
meshes.

## Validation limits

Workspace preparation rejects the configuration before workspace mutation if
any semantic or downstream-serialization check fails. Public v1 limits are:

- at most 65,536 bytes per configuration file;
- at most 64 ASCII characters per JSON numeric token and per canonical source
  or derived decimal;
- at most 1,000 bins on each axis;
- at most 10,000,000 total voxels;
- finite, strictly ordered binary64 edges with positive spacing; and
- DICOM Decimal String and complete RTDOSE affine compatibility within the
  existing 1e-6 mm absolute geometry tolerance.

Preparation loads one effective mesh and binds its semantic SHA-256 to every
active segment. The preparation summaries record the source kind, optional raw
file SHA-256, canonical centre and voxel-size vectors, counts, edges, semantic
digest, and RTDOSE serialization preflight.

These checks govern requested input geometry only. Actual PHITS tally output
remains authoritative downstream: Sumtally still requires complete geometry
equality across all active segment outputs, and RTDOSE placement still comes
from the accepted Sumtally output mesh. Missing, stale, ambiguous, or
inconsistent output geometry is rejected rather than replaced by configuration
metadata.

## CLI and GUI

Pass the file only while preparing a new workspace:

```powershell
dicomxphits-prepare-3dcrt-workspace `
  <other-required-options> `
  --calculation-config-path "C:\outside-repo\calculation.json"
```

In the GUI, select **Calculation config (optional)** on the Workspace page.
Leave it blank for the legacy default. The path is passed only to **Prepare
workspace**, is not passed to PHITS, Sumtally, or RTDOSE commands, and is not
saved in the first-version persistent GUI settings. Changing the selection
does not rewrite an existing workspace; prepare a new workspace instead.
