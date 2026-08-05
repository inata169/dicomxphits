# Manual Smoke Workflow

This guide describes the v1.0.x smoke workflow for
`dicomxphits`. It is documentation for local validation and review. It does not
add a GUI, runtime command, or CI requirement for real PHITS tools.

## Safety Rules

- Real DICOM files must never be placed anywhere in this repository. The only
  tracked DICOM file is the reviewed, sanitized, zero-dose public RTDOSE
  template under `templates/`.
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

1. On Windows, run the CT2PHITS frontend for a confirmed non-patient phantom.
   `dicomxphits-run-ct2phits` invokes the user-supplied `RTphits_win.bat`; it
   does not run the CT2PHITS executable directly.
2. Prepare a strict 3D-CRT workspace from the validated frozen handoff.
3. Run the per-segment PHITS inputs to create every manifest
   `expected_output_path`.
4. Generate Sumtally input for all active strict 3D-CRT segments.
5. Run Sumtally with PHITS, or use a mocked runner in automated tests.
6. Prepare RTDOSE conversion from the all-segments totalfield Sumtally output.
7. Run phits2dicom locally, or use a mocked runner in automated tests.
8. Optionally execute the external GPR comparison, or record an explicit skip.
9. Review summaries and logs.

## Local Path Placeholders

Keep these values separate:

```powershell
$PhitsRoot = "C:\path\to\phits"
$PhitsExe = "C:\path\to\phits\bin\phits335_win_openmp.exe"
$RtphitsRoot = "C:\path\to\phits\utility\RTphits"
$Phits2DicomExe = "C:\path\to\phits\utility\RTphits\bin\phits2dicom_win.exe"
$SourceRtplan = "C:\outside-repo\non-patient-input\RTPLAN.dcm"
$CtDicomRoot = "C:\outside-repo\non-patient-input\CT"
$Ct2phitsWorkspace = "C:\path\to\phits\utility\RTphits\work\smoke-case"
$Workspace = "C:\outside-repo\dicomxphits-smoke-workspace"
$TemplateDicom = "templates\phits2dicom_rtdose_template.dcm"
$ReferenceRtDose = "C:\outside-repo\reference_rtdose.dcm"
$EvaluationRtDose = "C:\outside-repo\evaluation_rtdose.fixed.dcm"
$GprRoot = "C:\path\to\GPR-comparing"
```

`$TemplateDicom` must be a phits2dicom-compatible RTDOSE base template with the
required overwrite tags already present. When a local compatible template is not
available, use
`templates/phits2dicom_rtdose_template.dcm`. Do not use repository-local PHITS
or RTphits sample files. If a clinical RTDOSE is missing required overwrite
tags, prepare fails before phits2dicom execution.

Run the Windows frontend command shown below for the confirmed non-patient
phantom first. It calls the supplied `RTphits_win.bat` and creates a frozen
handoff below `$Ct2phitsWorkspace`. `$CtDatfilesRoot` must then point directly
to its raw `DATfiles` directory. It must contain ordinary CT2PHITS outputs,
including
`CTusrparam.dat`, `CTcell.dat`, `CTmaterial.dat`, `CTuniverse.dat`,
`CTsurf.dat`, `CTmatnamecolor.dat`, `CTvoxel.dat`, and `phantominfo.dat`.
Use that same frozen plan as `$FrozenRtplan` and one CT slice from the same
series as `$CtReferenceDicom`.
dicomxphits performs the `.dat` to runtime-include preparation and coordinate
translation itself. Do not select `CT_repaired`, a generated field directory,
or a directory where files were manually renamed to `.inp`.

The workspace may also be under an ignored local path if that is how the local
developer environment is configured. Do not use a tracked path under
the repository tree for real-tool smoke outputs.

## Stage Commands

Run the Windows CT2PHITS frontend through `RTphits_win.bat`:

```powershell
dicomxphits-run-ct2phits `
  --ct-dicom-root $CtDicomRoot `
  --rtplan $SourceRtplan `
  --rtphits-root $RtphitsRoot `
  --workspace-root $Ct2phitsWorkspace `
  --timeout-seconds 300 `
  --confirm-non-patient-phantom

$FrozenRtplan = Join-Path $Ct2phitsWorkspace "RTPLAN.dcm"
$CtDatfilesRoot = Join-Path $Ct2phitsWorkspace "DATfiles"
$CtReferenceDicom = Join-Path $Ct2phitsWorkspace "CT\CT000001.dcm"
```

If the source contains multiple CT series, add
`--ct-series-instance-uid <uid>`. Confirm the exact copied CT slice recorded by
the completed frontend summary before assigning `$CtReferenceDicom`.

Prepare the public workspace:

```powershell
dicomxphits-prepare-3dcrt-workspace `
  --rtplan $FrozenRtplan `
  --workspace-root $Workspace `
  --phits-root-folder $PhitsRoot `
  --phits-executable-path $PhitsExe `
  --phits2dicom-executable-path $Phits2DicomExe `
  --maxcas 1000000 `
  --maxbch 10 `
  --omp-threads 8 `
  --ct-datfiles-root $CtDatfilesRoot `
  --ct-reference-dicom $CtReferenceDicom `
  --confirm-non-patient-phantom
```

This command uses the built-in approved public research machine model by
default. It needs no machine-configuration file, Elekta file, NDA or paid
vendor dataset, facility geometry/calibration input, or original IAEA
phase-space/header file. The licensed PHITS installation is the only default
external software prerequisite; the confirmed non-patient CT2PHITS raw
`DATfiles` and CT reference are a separate input-data requirement.

Run all generated active segments with the public runner:

```powershell
dicomxphits-run-segments `
  --workspace-root $Workspace `
  --phits-executable-path $PhitsExe
```

The runner follows the strict segment manifest and requires every active
segment to produce its `expected_output_path`. Automated tests use mocked
segment outputs instead of real PHITS. The runner passes `file = ...` to the
PHITS executable and keeps the workspace root as the working directory so that
`libpath.inp`, CT includes, and the public spectrum resolve correctly. The
first input line `$OMP = 8` is PHITS's documented OpenMP command rather than a
comment. The runner reads it and sets `OMP_NUM_THREADS=8` for the direct OpenMP
executable; use the workspace-preparation options above to choose a different
positive value.

Generate all-active-segments totalfield Sumtally input:

```powershell
dicomxphits-generate-sumtally `
  --workspace-root $Workspace `
  --phits-root-folder $PhitsRoot
```

Run Sumtally with PHITS for optional local real-tool validation:

```powershell
dicomxphits-run-sumtally `
  --workspace-root $Workspace `
  --phits-executable-path $PhitsExe
```

Prepare RTDOSE conversion:

```powershell
dicomxphits-prepare-rtdose `
  --workspace-root $Workspace `
  --rtplan $FrozenRtplan `
  --template-dicom $TemplateDicom `
  --ct-reference-dicom $CtReferenceDicom `
  --phits-out "$Workspace\sumtally\phits.out"
```

Run phits2dicom for optional local real-tool validation:

```powershell
dicomxphits-run-rtdose `
  --workspace-root $Workspace `
  --phits2dicom-executable-path $Phits2DicomExe
```

Use the same frozen RT Plan that produced the workspace manifest. The accepted
result is the path recorded as `coordinate_corrected_rtdose_output` in
`analysis/rtdose_conversion_execution_summary.json`, normally the
`sumtally/*_all_active_segments_totalfield.fixed.dcm` file. RTDOSE Run reports
failure if this final file is not a PLAN dose referencing that frozen RT Plan.
The GUI shows `Completed` only after the final file is reopened and its
plan-and-tally-derived patient coordinates pass. Verify the execution evidence
without copying the DICOM or workspace into the repository:

```powershell
$RunSummary = Get-Content -Raw "$Workspace\analysis\rtdose_conversion_execution_summary.json" |
  ConvertFrom-Json

[pscustomobject]@{
  StageStatus = $RunSummary.stage_status
  CoordinateValidated = $RunSummary.coordinate_placement_validation.validated
  MaxResidualMm = $RunSummary.coordinate_placement_validation.maximum_absolute_component_residual_mm
  OutputExists = Test-Path -LiteralPath $RunSummary.coordinate_corrected_rtdose_output
}
```

