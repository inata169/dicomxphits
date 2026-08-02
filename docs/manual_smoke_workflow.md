# Manual Smoke Workflow

This guide describes the v1.0.0 smoke workflow for
`dicomxphits`. It is documentation for local validation and review. It does not
add a GUI, runtime command, or CI requirement for real PHITS tools.

## Safety Rules

- Real DICOM files must never be placed under `public_release/dicomxphits/`.
  The only DICOM file allowed in this tree is the reviewed, sanitized,
  zero-dose public RTDOSE template under `templates/`.
- Real PHITS or phits2dicom smoke execution is optional local validation only
  and is not required for CI.
- Local real-tool workspaces should be outside the repository tree or under
  ignored local paths.
- Do not copy real patient data, real clinical exports, PHITS execution results,
  RTphits official files, PHITS official distribution files, or local artifacts
  into this repository.
- Synthetic dummy CT is only for explicit smoke testing. It is not the default
  CT reference for clinical-like workflow review.
- Synthetic DICOM used for tests or examples must use obvious dummy values only.
  Do not use real `PatientID`, `PatientName`, `InstitutionName`, machine names,
  or facility-derived UID roots.

## Smoke Stages

Run each stage only after the previous stage summary reports success.

1. Prepare a strict 3D-CRT workspace.
2. Run the per-segment PHITS inputs to create every manifest
   `expected_output_path`.
3. Generate Sumtally input for all active strict 3D-CRT segments.
4. Run Sumtally with PHITS, or use a mocked runner in automated tests.
5. Prepare RTDOSE conversion from the all-segments totalfield Sumtally output.
6. Run phits2dicom locally, or use a mocked runner in automated tests.
7. Optionally execute the external GPR comparison, or record an explicit skip.
8. Review summaries and logs.

## Local Path Placeholders

Keep these values separate:

```text
PHITS_ROOT=/path/to/phits-root
PHITS_EXE=/path/to/phits/bin/phits
PHITS2DICOM_EXE=/path/to/phits2dicom
WORKSPACE=/outside/repo/dicomxphits-smoke-workspace
CT_DATFILES_ROOT=/outside/repo/non-patient-ct2phits/DATfiles
FROZEN_RTPLAN=/outside/repo/non-patient-ct2phits/RTPLAN.dcm
TEMPLATE_DICOM=/outside/repo/template_rtdose.dcm
CT_REFERENCE_DICOM=/outside/repo/reference_ct.dcm
REFERENCE_RTDOSE=/outside/repo/reference_rtdose.dcm
EVALUATION_RTDOSE=/outside/repo/evaluation_rtdose.fixed.dcm
GPR_ROOT=/path/to/GPR-comparing
```

`TEMPLATE_DICOM` must be a phits2dicom-compatible RTDOSE base template with the
required overwrite tags already present. When a local compatible template is not
available, use
`templates/phits2dicom_rtdose_template.dcm`. Do not use repository-local PHITS
or RTphits sample files. If a clinical RTDOSE is missing required overwrite
tags, prepare fails before phits2dicom execution.

Run `ct2phits.exe` for the confirmed non-patient phantom first.
`CT_DATFILES_ROOT` must point directly to the resulting raw `DATfiles`
directory. It must contain the ordinary CT2PHITS outputs such as
`CTusrparam.dat`, `CTcell.dat`, `CTmaterial.dat`, `CTuniverse.dat`,
`CTsurf.dat`, `CTmatnamecolor.dat`, `CTvoxel.dat`, and `phantominfo.dat`.
Use that same frozen plan as `FROZEN_RTPLAN` and select one CT slice from the
same series as `CT_REFERENCE_DICOM`.
dicomxphits performs the `.dat` to runtime-include preparation and coordinate
translation itself. Do not select `CT_repaired`, a generated field directory,
or a directory where files were manually renamed to `.inp`.

The workspace may also be under an ignored local path if that is how the local
developer environment is configured. Do not use a tracked path under
the repository tree for real-tool smoke outputs.

## Stage Commands

Prepare the public workspace:

```bash
dicomxphits-prepare-3dcrt-workspace \
  --rtplan /outside/repo/synthetic_or_local_rtplan.dcm \
  --workspace-root "$WORKSPACE" \
  --phits-root-folder "$PHITS_ROOT" \
  --phits-executable-path "$PHITS_EXE" \
  --phits2dicom-executable-path "$PHITS2DICOM_EXE" \
  --ct-datfiles-root "$CT_DATFILES_ROOT" \
  --ct-reference-dicom "$CT_REFERENCE_DICOM" \
  --confirm-non-patient-phantom
```

This command uses the built-in approved public research machine model by
default. It needs no machine-configuration file, Elekta file, NDA or paid
vendor dataset, facility geometry/calibration input, or original IAEA
phase-space/header file. The licensed PHITS installation is the only default
external software prerequisite; the confirmed non-patient CT2PHITS raw
`DATfiles` and CT reference are a separate input-data requirement.

Run all generated active segments with the public runner:

```bash
dicomxphits-run-segments \
  --workspace-root "$WORKSPACE" \
  --phits-executable-path "$PHITS_EXE"
```

The runner follows the strict segment manifest and requires every active
segment to produce its `expected_output_path`. Automated tests use mocked
segment outputs instead of real PHITS. The runner passes `file = ...` to the
PHITS executable and keeps the workspace root as the working directory so that
`libpath.inp`, CT includes, and the public spectrum resolve correctly.

Generate all-active-segments totalfield Sumtally input:

```bash
dicomxphits-generate-sumtally \
  --workspace-root "$WORKSPACE" \
  --phits-root-folder "$PHITS_ROOT"
```

