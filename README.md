# dicomxphits

dicomxphits is an education and research workflow for preparing strict
fixed-field 3D-CRT PHITS inputs from DICOM RT Plans and for controlling the
explicit PHITS, Sumtally, RTDOSE, coordinate-correction, and external GPR
handoff stages.

Within its documented non-patient phantom scope, this repository is a working
public implementation of that complete chain rather than only a proposal that
the interfaces might be connected. It provides a bounded engineering
demonstration—a constructive proof of feasibility—for an openly inspectable
and modifiable DICOM-to-PHITS-to-RTDOSE research workflow.

It is not clinical commissioning, patient QA, vendor certification, or a
substitute for independent clinical validation. Real patient DICOM, licensed
tool distributions, and real-tool outputs must remain outside this repository.

## Status

Version 1.0.1 includes standalone public adapters for strict 3D-CRT workspace
preparation, PHITS segment execution, Sumtally generation and execution,
RTDOSE conversion and coordinate correction, and an optional external
GPR-comparing handoff. See the [v1.0.1 release notes](docs/release-notes-v1.0.1.md)
for the changes since v1.0.0.

## Supported Environment

The supported use depends on the host environment. Installing the Python
package on a platform does not by itself mean that the complete external-tool
workflow is supported there.

| Environment | Documented use | Important boundary |
| --- | --- | --- |
| Windows host with Python 3.12 | Guided desktop GUI and the public CLI adapters, including the Windows CT2PHITS frontend and explicitly authorized real-tool workflow | The supplied GUI launcher and `RTphits_win.bat` adapter are Windows-only. Licensed external tools and confirmed non-patient inputs remain user-supplied and outside this repository. |
| Linux or the project Dev Container | Python 3.12 development, synthetic/mock tests, CLI validation, and the public-tree audit | The Dev Container is not a real-tool runtime. It does not support the Windows CT2PHITS frontend or the supplied PowerShell GUI launcher. |
| GitHub Actions on Ubuntu and Windows | Python 3.12 synthetic/mock compilation, tests, and public-tree validation | CI does not run PHITS, RT-PHITS, CT2PHITS, Sumtally, phits2dicom, GPR, or real DICOM. |
| macOS | Outside the v1 support range | Package installation or partial Python execution must not be interpreted as support for the guided workflow or external tools. |

The documented guided GUI workflow is therefore a Windows-host workflow. The
repository's Linux Dev Container is a separate development and validation
environment; its Python installation does not create the Windows host
`.venv` required by the launcher. Python 3.12 is the only supported Python
runtime for v1. Python 3.11 and earlier and Python 3.13 and later are outside
the v1 support range; this statement does not claim that every later version
is technically incapable of running any part of the package.

## Windows GUI Quick Start

