# Add Configurable 3D Dose Tally Mesh

## Why

The public fixed-field 3D-CRT workspace renderer currently embeds one 3D dose
tally mesh in code. Its voxel centres span `-150 mm` through `150 mm` on x and
y and `-100 mm` through `200 mm` on z, with `3 mm` spacing on every axis. This
is a useful backward-compatible default, but a research workspace cannot select
another regular 3D sampling region without changing source code.

The tally mesh is a calculation sampling choice, not a property of the
accelerator source, jaws, MLC, materials, or calibrated public machine model.
Putting it in the machine configuration would couple independent concerns and
could make a sampling-only change appear to alter the machine configuration
bound to the approved dose factor.

Users should specify the inclusive first and last voxel-centre coordinates and
voxel size in millimetres. They should not have to derive PHITS centimetre bin
edges such as `xmin = -15.15` or provide arbitrary PHITS tally syntax.

## What Changes

- Add an optional, versioned public calculation configuration that is separate
  from the machine configuration and contains only the supported 3D dose tally
  mesh fields in this first version.
- Accept three-axis `center_min_mm`, `center_max_mm`, and `voxel_size_mm`
  values for the 3D dose tally, with the endpoints interpreted as inclusive
  voxel centres.
- Derive each PHITS bin count and centimetre bin-edge pair deterministically
  from the validated centre range and voxel size.
- Preserve the exact existing 3D tally geometry when no calculation
  configuration is supplied.
- Reject malformed, non-finite, non-positive, non-integral-grid, unknown, or
  resource-unsafe configurations, including bounded-file or numeric-rendering
  violations and downstream binary64 incompatibility, before creating or
  modifying a workspace or launching PHITS.
- Load one effective calculation configuration per workspace preparation and
  render the same normalized 3D mesh into every active segment.
- Record the effective calculation source, normalized mesh, derived PHITS
  geometry, and binding digest in workspace preparation evidence.
- Keep the existing Sumtally mesh-consistency gate and the existing RTDOSE
  placement authority: downstream geometry continues to be read from the
  accepted PHITS/Sumtally tally output, not trusted from the configuration
  alone.
- Add one optional calculation-configuration file selector to the existing
  Workspace preparation GUI path, with no mesh editor, preset catalogue, or
  workflow redesign.
- Add synthetic unit and integration coverage and document the versioned
  calculation configuration after implementation approval.

## Impact

- Affected capabilities: new `configurable-dose-tally` capability and the
  existing `guided-gui-workflow` capability.
- Expected implementation areas after approval:
  `src/dicomxphits/prepare_3dcrt_workspace.py`, the public PHITS tally
  rendering boundary, a new calculation-config loader/validator, preparation
  evidence, and the minimal Workspace-page handoff in
  `src/dicomxphits/gui.py`.
- Expected public configuration artifacts after approval:
  `config/dicomxphits.calculation.example.json` and
  `config/dicomxphits.calculation.schema.json`.
- Expected tests after approval: calculation-config validation, exact
  centre-to-edge conversion, default-render regression, workspace-wide mesh
  identity, resource limits, CLI/GUI handoff, and existing Sumtally/RTDOSE
  geometry-consistency regression coverage, including compact huge-exponent
  inputs, using synthetic data and fake or mock runners only.
- Backward compatibility: omitting the calculation configuration retains the
  existing x/y/z centre ranges, `3 mm` voxel sizes, `101` bins per axis, and
  PHITS edges `[-15.15, 15.15]`, `[-15.15, 15.15]`, and
  `[-10.15, 20.15]` centimetres.
- Unchanged public contracts: machine model and its calibration binding,
  source and accelerator physics, DICOM coordinate transform, MU and dose
  normalization, PDD tally, actual-output-based RTDOSE placement, and the
  fixed-field 3D-CRT research scope.
- External execution: not authorized. Proposal validation and future automated
  implementation validation use no real PHITS, RT-PHITS, Sumtally,
  phits2dicom, GPR, real DICOM, or facility-specific data.
