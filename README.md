# dicomxphits

dicomxphits is an education and research workflow for preparing strict
fixed-field 3D-CRT PHITS inputs from DICOM RT Plans and for controlling the
explicit PHITS, Sumtally, RTDOSE, coordinate-correction, and external GPR
handoff stages.

## Status

Version 1.0.0 includes standalone public adapters for strict 3D-CRT workspace
preparation, PHITS segment execution, Sumtally generation and execution,
RTDOSE conversion and coordinate correction, and an optional external
GPR-comparing handoff.

## v1.0.0 Workflow

The v1.0.0 workflow is intentionally narrow:

- strict 3D-CRT RT Plan input
- strict MU gate before downstream stages
- generated PHITS input workspace through public adapters
- explicit PHITS execution stage
- explicit Sumtally generation and execution stage
- explicit RTDOSE conversion stage

Each stage must write command metadata, return code when executed, stdout and
stderr capture paths or content, major input and output paths, and a summary JSON
path.

## v1.0.0 Public Model Scope

For v1.0.0, dicomxphits supports fixed-field 3D-CRT up to the centered
`20 x 20 cm2` effective-aperture boundary for education and research. After
DICOM Control Point inheritance is resolved, the jaw and MLC common effective
aperture at every Control Point must remain inside the closed collimator-local
isocenter-plane box from `-100.000 mm` to `+100.000 mm` on both X and Y. Each
effective width must also be no greater than `200.000 mm`.

A centered `20 x 20 cm2` aperture is therefore the largest square at the
boundary. A narrower offset aperture is eligible only when every effective
point remains inside the same box. The workflow rejects overruns rather than
clipping, recentering, or expanding the source cone.

This narrow initial boundary was selected for a maintainable education and
research workflow with Monte Carlo computational cost in mind. It is not based
on an estimate of clinical field-frequency distribution.

### Tested DICOM Environment

The DICOM RT files used to test this repository were exported by Elekta Monaco
6.2.2:

- RT Plan (`RTPLAN`)
- RT Dose (`RTDOSE`)
- RT Structure Set (`RTSTRUCT`)

The tested DICOM CT files identify the following scanner:

- Manufacturer (`0008,0070`): `GE MEDICAL SYSTEMS`
- Manufacturer's Model Name (`0008,1090`): `Discovery RT`

These values record the environment actually tested for v1.0.0. They do not
claim validation or guaranteed compatibility for other TPS versions, treatment
machines, or CT scanners. The runtime does not reject an input solely because
these identifying DICOM values differ.