On a Windows host, run the following commands from the repository root in
PowerShell. Do not run this launcher from the Linux Dev Container terminal.

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\launchers\run_gui_venv.cmd
```

Confirm that the first command reports Python 3.12. If the Python launcher is
unavailable, use `python --version` only when it reports Python 3.12, then run
`python -m venv .venv`. The `.cmd` launcher is the default Windows entry point
because it is not governed by PowerShell's `.ps1` script execution policy. It
adds the repository-local `.venv\Scripts` directory to the child process PATH
and starts the GUI with that environment's Python.

The equivalent PowerShell launcher remains available where local policy allows
unsigned repository scripts:

```powershell
.\launchers\run_gui_venv.ps1
```

If PowerShell reports `PSSecurityException` or says that the downloaded script
is not digitally signed, keep the machine or organization execution policy in
place and use `run_gui_venv.cmd`. Neither launcher creates an environment,
installs dependencies, or reuses the Dev Container's Linux Python. See
[Guided Desktop GUI](#guided-desktop-gui) for tool setup and case-path behavior.
For the complete v1.0.x walkthrough, see the
[GUI User Guide](docs/gui-user-guide.md).

## Workflow at a Glance

The guided workflow keeps each stage explicit and gated:

1. **CT2PHITS** — on Windows, `dicomxphits-run-ct2phits` invokes the
   user-supplied `RTphits_win.bat` for a confirmed non-patient phantom; it never
   calls `ct2phits_win.exe` directly.
2. **Workspace Prepare** — validate the frozen handoff and prepare strict
   fixed-field 3D-CRT PHITS inputs.
3. **PHITS** — explicitly run every active segment.
4. **Sumtally Generate / Run** — generate and explicitly execute the
   all-active-segments totalfield Sumtally job.
5. **RTDOSE Prepare / Run** — prepare conversion, invoke phits2dicom, and apply
   the validated coordinate-correction handoff.
6. **Optional GPR** — execute the external comparison or record an explicit
   knowledge-based skip.

## What This Repository Demonstrates

The public adapters implement the path from non-patient phantom DICOM CT and
RT Plan inputs, through the user-supplied CT2PHITS handoff, fixed-field 3D-CRT
PHITS input generation and segment calculation, Sumtally dose aggregation,
DICOM RT Dose conversion and coordinate correction, to an external
GPR-comparing comparison using a TPS-derived RT Dose as the reference and the
coordinate-corrected PHITS-derived RTDOSE as the evaluation.

Two bounded non-patient phantom cases have been confirmed by the author to
complete this end-to-end workflow: a centered `20 × 20 cm²` field on a water
phantom and a case using the PHITSgeoTest plan. A read-only review of four
locally retained comparison reports and their run logs mapped one record to
PHITSgeoTest, two records to the same centered water-phantom case, and one
record to a separate non-patient phantom. The PHITSgeoTest case produced a
Gamma Passing Rate of at least 95%. The two centered water-phantom records
produced values around 95%, slightly below 95% in both records.

All four records used global `3% / 3 mm` gamma with a `10%` dose cutoff,
global-maximum normalization, linear interpolation, and an interpolation
fraction of 3. A separate non-patient phantom record also produced a passing
rate of at least 95%. The available evidence for that record establishes the
comparison outcome, but not the human-confirmed completion of the full chain
used to define the two demonstrated cases, so it is retained only as supporting
comparison evidence. Exact individual pass rates, external paths, identifiers,
and result files are not published.

This is a working end-to-end demonstration within a deliberately narrow
research scope. It demonstrates that the public implementation and external
tool handoffs can be made operational; it does not demonstrate clinical
accuracy, commissioning, general machine compatibility, or suitability for
patient QA. The reported Gamma Passing Rates are research observations, not
clinical acceptance thresholds or QA decisions. See
[Public Feasibility Demonstration](docs/public-feasibility-demonstration.md)
for the evidence and reproducibility boundaries.

## v1.0.x Workflow

The v1.0.x workflow is intentionally narrow:

- strict 3D-CRT RT Plan input
- strict MU gate before downstream stages
- generated PHITS input workspace through public adapters
- explicit PHITS execution stage
- explicit Sumtally generation and execution stage
- explicit RTDOSE conversion stage

Each stage must write command metadata, return code when executed, stdout and
stderr capture paths or content, major input and output paths, and a summary JSON
path.

## v1.0.x Supported Scope

For v1.0.x, dicomxphits supports fixed-field 3D-CRT up to the centered
`20 × 20 cm²` effective-aperture boundary for education and research. After
DICOM Control Point inheritance is resolved, the jaw and MLC common effective
aperture at every Control Point must remain inside the closed collimator-local
isocenter-plane box from `-100.000 mm` to `+100.000 mm` on both X and Y. Each
effective width must also be no greater than `200.000 mm`.

A centered `20 × 20 cm²` aperture is therefore the largest square at the
boundary. A narrower offset aperture is eligible only when every effective
point remains inside the same box. The workflow rejects overruns rather than
clipping, recentering, or expanding the source cone.

The v1 scope is fixed-field 3D-CRT only. IMRT, dynamic MLC delivery, and VMAT
are outside the supported scope.

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

These values record the environment originally documented for v1.0.0. They do not
claim validation or guaranteed compatibility for other TPS versions, treatment
machines, or CT scanners. The runtime does not reject an input solely because
these identifying DICOM values differ.

Elekta's public
[Infinity brochure](https://www.elekta.com/products/radiation-therapy/infinity/assets/Infinity-Brochure.pdf)
describes Agility leaves across a full `40 × 40 cm²` device field. That is a
cited hardware specification only. It is outside the dicomxphits v1.0.x
software scope and is not supported behavior.

Technical references to Elekta, Agility, Monaco, IAEA, PHITS, or other product
and organization names identify provenance or interfaces only. They do not
imply affiliation, endorsement, certification, or comprehensive compatibility.

## Built-In Public Research Model

The default workspace preparation uses a deliberately simplified built-in
public research model:

- a uniform `3 × 3 mm` rectangular photon source centered in a beam-aligned
  source plane located `100 cm` upstream of isocenter;
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

## Why a Simplified Public Model Matters

The simplification is an intentional trade-off. The built-in source, spectrum,
rectangular MLC and Y-Diaphragm geometry, materials, and transport settings can
be inspected, discussed, and modified without vendor-confidential machine
drawings, NDA-protected information, facility-specific commissioning data, or
proprietary Monaco beam-model data. Licensed PHITS and RT-PHITS tools remain
external prerequisites and are not redistributed here.

This openness makes the workflow useful as a research baseline even though the
model does not reproduce a specific clinical Elekta unit, a proprietary
Monaco beam-model configuration, or a commercial treatment-machine digital
twin, and it carries no vendor certification. Its replaceable research-model
components let investigators supply a different configuration and study more
detailed source, MLC, jaw, material, or transport descriptions. A changed
model requires its own calibration and validation; the default dose factor is
deliberately rejected or must be
disabled with `--relative-dose-only`. The value is the public, inspectable
foundation and demonstrated workflow, not a claim that the simplified model
already has clinical-machine fidelity.

## Photon Spectrum Provenance and Dose Calibration

The bundled 59-bin photon spectrum is an author-generated derivative of part 1
of the IAEA `ELEKTA_PRECISE` 6 MV phase-space dataset, identified by
`ELEKTA_PRECISE_6mv_part1.IAEAphsp` and its matching `.IAEAheader`. The source
dataset was prepared by Iwan Kawrakow at the National Research Council of
Canada and was accessed from
[IAEA Nuclear Data Services](https://www-nds.iaea.org/phsp/photon1/) on
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
factor before output is created. This education and research calibration
carries no clinical commissioning, vendor certification, or universal
clinical-beam claim.

## External Tool Paths

The workflow must keep these paths separate:

- PHITS root folder: used for generated `libpath.inp` `file(1)` values
- PHITS executable path: used for PHITS and Sumtally execution
- phits2dicom executable path: used for RTDOSE conversion

The guided Windows GUI normally derives these separate runtime paths from one
`PHITS installation folder`. Its initial supported standard profile is the
PHITS 3.35-style Windows layout:

```text
<PHITS installation folder>/
├─ bin/phits335_win_openmp.exe
└─ utility/RTphits/
   ├─ RTphits_win.bat
   ├─ data/HumanVoxelTable.data
   └─ bin/phits2dicom_win.exe
