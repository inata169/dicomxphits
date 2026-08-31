# CLI and Technical Reference

This document contains the detailed command-line examples and technical stage
contracts for dicomxphits. Start with the repository [README](../README.md) and
the [GUI User Guide](gui-user-guide.md) when using the guided Windows workflow.

The real-tool examples below use Windows PowerShell and placeholder paths
outside the repository. They require separately obtained licensed tools and an
explicitly confirmed non-patient phantom; they are not Dev Container commands.

## Prepare Workspace Adapter

The workspace adapter prepares the v1.0.x starting workspace:

```powershell
dicomxphits-prepare-3dcrt-workspace `
  --rtplan "C:\path\to\RTphits\work\case-id\RTPLAN.dcm" `
  --workspace-root "C:\outside-repo\dicomxphits-work\case-id" `
  --phits-root-folder "C:\path\to\phits" `
  --phits-executable-path "C:\path\to\phits\bin\phits335_win_openmp.exe" `
  --phits2dicom-executable-path "C:\path\to\phits\utility\RTphits\bin\phits2dicom_win.exe" `
  --maxcas 1000000 `
  --maxbch 10 `
  --omp-threads 8 `
  --calculation-config-path "C:\outside-repo\calculation.json" `
  --ct-datfiles-root "C:\path\to\RTphits\work\case-id\DATfiles" `
  --ct-reference-dicom "C:\path\to\RTphits\work\case-id\CT\CT000001.dcm" `
  --confirm-non-patient-phantom
```

The stage writes a strict segment manifest, `libpath.inp`, generated PHITS input
files, and `analysis/public_preparation_workspace_summary.json`. PHITS execution
is intentionally not performed by this adapter. Strict 3D-CRT segment manifest
and rectangular PHITS input generation use the built-in public research model
and package-owned helper code inside this repository. They do not require a
machine-config argument, private `scripts/` imports, vendor/facility inputs, or
the original IAEA files.

`--calculation-config-path` is optional. Omit it for the byte-compatible legacy
3D tally. A supplied file is validated before workspace mutation and is bound
to every active segment; it does not change the PDD tally. Actual segment and
Sumtally output mesh geometry remains authoritative for Sumtally and RTDOSE.

Run the generated active segments explicitly before Sumtally:

```powershell
dicomxphits-run-segments `
  --workspace-root "C:\outside-repo\dicomxphits-work\case-id" `
  --phits-executable-path "C:\path\to\phits\bin\phits335_win_openmp.exe"
```

The segment runner invokes the PHITS executable using PHITS's `file = ...`
launcher input contract and runs from the workspace root, so all generated
include paths resolve correctly. It reads the required `$OMP = N` directive
and passes `OMP_NUM_THREADS=N` to the direct OpenMP executable. Do not remove
the dollar sign or run a segment by changing the working directory to
`segments/<segment-id>`.

## Sumtally Adapter

The Sumtally adapters prepare and run one all-active-segments totalfield
Sumtally job:

```powershell
dicomxphits-generate-sumtally `
  --workspace-root "C:\outside-repo\dicomxphits-work\case-id" `
  --phits-root-folder "C:\path\to\phits"

dicomxphits-run-sumtally `
  --workspace-root "C:\outside-repo\dicomxphits-work\case-id" `
  --phits-executable-path "C:\path\to\phits\bin\phits335_win_openmp.exe"
```

The generated Sumtally output is MU-weighted all-segments totalfield output. It
is not a per-beam `beamMU` output. Sumtally input and wrapper generation use
package-owned helper code and do not require private `scripts/` imports.

## RTDOSE Adapter

The RTDOSE adapters prepare and run conversion for the preceding all-segments
totalfield Sumtally output:

```powershell
dicomxphits-prepare-rtdose `
  --workspace-root "C:\outside-repo\dicomxphits-work\case-id" `
  --rtplan "C:\path\to\RTphits\work\case-id\RTPLAN.dcm" `
  --template-dicom "templates\phits2dicom_rtdose_template.dcm" `
  --ct-reference-dicom "C:\path\to\RTphits\work\case-id\CT\CT000001.dcm" `
  --phits-out "C:\outside-repo\dicomxphits-work\case-id\sumtally\phits.out"

dicomxphits-run-rtdose `
  --workspace-root "C:\outside-repo\dicomxphits-work\case-id" `
  --phits2dicom-executable-path "C:\path\to\phits\utility\RTphits\bin\phits2dicom_win.exe"