Expected values are `success`, `True`, a residual no greater than
`0.000001 mm`, and `True`. This is research workflow evidence, not clinical
validation.

Legacy RTDOSE Prepare/Run success summaries without coordinate-placement proof
return the GUI to `Not run`. Explicit Prepare and Run clicks may replace only
those legacy successful summaries without enabling general overwrite. Failed
summaries and current placement evidence keep the normal overwrite guards.

RTDOSE preparation also requires matching manifest and generated-input SHA-256
evidence from Sumtally Generate and Sumtally Run. Sumtally Run accepts only the
wrapper path recorded by Generate and rejects a changed wrapper or
`sumtally.inp`. Generate records every active segment output and recursively
resolved wrapper `infl` file; Run verifies the same dependency set and digests
before PHITS launch. Run must create or byte-change the expected dose output and
records its SHA-256; a timestamp-only change is rejected. RTDOSE Prepare
verifies the Generate/Run evidence, copies the Sumtally dose and phits.out into
rtdose/DATfiles, and applies the IPP title patch only to those private copies.
Prepare proves the upstream files remained byte-for-byte unchanged, and Run
revalidates both source and prepared-copy digests.
A workspace changed by the historical in-place IPP title patch can be reused
without rerunning Sumtally only when reversing that title from the hash-bound
segment evidence, including LF/CRLF normalization, exactly reproduces the
Sumtally Run SHA-256. Recovered bytes are written only to the private copy;
every other mismatch fails. An older handoff without explicit mesh fields can
otherwise be reused when segment and Sumtally outputs match their digests and
contain one consistent mesh. Failed reconstruction requires rerunning both
Sumtally stages, but not PHITS segment transport.
If either summary predates the current normalization or binding evidence,
select **Allow overwrite of
downstream stage summaries**, then rerun **Sumtally Generate**, **Sumtally
Run**, **Prepare RTDOSE**, and **Run RTDOSE** using the existing unchanged
segment outputs. PHITS transport is not rerun solely for this correction.
The GUI must report RTDOSE `Completed` only when the current Sumtally binding,
Prepare summary, and Run summary digest agree. A stale success summary remains
on disk for audit but must return the workflow to `Not run` or `Prepared`;
it must not enable a stale **Run RTDOSE** action.
Referenced non-treatment beams are accepted only as skipped, zero-segment-MU
manifest entries; active coverage remains limited to treatment-eligible beams,
while complete plan, included, and normalization MU provenance remains bound
to every referenced beam. A non-treatment referenced beam meterset may be zero
but must not be negative or non-finite; it contributes no Sumtally weight or
`sumfactor`. With `isumtally = 2`, Sumtally evaluates
`X = F * sum((r_j / sum(r)) * X_j)`. The workflow uses active segment MU as
`r_j` and their sum as `F`, giving
`sum(active_segment_mu * segment_dose_per_mu)` in `GY`.
The frozen RT Plan is bound by the completed CT2PHITS manifest SHA-256, with
exact segment-geometry reconstruction as the legacy fallback. The generated
`phits2dicom.inp` digest is also checked between RTDOSE Prepare and Run, along
with the digests of its template, CT, staged dose, and staged `phits.out` inputs.
The converter must create or byte-change its expected RTDOSE; merely touching a
stale output fails before plan-reference synchronization.

Optionally execute the external GPR comparison:

```powershell
dicomxphits-run-gpr-compare `
  --reference-rtdose $ReferenceRtDose `
  --evaluation-rtdose $EvaluationRtDose `
  --output-dir "$Workspace\gpr" `
  --gpr-root $GprRoot `
  --dd 3 `
  --dta 3 `
  --cutoff 10 `
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
- `sumtally_normalization = active_treatment_segments_totalfield_segment_mu_sum`
- `sumfactor = sum(active treatment segment_mu)`
- `rt_dose_conversion_hint.input_dose_unit = GY`
- `rt_dose_conversion_hint.is_beam_mu_output = false`

RTDOSE conversion must not treat this output as per-beam `beamMU`.

## Historical Evidence: Local-Only GUI Confidence Check

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