```

The standard profile selects the PHITS 3.35 OpenMP executable and the exact
Windows phits2dicom executable. Linux and macOS phits2dicom files distributed
beside it do not create an ambiguity. The GUI checks only these bounded
relative paths and does not run an external tool during setup validation. A
future or nonstandard layout remains usable through the explicit custom-layout
controls; the GUI does not silently fall back to the serial PHITS executable.

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
  --maxcas 1000000 `
  --maxbch 10 `
  --omp-threads 8 `
  --ct-datfiles-root <ct2phits-workspace>/DATfiles `
  --ct-reference-dicom <ct2phits-workspace>/CT/CT000001.dcm `
  --confirm-non-patient-phantom
```

Neither adapter runs PHITS, Sumtally, phits2dicom, or GPR as part of this
frontend stage.

## Guided Desktop GUI

Use the [Windows GUI Quick Start](#windows-gui-quick-start) to create the
Python 3.12 environment and launch the guided Tkinter interface. The details
below describe the guided workflow after launch.

The GUI presents CT2PHITS as the first stage, then keeps workspace preparation,
PHITS, Sumtally, and RTDOSE conversion as separate gated actions. After a
successful CT2PHITS run, it automatically passes the frozen `RTPLAN.dcm`,
`CT/CT000001.dcm`, and `DATfiles` paths to workspace preparation. An existing
validated handoff can still be entered from the advanced workspace controls.

RTDOSE remains a two-step action. After **Prepare RTDOSE** succeeds, the GUI
shows **Prepared**, disables the prepare action, and makes **Run RTDOSE** the
next available action. Only **Run RTDOSE** invokes phits2dicom and creates the
raw and coordinate-corrected DICOM outputs. **Completed** requires a successful
independent final coordinate-placement validation. Legacy Prepare/Run success
summaries without placement proof are not accepted: the GUI returns to
**Not run**, and explicit Prepare/Run clicks may replace only those legacy
successful summaries. Failed summaries and current evidence keep the normal
overwrite guards. A successful prepare summary must
be reused rather than prepared again. If an upstream Sumtally rerun invalidates
that preparation, explicitly select **Allow overwrite of downstream stage
summaries** to re-enable **Prepare RTDOSE**; the RTDOSE adapter still validates
the new evidence and fails closed if it is inconsistent. The GUI reports
`Completed` only when the Prepare summary is bound to the current Sumtally
evidence and the Run summary records the exact current Prepare-summary digest.
Stale success summaries are retained for audit but do not enable **Run RTDOSE**.

For first-time standard setup, open **Tool settings**, select the licensed
**PHITS installation folder**, and choose **Validate and save setup**. After
that, a normal case requires only the source RT Plan and CT DICOM folder. The
GUI derives a visible new CT2PHITS case output below
`<RT-PHITS root>/work/`; changing the RT Plan or effective RT-PHITS root
replaces the previous derived value instead of retaining a stale workspace.

Selecting an RT Plan may suggest its parent as the CT folder. Explicit CT input
values remain editable, while standard-profile tool paths and CT2PHITS case
output are read-only derived values. The GUI does not recursively scan for
DICOM, search the computer for installations, run setup-time external tools,
or bypass the explicit non-patient confirmation. Use **Custom layout
(advanced)** only when the installed distribution does not match the displayed
PHITS 3.35-style relative layout.

Before **Prepare workspace**, the Workspace page exposes `maxcas` (histories
per batch), `maxbch` (batches), and OpenMP threads. Their defaults are
`1000000`, `10`, and `8`; each must be a positive integer. The selected values
are written only into newly prepared segment inputs and their summaries. They
do not rewrite an existing workspace or change Sumtally settings. The generated
first line remains `$OMP = N`: the dollar sign is official PHITS OpenMP syntax,
not a comment marker. Direct segment execution also passes the same value as
`OMP_NUM_THREADS=N` to the selected OpenMP executable.

The validated profile, stable local tool paths, valid segment runtime
preferences, and each field's most recent Browse directory are saved to the ignored
`config/dicomxphits.gui.local.json` file. The per-case RT Plan, CT folder,
derived CT2PHITS output, non-patient confirmation, and overwrite permission are
never persisted and always start empty or cleared. Existing flat tool settings
are retained as a custom layout unless they match the supported standard
profile. The tracked repository does not contain populated local paths.

## Key Files and Directories

This is a selected map of the public tree, not an exhaustive directory listing.

```text
config/
  dicomxphits.machine.schema.json
  dicomxphits.machine.example.json
  dicomxphits.paths.schema.json
  dicomxphits.paths.example.json
