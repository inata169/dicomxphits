# dicomxphits GUI User Guide (v1.0.x)

For clinical medical physicists and fourth-year university students studying medical physics

> **Important**
> dicomxphits v1.0.x is a fixed-field 3D-CRT workflow for education and research. It is not for clinical commissioning, patient-specific QA, or treatment decisions. The GUI may be used only with appropriately authorized **non-patient phantom data**. IMRT, dynamic MLC delivery, and VMAT are outside its supported scope.

## 1. What the GUI does

dicomxphits prepares PHITS calculations from DICOM RT Plan and CT data, runs the explicit calculation stages, and converts the result to DICOM RT Dose. The GUI divides this workflow into five pages:

1. **CT2PHITS** converts the CT images into voxel data used by PHITS.
2. **Workspace** reads the RT Plan and generates fixed-field PHITS inputs.
3. **PHITS** runs the Monte Carlo calculation for each irradiation segment.
4. **Sumtally** combines the segment results with MU weighting.
5. **RTDOSE** converts the combined dose to DICOM RT Dose and corrects its patient coordinates.

The GUI deliberately keeps the external-tool stages separate. Each stage records a JSON summary and logs so that you can determine what ran, which inputs were used, and where a failure occurred.

The final GUI output is normally:

```text
<3D-CRT workspace>\sumtally\
  deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm
```

Confirm the exact output path in `coordinate_corrected_rtdose_output` within `analysis/rtdose_conversion_execution_summary.json`.

## 2. Supported scope

| Item | v1.0.x scope |
| --- | --- |
| Intended use | Education and research only |
| Operating system | Windows host |
| Python | 3.12 only; 3.11 and earlier and 3.13 and later are unsupported |
| Delivery type | Fixed-field 3D-CRT |
| Aperture boundary | X and Y within -100 to +100 mm in collimator coordinates; width no greater than 200 mm |
| Largest centered square field | 20 × 20 cm² |
| Input | Non-patient phantom CT DICOM and RT Plan |
| Not supported | Patient data, IMRT, dynamic MLC, VMAT, clinical commissioning, or patient QA |

The workflow does not clip an aperture to make it fit. A plan outside the boundary is rejected.

## 3. Prerequisites

### Software

- Python 3.12 on Windows
- The dicomxphits repository
- A separately and legitimately obtained PHITS installation
- The RT-PHITS files supplied with that installation
- Tkinter, normally included with the Windows Python distribution

PHITS, RT-PHITS, and phits2dicom are not distributed with dicomxphits.

The standard profile expects this layout below the selected PHITS installation folder:

```text
<PHITS installation folder>\
├─ bin\phits335_win_openmp.exe
└─ utility\RTphits\
   ├─ RTphits_win.bat
   ├─ data\HumanVoxelTable.data
   └─ bin\phits2dicom_win.exe
```

If your installation uses a different layout, select **Custom layout (advanced)** and provide each path explicitly.

### Input data

- A complete CT DICOM series for one phantom
- A DICOM RT Plan using the same Frame of Reference as that CT
- A fixed-field 3D-CRT plan
- Finite, positive MU for every active treatment beam; any SETUP beam must
  have finite, non-negative MU and is excluded from treatment dose

If the CT folder contains more than one series, identify the intended `SeriesInstanceUID` before starting.

### Output location

Create calculation workspaces outside the repository. Do not add real data, licensed PHITS files, or generated calculation results to Git.

## 4. Install and launch

Open PowerShell in the repository root. Do not launch the GUI from the Linux Dev Container terminal.

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\launchers\run_gui_venv.cmd
```

Confirm that the first command reports `Python 3.12.x`.

If the `py` launcher is unavailable, replace the first two commands only when `python --version` reports Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\launchers\run_gui_venv.cmd
```

The `.cmd` launcher adds the repository-local `.venv\Scripts` directory to the
GUI process PATH. It does not create the virtual environment or install
dependencies for you.

The equivalent `.\launchers\run_gui_venv.ps1` launcher may be used where local
PowerShell policy permits unsigned repository scripts. If a Download ZIP copy
produces `PSSecurityException` or a digital-signature error, do not weaken the
machine or organization execution policy; use `run_gui_venv.cmd` instead.

The bounded, human-reported Windows check completed after this launcher change
is recorded in [Windows GUI Launcher Validation -
2026-08-06](windows-gui-launcher-validation-2026-08-06.md). That record omits
external paths and results and is not clinical validation or a general Windows
compatibility claim.

## 5. One-time tool setup

1. Open **1 CT2PHITS** in the left sidebar.
2. Select **Tool settings • Show saved paths**.
3. For a normal installation, select **Standard PHITS 3.35-style layout**.
4. Under **PHITS installation folder**, select the top-level PHITS directory.
5. Confirm that **RTDOSE template** points to:

   ```text
   templates\phits2dicom_rtdose_template.dcm
   ```

6. Select **Validate and save setup**.
7. Setup is complete when the status reads `Ready — phits-3.35-windows`.
8. Select **Tool settings • Back to case setup**.