```

`--template-dicom` must be a phits2dicom-compatible RTDOSE base template that
already contains the DICOM tags phits2dicom overwrites. The public tree includes
`templates/phits2dicom_rtdose_template.dcm`, a sanitized project-authored
RTDOSE template with dummy identity values and zeroed PixelData. Clinical RTDOSE
files that are missing required overwrite tags are rejected during prepare.
Official PHITS or RTphits sample files are not bundled in this repository.

`--rtplan` must identify the same frozen RT Plan used to prepare the 3D-CRT
workspace. The adapter verifies its SOP Instance UID, Frame of Reference, and
complete treatment-beam coverage against `segments/segment_manifest.json`.
It also verifies the complete frozen RT Plan file against the SHA-256 recorded
by the adjacent completed CT2PHITS workspace manifest. A legacy handoff without
that digest must reproduce the same segment geometry when rebuilt from the RT
Plan and the recorded sampling policy.

Referenced non-treatment beams such as `SETUP` are allowed only when the
manifest retains them as skipped, zero-segment-MU evidence; they are excluded
from active treatment coverage. The existing full-plan total and normalization
MU values continue to include every fraction-group referenced beam. Their
referenced beam meterset may be zero, but must be finite and nonnegative.
Only active treatment-segment MU contributes to Sumtally file weights and
`sumfactor`; complete MU totals must reconcile as active treatment MU plus
validated skipped non-treatment BeamMeterset. Template plan references are not
accepted as provenance.

Sumtally Generate and Sumtally Run record the canonical SHA-256 of that segment
manifest and the SHA-256 values of the generated PHITS wrapper and
`sumtally.inp`. Sumtally Run rejects a `--sum-input` override unless it resolves
to the wrapper recorded by Generate, and rejects either generated input when
its content has changed. Generate also records every active segment output and
all recursively resolved `infl` files consumed by the wrapper. Run verifies the
complete dependency set and every digest before PHITS launch. RTDOSE Prepare
requires the Generate and Run evidence to match. Sumtally Run also requires the
expected dose output to be newly created or byte-changed by that invocation,
records its SHA-256, and RTDOSE Prepare verifies that digest before copying the
dose and companion `phits.out` into `rtdose/DATfiles`.

The documented ImagePositionPatient title patch is applied only to those
private copies; Prepare records before/after source hashes and fails if either
upstream file changes. RTDOSE Run verifies both the unchanged upstream evidence
and the prepared-copy digests.

An older workspace changed by the historical in-place IPP title patch remains
reusable only when restoring the hash-bound segment T-Deposit title, including
the historical LF/CRLF normalization, exactly reproduces the Sumtally Run
SHA-256. Recovery bytes are used only for the private converter copy. Any
additional or ambiguous difference fails closed. An older successful handoff
without explicit mesh fields otherwise remains reusable when its segment
outputs and accepted Sumtally output match their recorded SHA-256 values and
contain one consistent mesh header. If reconstruction cannot be proven, rerun
Sumtally Generate and Sumtally Run before rerunning RTDOSE Prepare and Run.

Existing segment PHITS outputs remain reusable without PHITS transport only
when their manifest records the current
`dicomxphits_iec_gantry_mlcx_collimator_ct_accelerator_geometry_v5` contract
and every active segment records unambiguous zero values for PHITS Category-I
`Number of lost particles`, `Number of geometry recovering`, and
`Number of unrecovered errors`. Transport evidence with v4 or older, missing,
mixed, or ambiguous geometry provenance or geometry diagnostics requires a
newly prepared workspace and PHITS, Sumtally, and RTDOSE recalculation
regardless of recorded gantry, collimator, MLC, field, or CT FOV values.
Mirroring or relabeling only the final DICOM is not a repair for transport
performed with an obsolete geometry convention.

The v5 renderer excludes the complete transformed accelerator cell from the CT
wrapper. It does not crop the CT, apply an FOV threshold, change SAD/SSD, or
narrow the circumscribed source cone. The unchanged public
`8.7608E+11 source/MU` factor was explicitly reaccepted for v5 on 2026-08-31
from human-reviewed repository-safe evidence that the reference calibration
geometry was non-overlapping and transport-equivalent. That reacceptance did
not include an external PHITS dose comparison. A pre-v5 factor binding remains
stale and is rejected.

For a workspace with stale or factor-one weighted-average evidence, reopen it
with **Open existing case…** and select **Create DICOM RT Dose**. The contextual
confirmation lists the downstream stages and preserves old Sumtally/RTDOSE
files before replacement. Existing digest-bound segment PHITS outputs remain
reusable when the gantry-geometry rule above also passes; PHITS transport does
not need to be rerun solely for this normalization correction. Old Sumtally or
DICOM outputs must not be repaired with an empirical scale factor.

The adapter writes `phits2dicom.inp` as UTF-8 LF stdin content with
slash-normalized paths and records its SHA-256 during RTDOSE Prepare. RTDOSE Run
rejects the file if it changed before converter launch. Prepare also records
the SHA-256 of every file named by that input: the workspace template, CT
reference, staged Sumtally dose copy, and staged companion `phits.out`. Run
revalidates all four files immediately before conversion. The converter output
must also be new or have a changed SHA-256; a timestamp-only change fails before
plan-reference synchronization.

For PHITS `isumtally = 2`,
`X = F * sum((r_j / sum(r)) * X_j)`. The workflow uses active
treatment-segment MU as `r_j` and their sum as `F`, so the Sumtally result is
`sum(active_segment_mu * segment_dose_per_mu)` in `GY`. The approved
public-model `totfact_per_MU` is applied in each PHITS segment and the treatment
MU is applied once by Sumtally.

This Sumtally result is one delivery of the single accepted Fraction Group.
RTDOSE Prepare requires its positive integer `NumberOfFractionsPlanned`, keeps
the active-MU public-model base factor at `1.0`, and passes
`1.0 * NumberOfFractionsPlanned` to PHITS2DICOM exactly once. The generated
RTDOSE is therefore the PLAN course dose in `GY`. Its summaries record
`approved_public_model_totfact_per_mu_applied_in_phits`, the base factor,
fraction count, effective factor, equation, and frozen-plan binding. Missing,
invalid, ambiguous, or changed fraction evidence fails before converter
execution; the workflow does not multiply an already converted PixelData array.

After conversion, `dicomxphits-run-rtdose` synchronizes the output to
`DoseSummationType = PLAN` with exactly one reference to the validated frozen
RT Plan, then creates the accepted `.fixed.dcm` output next to the Sumtally
`.out` file. For the default workflow its path is
`<workspace>/sumtally/deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm`.
The execution summary records the exact path in
`coordinate_corrected_rtdose_output`.

This final output maps the supported PHITS tally `(y, z, reversed x)` bin-centre
layout to the DICOM patient grid through the frozen-plan isocenter and
`I + 10 * (-x, z, y)` millimetre mapping. The converter CT slice position is
compatibility metadata, not final placement evidence. Stored dose values and
`DoseGridScaling` are preserved. The final DICOM is reopened and its first,
centre, edge, and final voxel positions must match the bound tally geometry with
zero relative tolerance and `1e-6 mm` absolute component tolerance. The run
fails instead of accepting an output whose coordinate placement, PLAN
reference, or mesh evidence is missing.

This output is absolute dose only for the defined public education and research
reference model. It does not claim clinical commissioning, universal machine
`Gy/MU` accuracy, certification by a vendor, or agreement with a physical
Elekta unit.

## GPR-comparing Handoff

[GPR-comparing](https://github.com/inata169/GPR-comparing) remains an external
research tool and is not bundled. The public boundary can either record an
explicit knowledge-based skip when the tool is not configured, prepare the
exact external command, or execute it after checking that both RTDOSE inputs
use `GY` and share a `FrameOfReferenceUID`:

```powershell
dicomxphits-run-gpr-compare `
  --reference-rtdose "C:\outside-repo\reference-rtdose.dcm" `
  --evaluation-rtdose "C:\outside-repo\dicomxphits-work\case-id\sumtally\deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm" `
  --output-dir "C:\outside-repo\dicomxphits-work\case-id\gpr" `
  --gpr-root "C:\path\to\GPR-comparing" `
  --dd 3 `
  --dta 3 `
  --cutoff 10 `
  --execute
```

The handoff requires a fresh `run3d.json` from the external process and records
the gamma criteria and pass rate. The example explicitly selects global
`3% / 3 mm` with a `10%` cutoff to match the accepted historical GPR evidence.
The CLI defaults are `3% / 2 mm` with a `10%` cutoff, so criteria must not be
omitted when reproducing the accepted result. The handoff makes no
clinical-validity claim.

## Advanced and Maintenance Commands

`dicomxphits-prepare-ct-calibration` prepares the explicit CT calibration
workflow; it is not part of the normal guided case sequence.
`dicomxphits-fix-rtdose-coordinates` exposes the standalone RTDOSE coordinate
correction operation for controlled maintenance or investigation. The normal
RTDOSE Run stage performs its accepted correction handoff automatically.