docs/
  development-handoff-2026-08-07.md
  development-handoff-2026-08-06.md
  gui-user-guide.md
  manual_smoke_workflow.md
  public-feasibility-demonstration.md
  release_acceptance_evidence.json
  windows-gui-launcher-validation-2026-08-06.md
  workflow_stages.md
launchers/
  README.md
  run_gui_venv.cmd
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

## Detailed CLI Reference

The real-tool examples below use Windows PowerShell and placeholder paths
outside the repository. They require separately obtained licensed tools and an
explicitly confirmed non-patient phantom; they are not Dev Container commands.

### Prepare Workspace Adapter

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

### Sumtally Adapter

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

### RTDOSE Adapter

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
records its SHA-256, and
RTDOSE Prepare verifies that digest before copying the dose and companion
phits.out into rtdose/DATfiles. The documented ImagePositionPatient title patch
is applied only to those private copies; Prepare records before/after source
hashes and fails if either upstream file changes. RTDOSE Run verifies both the
unchanged upstream evidence and the prepared-copy digests.

An older workspace changed by the historical in-place IPP title patch remains
reusable only when restoring the hash-bound segment T-Deposit title, including
the historical LF/CRLF normalization, exactly reproduces the Sumtally Run
SHA-256. Recovery bytes are used only for the private converter copy. Any
additional or ambiguous difference fails closed. An older successful handoff
without explicit mesh fields otherwise remains reusable when its segment
outputs and accepted Sumtally output match their recorded SHA-256 values and
contain one consistent mesh header. If reconstruction cannot be proven, rerun
Sumtally Generate and Sumtally Run before rerunning RTDOSE Prepare and Run.
Existing segment PHITS outputs remain reusable without PHITS transport.
For a workspace with stale or factor-one weighted-average evidence, select
**Allow overwrite of downstream stage summaries**, then rerun **Sumtally
Generate**, **Sumtally Run**, **Prepare RTDOSE**, and **Run RTDOSE**. Existing
digest-bound segment PHITS outputs remain reusable; PHITS transport does not
need to be rerun solely for this normalization correction. Old Sumtally or
DICOM outputs must not be repaired with an empirical scale factor.