This setup validation checks required paths only. It does not run PHITS or another external tool.

Stable tool paths, runtime preferences, and the most recent Browse locations may be saved. The RT Plan, CT folder, case output, non-patient confirmation, and overwrite permission are never restored automatically.

## 6. Standard GUI workflow

### Step 1: CT2PHITS

Select **1 CT2PHITS**.

1. Under **RT Plan (source)**, select the non-patient phantom RT Plan.
2. Under **CT DICOM folder**, select the folder containing the corresponding CT series.
3. Review **CT2PHITS case output**.
   - In the standard profile, it is derived automatically below `<RT-PHITS root>\work\`.
   - The directory must not exist before the run.
4. If the CT folder contains multiple series, enter the intended UID in **Series UID (optional)** under Tool settings.
5. Normally, keep the **Timeout (seconds)** default of `300`.
6. Select **I confirm non-patient phantom data**.
7. Select **Run CT2PHITS**.
8. Review the Activity log and sidebar status.

After success, the GUI automatically hands these items to the next stage:

- **Frozen RT Plan**: the stable RT Plan snapshot copied into the CT2PHITS workspace
- **CT reference**: the selected reference slice from the CT series
- **CT2PHITS DATfiles**: the raw files produced by CT2PHITS

Confirm that the handoff status reads **Verified frozen handoff**. All downstream stages use the Frozen RT Plan, not the mutable source file.

### Step 2: Workspace

Select **2 Workspace**.

1. Choose the parent location for **3D-CRT workspace**.
   - **Browse…** proposes a new workspace name below the selected parent.
   - Keep it outside the repository.
2. Confirm that **Geometry mode** is `rectangular_3dcrt`.
3. Normally, leave **Machine config (optional)** empty. This selects the built-in public rectangular research model.
4. For a first exercise, review the runtime controls and keep their defaults unless you have a specific reason to change them.

   | Setting | Default | Meaning |
   | --- | ---: | --- |
   | `maxcas` | 1,000,000 | Histories per batch |
   | `maxbch` | 10 | Number of batches |
   | OpenMP threads | 8 | Parallel threads for segment execution |

5. Select **Prepare workspace**.

PHITS does not run during this stage. dicomxphits validates the RT Plan, MU, aperture, and CT/RT coordinate relationship, then generates PHITS inputs for the plan segments.

Important outputs include:

```text
<workspace>\
├─ libpath.inp
├─ segments\segment_manifest.json
└─ analysis\
   ├─ phits_generation_summary.json
   └─ public_preparation_workspace_summary.json