Run Sumtally with PHITS for optional local real-tool validation:

```bash
dicomxphits-run-sumtally \
  --workspace-root "$WORKSPACE" \
  --phits-executable-path "$PHITS_EXE"
```

Prepare RTDOSE conversion:

```bash
dicomxphits-prepare-rtdose \
  --workspace-root "$WORKSPACE" \
  --rtplan "$FROZEN_RTPLAN" \
  --template-dicom "$TEMPLATE_DICOM" \
  --ct-reference-dicom "$CT_REFERENCE_DICOM" \
  --phits-out "$WORKSPACE/sumtally/phits.out"
```

Run phits2dicom for optional local real-tool validation:

```bash
dicomxphits-run-rtdose \
  --workspace-root "$WORKSPACE" \
  --phits2dicom-executable-path "$PHITS2DICOM_EXE"
```

Use the same frozen RT Plan that produced the workspace manifest. The accepted
result is the path recorded as `coordinate_corrected_rtdose_output` in
`analysis/rtdose_conversion_execution_summary.json`, normally the
`sumtally/*_all_active_segments_totalfield.fixed.dcm` file. RTDOSE Run reports
failure if this final file is not a PLAN dose referencing that frozen RT Plan.
RTDOSE preparation also requires matching manifest and generated-input SHA-256
evidence from Sumtally Generate and Sumtally Run. Sumtally Run accepts only the
wrapper path recorded by Generate and rejects a changed wrapper or
`sumtally.inp`. Generate records every active segment output and recursively
resolved wrapper `infl` file; Run verifies the same dependency set and digests
before PHITS launch. Run must update the expected dose output and records its
SHA-256; RTDOSE Prepare verifies the Generate/Run evidence before the IPP title
patch, and RTDOSE Run verifies the prepared digest. If either summary predates
this evidence, rerun both Sumtally stages using the existing unchanged segment
outputs first.
Referenced non-treatment beams are accepted only as skipped, zero-segment-MU
manifest entries; active coverage remains limited to treatment-eligible beams,
while the existing full referenced-beam normalization MU is preserved. A
non-treatment referenced beam meterset may be zero but must not be negative or
non-finite.
The frozen RT Plan is bound by the completed CT2PHITS manifest SHA-256, with
exact segment-geometry reconstruction as the legacy fallback. The generated
`phits2dicom.inp` digest is also checked between RTDOSE Prepare and Run, along
with the digests of its template, CT, prepared dose, and `phits.out` inputs.

Optionally execute the external GPR comparison:

```bash
dicomxphits-run-gpr-compare \
  --reference-rtdose "$REFERENCE_RTDOSE" \
  --evaluation-rtdose "$EVALUATION_RTDOSE" \
  --output-dir "$WORKSPACE/gpr" \
  --gpr-root "$GPR_ROOT" \
  --dd 3 \
  --dta 3 \
  --cutoff 10 \
  --execute
```

This explicit global `3% / 3 mm`, `10%` cutoff selection matches the accepted
historical GPR evidence. The CLI defaults are `3% / 2 mm`, `10%` cutoff. If the
external tool is not configured, omit `--gpr-root` and `--execute` to write an
explicit knowledge-based skip record instead of claiming a new comparison.

## Summary Review

Review these files after each stage:

- `analysis/public_preparation_workspace_summary.json`
- `analysis/phits_generation_summary.json`
- `analysis/segment_execution_summary.json`
- `analysis/sumtally_generation_summary.json`
- `analysis/sumtally_execution_summary.json`
- `analysis/rtdose_conversion_prepare_summary.json`
- `analysis/rtdose_conversion_execution_summary.json`
- `gpr/gpr_handoff_summary.json` when the optional GPR stage is used

The Sumtally output contract must remain:

- `sumtally_scope = all_active_segments`
- `sumtally_mode = totalfield`
- `weight_field = segment_mu`
- `sumtally_normalization = all_segments_totalfield_segment_mu`
- `rt_dose_conversion_hint.is_beam_mu_output = false`

RTDOSE conversion must not treat this output as per-beam `beamMU`.

## Local-Only GUI Confidence Check

A human-operated Windows GUI confidence check was performed after the
rectangular smoke-input updates were merged into `main`. The check used a fresh
ignored local workspace and a user-supplied local machine configuration file.
No DICOM identifiers, clinical machine configuration contents, PHITS outputs,
RTDOSE outputs, raw logs, or private absolute paths are part of this note.

The checked scope was limited to `rectangular_3dcrt` workspace preparation from
the public GUI. The operator confirmed:

- the local workspace was ignored by Git before use;
- Workspace Prepare completed in `rectangular_3dcrt` mode;
- seven active segment PHITS input files were generated;
- the first generated PHITS input contained a Source section, Y-Diaphragm
  cells, MLC bank cells, an inside-world transport cell, the rectangular
  Transform entry, and a T-Deposit tally writing `deposit-target-3D.out`;
- the GUI output stated that `rectangular_3dcrt` is rectangular geometry
  generation only and does not provide dose validation or clinical validity
  certification.

This check is operator confidence evidence for GUI mode selection, path safety,
and rectangular PHITS input generation. It is not clinical validation, not dose
accuracy validation, not patient-specific QA evidence, and not a commissioned
beam-model claim.

## CI Smoke Boundary

Automated tests use synthetic inputs and mocked external tools only. CI must not
require real PHITS, real phits2dicom, real DICOM files, or PHITS execution
results. Run the public validation set before opening a PR:

```bash
python -m pytest -q
```