The adapter writes `phits2dicom.inp` as UTF-8 LF stdin content with
slash-normalized paths and records its SHA-256 during RTDOSE Prepare. RTDOSE Run
rejects the file if it changed before converter launch. Prepare also records
the SHA-256 of every file named by that input: the workspace template, CT
reference, staged Sumtally dose copy, and staged companion `phits.out`. Run revalidates
all four files immediately before conversion. The converter output must also
be new or have a changed SHA-256; a timestamp-only change fails before plan
reference synchronization. For PHITS `isumtally = 2`, `X = F * sum((r_j / sum(r)) * X_j)`. The
workflow uses active treatment-segment MU as `r_j` and their sum as `F`, so the
Sumtally result is `sum(active_segment_mu * segment_dose_per_mu)` in `GY`.
The approved public-model `totfact_per_MU` is applied in each PHITS segment and
the treatment MU is applied once by Sumtally. PHITS2DICOM therefore keeps
Factor `1.0` and the generated RTDOSE is labeled DICOM `DoseUnits = GY`. Its
summaries record
`approved_public_model_totfact_per_mu_applied_in_phits` and the exact factor.
After conversion, `dicomxphits-run-rtdose` synchronizes the output to
`DoseSummationType = PLAN` with exactly one reference to the validated frozen
RT Plan, then creates the accepted `.fixed.dcm` output next to the Sumtally
`.out` file. For the default workflow its path is
`<workspace>/sumtally/deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm`.
The execution summary records the exact path in
`coordinate_corrected_rtdose_output`. This final output maps the supported
PHITS tally `(y, z, reversed x)` bin-centre layout to the DICOM patient grid
through the frozen-plan isocenter and `I + 10 * (-x, z, y)` millimetre
mapping. The converter CT slice position is compatibility metadata, not final
placement evidence. Stored dose values and `DoseGridScaling` are preserved.
The final DICOM is reopened and its first, centre, edge, and final voxel
positions must match the bound tally geometry with zero relative tolerance and
`1e-6 mm` absolute component tolerance. The run fails instead of accepting an
output whose coordinate placement, PLAN reference, or mesh evidence is missing,

This output is absolute dose only for the defined public education and research
reference model. It does not claim clinical commissioning, universal machine
`Gy/MU` accuracy, certification by a vendor, or agreement with a physical Elekta unit.

### GPR-comparing Handoff

[GPR-comparing](https://github.com/inata169/GPR-comparing) remains an external
research tool and is not bundled. The public boundary can either record an
explicit knowledge-based skip when the tool is
not configured, prepare the exact external command, or execute it after
checking that both RTDOSE inputs use `GY` and share a `FrameOfReferenceUID`:

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

### Advanced and Maintenance Commands

`dicomxphits-prepare-ct-calibration` prepares the explicit CT calibration
workflow; it is not part of the normal guided case sequence.
`dicomxphits-fix-rtdose-coordinates` exposes the standalone RTDOSE coordinate
correction operation for controlled maintenance or investigation. The normal
RTDOSE Run stage performs its accepted correction handoff automatically.

## Related Documentation

- [Public feasibility demonstration and research boundaries](docs/public-feasibility-demonstration.md)
- [GUI User Guide for v1.0.x](docs/gui-user-guide.md)
- [Windows GUI launcher validation — 2026-08-06](docs/windows-gui-launcher-validation-2026-08-06.md)
- [Development handoff — 2026-08-07](docs/development-handoff-2026-08-07.md)
- [Development handoff — 2026-08-06](docs/development-handoff-2026-08-06.md)
- [Manual smoke workflow](docs/manual_smoke_workflow.md)
- [Workflow stages and gates](docs/workflow_stages.md)
- [CT2PHITS frontend handoff](docs/ct2phits-frontend-handoff.md)
- [Development and Dev Container guidance](docs/development.md)
- [Current project status](docs/project-status.md)

## Related Repositories

- [GPR-comparing](https://github.com/inata169/GPR-comparing) is the separate
  external research tool used by the optional gamma-comparison handoff. It is
  not bundled with dicomxphits, and its outputs must stay outside this
  repository.
- [dicom4dicomxphits](https://github.com/inata169/dicom4dicomxphits) is a private,
  data-only companion repository containing anonymized DICOM CT, RT Plan, and
  RT Dose examples for dicomxphits. Access requires GitHub authorization. Its
  examples remain non-patient research and education data and do not establish
  clinical validity.

Real PHITS and phits2dicom smoke execution is optional local validation only and
is not required for CI. Real DICOM files and real-tool outputs must not be
placed in this repository.

## Public Distribution Boundaries

The public distribution intentionally excludes private research runtime,
private release-planning records, real DICOM inputs, local machine
configuration, PHITS and RTphits distributions, credentials, and generated
outputs. The only tracked DICOM file is the sanitized, zero-dose public RTDOSE
template at `templates/phits2dicom_rtdose_template.dcm`; synthetic test data are
generated in code, and no patient DICOM or real-tool result is included.