Elekta's public
[Infinity brochure](https://www.elekta.com/products/radiation-therapy/infinity/assets/Infinity-Brochure.pdf)
describes Agility leaves across a full `40 x 40 cm2` device field. That is a
cited hardware specification only. It is outside the dicomxphits v1.0.0
software scope and is not supported behavior.

Technical references to Elekta, Agility, Monaco, IAEA, PHITS, or other product
and organization names identify provenance or interfaces only. They do not
imply affiliation, endorsement, certification, or comprehensive compatibility.

## Built-In Public Research Model

The default workspace preparation uses the approved built-in research model:

- a uniform `3 x 3 mm` rectangular photon source centered 100 cm from
  isocenter;
- the bundled 59-bin author-generated spectrum;
- the reviewed rectangular MLC and Y-Diaphragm model, shielding material, and
  PHITS transport settings.

These values were selected and tuned by the repository authors and
collaborators after reviewing literature, manufacturer information, and model
agreement. They are not represented as values copied wholly from one paper,
vendor drawings, facility calibration data, or an exact commissioned clinical
machine. Paschal et al.,
[DOI 10.1002/acm2.13715](https://doi.org/10.1002/acm2.13715), is cited as major
public modeling context rather than as the source of every numeric value.

No machine-configuration file is required for the default. A user-supplied
machine configuration remains an explicit override for research use. Because
the approved factor is bound to the built-in model identity, a changed machine
configuration fails closed as a stale factor unless the caller explicitly
selects `--relative-dose-only`.

## Photon Spectrum Provenance and Dose Calibration

The bundled 59-bin photon spectrum is an author-generated derivative of the
IAEA `ELEKTA_PRECISE_6MV` phase-space dataset. The source dataset was prepared
by Iwan Kawrakow at the National Research Council of Canada and was accessed
from [IAEA Nuclear Data Services](https://www-nds.iaea.org/phsp/photon1/) on
2025-08-06. The repository author generated the derivative with PSFC4PHITS,
PHITS, and Sumtally and authorized its neutral inclusion and redistribution.
The original IAEA phase-space and header files remain external and are neither
bundled nor required by the default runtime.

This derivative is an education and research source model. It is not a
commissioned or exact clinical Elekta beam and is not evidence of IAEA, NRC, or
Elekta endorsement.

Source, geometry, material, transport, and spectrum selection are resolved for
the public research default. The model-specific
`totfact_per_MU = 8.7608E+11 source/MU` was derived from the approved public CT
reference calculation and accepted on 2026-07-30. The default runtime writes
that exact value into PHITS inputs only after the machine-model identity
matches the calibrated public default; a changed model is rejected as a stale
factor before output is created. This is an education and research calibration,
not a commissioned, vendor-approved, or universal clinical beam.

## External Tool Paths

The workflow must keep these paths separate:

- PHITS root folder: used for generated `libpath.inp` `file(1)` values
- PHITS executable path: used for PHITS and Sumtally execution
- phits2dicom executable path: used for RTDOSE conversion

No PHITS or RTphits official distribution file is bundled in this tree.
The user's separately obtained licensed installations are external
prerequisites. The optional Windows CT2PHITS frontend requires the user-supplied
`RTphits_win.bat` and `data/HumanVoxelTable.data`; it never invokes
`ct2phits_win.exe` directly. Workspace preparation requires the raw `DATfiles`
directory emitted through that batch path for a confirmed non-patient phantom,
plus one CT DICOM slice
from that same series. These are input data, not bundled software. Supply them
with `--ct-datfiles-root`, `--ct-reference-dicom`, and
`--confirm-non-patient-phantom`. dicomxphits validates the complete raw
CT2PHITS file set, derives the CT origin and RTPLAN isocenter, checks their
Frame of Reference, and prepares the required PHITS include files. Do not
rename `CTuniverse.dat`, `CTvoxel.dat`, or `CTtrans.dat` by hand.
The default does not require Elekta files, an NDA, paid vendor data, facility
geometry or calibration, or the original IAEA phase-space/header files.

## CT2PHITS Frontend Adapter

On Windows, create a new CT2PHITS workspace below the separately supplied
RT-PHITS root and run the verified batch path explicitly:

```powershell
dicomxphits-run-ct2phits `
  --ct-dicom-root <non-patient-ct-directory> `
  --rtplan <non-patient-rtplan.dcm> `
  --rtphits-root <licensed-rtphits-root> `
  --workspace-root <licensed-rtphits-root>/work/<case-id> `
  --timeout-seconds 300 `
  --confirm-non-patient-phantom
```

If the input directory contains multiple CT series, also pass
`--ct-series-instance-uid <uid>`. The stage refuses non-Windows execution,
missing batch/table prerequisites, an existing workspace, failed or timed-out
execution, and pre-existing, missing, or empty outputs. It writes
`ct2phits_workspace_manifest.json`, `ct2phits_execution_summary.json`, captured
logs, the complete nine-file `DATfiles` inventory, and
`prepared_ct_assets/`. The summary records the eight-file raw handoff validated
by `validate_raw_ct2phits_datfiles()` and the coordinate-corrected assets
created by `prepare_ct2phits_assets()`; generated `CTtrans.dat` is inventoried,
while the downstream transform is the validated `CTtrans.inp`.

The generated handoff can then be supplied to the existing workspace adapter.
Reuse the frontend's frozen RT Plan snapshot so the downstream coordinate
transform is derived from the same RT Plan that the frontend validated:

```powershell
dicomxphits-prepare-3dcrt-workspace `
  --rtplan <ct2phits-workspace>/RTPLAN.dcm `
  --workspace-root <new-public-workspace> `
  --phits-root-folder <licensed-phits-root> `
  --phits-executable-path <licensed-phits-executable> `
  --phits2dicom-executable-path <licensed-phits2dicom-executable> `
  --ct-datfiles-root <ct2phits-workspace>/DATfiles `
  --ct-reference-dicom <ct2phits-workspace>/CT/CT000001.dcm `
  --confirm-non-patient-phantom
```

Neither adapter runs PHITS, Sumtally, phits2dicom, or GPR as part of this
frontend stage.

## Guided Desktop GUI

On Windows, launch the guided Tkinter interface from the repository-local
virtual environment:

```powershell
.\launchers\run_gui_venv.ps1
```

The GUI presents CT2PHITS as the first stage, then keeps workspace preparation,
PHITS, Sumtally, and RTDOSE conversion as separate gated actions. After a
successful CT2PHITS run, it automatically passes the frozen `RTPLAN.dcm`,
`CT/CT000001.dcm`, and `DATfiles` paths to workspace preparation. An existing
validated handoff can still be entered from the advanced workspace controls.

Selecting an RT Plan may suggest its parent as the CT folder and may propose
new workspace names from roots already selected by the user. These suggestions
remain editable. The GUI does not recursively scan for DICOM, discover an
RT-PHITS or PHITS installation, or bypass the explicit non-patient confirmation.

Stable local tool paths and each field's most recent Browse directory are saved
to the ignored `config/dicomxphits.gui.local.json` file. The non-patient
confirmation and overwrite permission are never persisted and always start
cleared. The tracked repository does not contain populated local paths.

## Directory Layout

```text
config/
  dicomxphits.machine.schema.json
  dicomxphits.machine.example.json
  dicomxphits.paths.schema.json
  dicomxphits.paths.example.json
docs/
  manual_smoke_workflow.md
  release_acceptance_evidence.json
  workflow_stages.md
launchers/
  README.md
  run_gui_venv.ps1
src/
  dicomxphits/
    public runtime modules
tests/
  README.md
  synthetic and generic regression tests
templates/
  phits2dicom_rtdose_template.dcm
  README.md
```

All runtime adapters are implemented inside the `dicomxphits` package and do
not import from a private repository layout.

## Prepare Workspace Adapter

The workspace adapter prepares the v1.0.0 starting workspace:

```bash
dicomxphits-prepare-3dcrt-workspace \
  --rtplan synthetic_rtplan.dcm \
  --workspace-root work/synthetic_case \
  --phits-root-folder /opt/phits-root \
  --phits-executable-path /opt/phits-root/bin/phits \
  --phits2dicom-executable-path /opt/phits-root/bin/phits2dicom \
  --ct-datfiles-root /outside/repo/non-patient-ct2phits/DATfiles \
  --ct-reference-dicom /outside/repo/non-patient-ct/CT_slice.dcm \
  --confirm-non-patient-phantom
```

The stage writes a strict segment manifest, `libpath.inp`, generated PHITS input
files, and `analysis/public_preparation_workspace_summary.json`. PHITS execution
is intentionally not performed by this adapter. Strict 3D-CRT segment manifest
and rectangular PHITS input generation use the built-in public research model
and package-owned helper code inside this repository. They do not require a
machine-config argument, private `scripts/` imports, vendor/facility inputs, or
the original IAEA files.

Run the generated active segments explicitly before Sumtally:

```bash
dicomxphits-run-segments \
  --workspace-root work/synthetic_case \
  --phits-executable-path /opt/phits-root/bin/phits
```

The segment runner invokes the PHITS executable using PHITS's `file = ...`
launcher input contract and runs from the workspace root, so all generated
include paths resolve correctly. Do not run a segment by changing the working
directory to `segments/<segment-id>`.

## Sumtally Adapter

The Sumtally adapters prepare and run one all-active-segments totalfield
Sumtally job:

```bash
dicomxphits-generate-sumtally \
  --workspace-root work/synthetic_case \
  --phits-root-folder /opt/phits-root

dicomxphits-run-sumtally \
  --workspace-root work/synthetic_case \
  --phits-executable-path /opt/phits-root/bin/phits
```

The generated Sumtally output is MU-weighted all-segments totalfield output. It
is not a per-beam `beamMU` output. Sumtally input and wrapper generation use
package-owned helper code and do not require private `scripts/` imports.

## RTDOSE Adapter

The RTDOSE adapters prepare and run conversion for the preceding all-segments
totalfield Sumtally output:

```bash
dicomxphits-prepare-rtdose \
  --workspace-root work/synthetic_case \
  --rtplan frozen_ct2phits/RTPLAN.dcm \
  --template-dicom user_template.dcm \
  --ct-reference-dicom user_ct_reference.dcm \
  --phits-out work/synthetic_case/sumtally/phits.out

dicomxphits-run-rtdose \
  --workspace-root work/synthetic_case \
  --phits2dicom-executable-path /opt/phits-root/bin/phits2dicom
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
Referenced non-treatment beams such as `SETUP` are allowed only when the
manifest retains them as skipped, zero-segment-MU evidence; they are excluded
from active treatment coverage. The existing full-plan total and normalization
MU values continue to include every fraction-group referenced beam. Template
plan references are not accepted as provenance.

Sumtally Generate and Sumtally Run record the canonical SHA-256 of that segment
manifest and the SHA-256 values of the generated PHITS wrapper and
`sumtally.inp`. Sumtally Run rejects a `--sum-input` override unless it resolves
to the wrapper recorded by Generate, and rejects either generated input when
its content has changed. RTDOSE Prepare requires the Generate and Run evidence
to match. Sumtally Run also requires the expected dose output to be updated by
that invocation, records its SHA-256, and RTDOSE Prepare verifies that digest
before applying its documented ImagePositionPatient title patch. RTDOSE Run
then verifies the prepared dose digest. For a workspace created before this
evidence was added, rerun Sumtally Generate and Sumtally Run before rerunning
RTDOSE Prepare and RTDOSE Run. Existing segment PHITS outputs remain reusable.

The adapter writes `phits2dicom.inp` as UTF-8 LF stdin content with
slash-normalized paths. The approved public-model `totfact_per_MU` has already
been applied in each PHITS input, so PHITS2DICOM uses Factor `1.0` and the
generated RTDOSE is labeled DICOM `DoseUnits = GY`. Its summaries record
`approved_public_model_totfact_per_mu_applied_in_phits` and the exact factor.
After conversion, `dicomxphits-run-rtdose` synchronizes the output to
`DoseSummationType = PLAN` with exactly one reference to the validated frozen
RT Plan, then creates the accepted `.fixed.dcm` output next to the Sumtally
`.out` file. For the default workflow its path is
`<workspace>/sumtally/deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm`.
The execution summary records the exact path in
`coordinate_corrected_rtdose_output`. This final output maps the supported
PHITS2DICOM `[frames, rows, columns]` voxel
layout to the DICOM patient grid, updates spacing and position consistently,
and preserves stored dose values, `DoseGridScaling`, and the physical volume
center. The run fails instead of accepting an output whose PLAN reference is
missing or stale. Unsupported or ambiguous input geometry also fails closed.

This output is absolute dose only for the defined public education and research
reference model. It does not claim clinical commissioning, universal machine
`Gy/MU` accuracy, vendor approval, or agreement with a physical Elekta unit.

## GPR-comparing Handoff

GPR-comparing remains an external research tool and is not bundled. The public
boundary can either record an explicit knowledge-based skip when the tool is
not configured, prepare the exact external command, or execute it after
checking that both RTDOSE inputs use `GY` and share a `FrameOfReferenceUID`:

```bash
dicomxphits-run-gpr-compare \
  --reference-rtdose reference.dcm \
  --evaluation-rtdose work/synthetic_case/sumtally/deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm \
  --output-dir work/synthetic_case/gpr \
  --gpr-root /path/to/GPR-comparing \
  --dd 3 \
  --dta 3 \
  --cutoff 10 \
  --execute
```

The handoff requires a fresh `run3d.json` from the external process and records
the gamma criteria and pass rate. The example explicitly selects global
`3% / 3 mm` with a `10%` cutoff to match the accepted historical GPR evidence.
The CLI defaults are `3% / 2 mm` with a `10%` cutoff, so criteria must not be
omitted when reproducing the accepted result. The handoff makes no
clinical-validity claim.

## Manual Smoke Workflow

See [docs/manual_smoke_workflow.md](docs/manual_smoke_workflow.md) for the
v1.0.0 smoke workflow.

Real PHITS and phits2dicom smoke execution is optional local validation only and
is not required for CI. Real DICOM files and real-tool outputs must not be
placed in this repository.

## Public Distribution Boundaries

The public distribution intentionally excludes private research runtime,
private release-planning records, real DICOM inputs, local machine
configuration, PHITS and RTphits distributions, credentials, and generated
outputs. Only non-patient test code and the public RTDOSE template are included.