```

### Step 3: PHITS

Select **3 PHITS**.

1. Confirm that **PHITS executable** points to the intended OpenMP executable.
2. Select **Run PHITS segments**.
3. Calculations may take a long time. Keep the GUI open and wait until the top status returns to `Ready`.
4. Confirm that the Activity log reports success and gives a summary path.

The runner follows the workspace manifest and executes every active segment. Sumtally cannot succeed until every required segment output is present.

> `$OMP = N` is official PHITS OpenMP syntax, not a comment. Do not remove the dollar sign from generated inputs.

### Step 4: Sumtally

Select **4 Sumtally**.

1. Select **Generate Sumtally**.
2. After generation succeeds, select **Run Sumtally**.
3. Confirm success for both actions in the Activity log.

Generate creates the aggregation inputs; Run executes the aggregation with PHITS.
The result is one MU-weighted `totalfield` covering all active treatment
segments. SETUP beams contribute neither weight nor `sumfactor`. Treatment
MU is applied once by Sumtally; the later phits2dicom conversion therefore uses
factor `1.0`. The result is not a per-beam `beamMU` output.

### Step 5: RTDOSE

Select **5 RTDOSE**.

1. Confirm that **RTDOSE template** points to the public template.
2. **CT reference** is the read-only path handed forward from CT2PHITS.
3. Confirm that **phits2dicom executable** points to the correct Windows executable.
4. Select **Prepare RTDOSE**.
5. When the status becomes **Prepared** and the log says `Next: click Run RTDOSE`, select **Run RTDOSE**.
6. After completion, open `analysis/rtdose_conversion_execution_summary.json`.
7. Use the `.fixed.dcm` path recorded in `coordinate_corrected_rtdose_output` as the final output.

**Prepare RTDOSE** prepares and verifies the conversion inputs and evidence.
**Run RTDOSE** is the action that invokes phits2dicom and creates the DICOM
output. The GUI reports **Completed** only when the Prepare summary is bound to
the current Sumtally evidence and the Run summary records the exact current
Prepare-summary digest. Stale success summaries cannot enable **Run RTDOSE**.

The final RT Dose is written with `DoseUnits = GY` and `DoseSummationType = PLAN`; its Frozen RT Plan reference and coordinates are checked. It is still research absolute dose for the defined public model and does not demonstrate agreement with a clinical machine.

## 7. How to confirm success

After each action, confirm all three:

1. The top status returns to `Ready`.
2. The sidebar status shows the stage as successful.
3. The **Activity log** reports success and gives the summary JSON path.

The main summaries are:

| Stage | Summary |
| --- | --- |
| Workspace | `analysis/public_preparation_workspace_summary.json` |
| PHITS | `analysis/segment_execution_summary.json` |
| Sumtally Generate | `analysis/sumtally_generation_summary.json` |
| Sumtally Run | `analysis/sumtally_execution_summary.json` |
| RTDOSE Prepare | `analysis/rtdose_conversion_prepare_summary.json` |
| RTDOSE Run | `analysis/rtdose_conversion_execution_summary.json` |

The summaries preserve traceability such as commands, major input and output paths, return codes, and file hashes.

## 8. Common problems

### Tool setup shows `Needs attention`

- Open **Tool settings**.
- Confirm that PHITS installation folder is the top-level PHITS directory.
- Check that the expected standard-layout files and folders exist.
- For a nonstandard installation, select **Custom layout (advanced)** and provide all four effective paths.
- Run **Validate and save setup** again.

### `Confirm that the CT and RT Plan describe non-patient phantom data`

Select **I confirm non-patient phantom data**. If the input contains patient data, stop the workflow.

### `CT2PHITS workspace must be new and must not exist`

Choose a new output name that does not yet exist. Do not delete or overwrite an earlier result merely to reuse its name.

### `workspace root already contains files`

Workspace Prepare normally requires a new or empty workspace. Use **Allow overwrite of downstream stage summaries** only when you understand which previous evidence must be replaced.

### An action button is disabled

A required external-tool path may be unresolved, another stage may still be running, or the RTDOSE state may restrict the action. Review Tool settings, the top status, and the Activity log.

### The CT folder contains multiple series

Enter the intended `SeriesInstanceUID` under **Series UID (optional)**. The GUI does not recursively search for DICOM, so select the folder containing the intended series explicitly.

### RTDOSE already shows `Prepared`

Do not repeat Prepare. Select **Run RTDOSE**. If you reran Sumtally and invalidated the prepared evidence, select **Allow overwrite of downstream stage summaries**, then prepare again.

### A stage failed and the cause is unclear

- Read the last error in the Activity log.
- Open the summary JSON path shown by the GUI.
- Review `failure_reason`, `return_code`, the recorded stdout/stderr log paths (for example, `stdout_path` and `stderr_path`), and the recorded input and output paths. Field names vary slightly by stage.
- If CT2PHITS timed out and `process_tree_termination_error` is not null, a human must confirm that no child process remains before reusing the external workspace.

## 9. Using an existing CT2PHITS handoff

Normally, begin at Step 1. Use **Use an existing validated CT2PHITS handoff (advanced)** on the Workspace page only when you already have a validated handoff. Provide:

- Frozen RT Plan
- CT reference
- DATfiles

The existence of these paths alone is not enough. Use the unchanged handoff associated with the completed CT2PHITS summary.

## 10. Outside the GUI: GPR comparison

The five GUI pages end with the coordinate-corrected RT Dose. Gamma analysis with the external [GPR-comparing](https://github.com/inata169/GPR-comparing) project is not part of the GUI. If needed, follow **GPR-comparing Handoff** in the repository README and run it explicitly from the CLI.

The accepted historical reproduction setting is global 3%/3 mm with a 10% cutoff. The CLI default is 3%/2 mm, so do not omit the criteria when reproducing that evidence.

## 11. Learning guide

On your first run, trace the workflow rather than looking only at the final RT Dose.

| Physics or clinical concept | Where to inspect it |
| --- | --- |
| RT Plan beams, Control Points, and MU | `segments/segment_manifest.json` |
| Monte Carlo histories | `maxcas` and `maxbch` on the Workspace page |
| Parallel calculation | OpenMP threads and `$OMP` in generated inputs |
| Calculation of each irradiation segment | `segments/` and `segment_execution_summary.json` |
| MU-weighted dose aggregation | Sumtally summaries |
| DICOM coordinates and RT Plan reference | RTDOSE execution summary and the `.fixed.dcm` file |

The educational value of dicomxphits is that it exposes the relationship among DICOM, the field model, Monte Carlo transport, MU weighting, and DICOM RT Dose one stage at a time.

## 12. Minimum completion checklist

- [ ] Launched the GUI with Python 3.12
- [ ] Tool setup reports `Ready`
- [ ] Confirmed that the inputs are non-patient phantom data
- [ ] CT2PHITS reports **Verified frozen handoff**
- [ ] Workspace Prepare succeeded
- [ ] Every PHITS segment completed successfully
- [ ] Sumtally Generate and Run succeeded
- [ ] RTDOSE Prepare reached **Prepared**
- [ ] RTDOSE Run succeeded
- [ ] Located the `.fixed.dcm` recorded in the execution summary
- [ ] Did not use the output for a clinical decision or patient QA

## Related documentation

- [dicomxphits README](../README.md)
- [Workflow stages and gates](workflow_stages.md)
- [Manual smoke workflow](manual_smoke_workflow.md)
- [CT2PHITS frontend handoff](ct2phits-frontend-handoff.md)
- [GPR-comparing](https://github.com/inata169/GPR-comparing)
