# Workflow Stages

The v1.0.x workflow is staged. A later stage must not run
until the previous stage gate has passed.

## Stages

1. Run the independent Windows CT2PHITS frontend for a confirmed non-patient
   phantom, or explicitly select an existing validated handoff, and validate
   its raw DATfiles handoff.
2. Prepare a strict 3D-CRT segment manifest and PHITS input workspace.
3. Run PHITS explicitly.
4. Generate and run Sumtally explicitly.
5. Convert the Sumtally output to RTDOSE and correct its patient coordinates.
6. Execute the external GPR comparison or record an explicit knowledge-based
   skip.
7. Review summaries and logs.

## Gate Rules

- All non-skipped segments must be strict 3D-CRT.
- At least one non-skipped segment must be present before downstream stages can
  run.
- Beam MU must be present, positive, and finite.
- PHITS root folder, PHITS executable path, and phits2dicom executable path are
  separate runtime roles. The guided Windows GUI normally resolves them from
  one explicitly selected PHITS installation folder and validates each role
  before enabling its dependent stage.
- Workspace preparation requires the raw `DATfiles` emitted through the Windows
  `dicomxphits-run-ct2phits` frontend and the user-supplied `RTphits_win.bat`
  for a confirmed non-patient phantom, plus one CT DICOM slice from that same
  series. Pass them with `--ct-datfiles-root`, `--ct-reference-dicom`, and
  `--confirm-non-patient-phantom`. The workflow never invokes the CT2PHITS
  executable directly.
- Workspace preparation validates CT/RTPLAN Frame of Reference, supported axial
  HFS orientation, CT origin, and a shared referenced-beam isocenter before it
  writes the workspace.
- The CT reference priority for RTDOSE conversion is:
  1. user-specified CT reference DICOM
  2. generated CT with synchronized reference identity
  3. synthetic smoke-test-only dummy CT

The synthetic dummy CT option is not the default for clinical-like workflow
review.

## CT2PHITS Frontend Adapter

`dicomxphits-run-ct2phits` is an independent, explicit Windows-only stage. It
selects one CT series, copies it into a new user-selected workspace below the
supplied RT-PHITS root, writes an OpenSpec-compatible `ct2phits.inp`, and calls
the supplied `RTphits_win.bat`. It does not discover an RT-PHITS installation
or invoke `ct2phits_win.exe` directly.

The stage inventories all nine generated files, rejects pre-existing, missing,
or empty output, records SHA-256 digests and process logs, and hands the
eight downstream raw files plus the copied CT reference to the existing CT
asset preparation functions. `CTtrans.dat` remains part of the nine-file
generation inventory; downstream geometry uses the validated `CTtrans.inp`
created by the existing coordinate-processing path.

The guided desktop GUI invokes this accepted CLI as its first stage. It does
not reproduce the frontend logic. When the execution summary reports
completion, the GUI applies the documented frozen handoff paths inside that
workspace to the next preparation stage. The source RT Plan remains distinct
from the frozen downstream snapshot.

The GUI's standard profile checks only the approved PHITS 3.35-style Windows
relative paths below an explicitly selected PHITS installation folder. It does
not recursively search for external installations and does not run any tool
during setup validation. The standard executable is
`bin/phits335_win_openmp.exe`, and the Windows converter is
`utility/RTphits/bin/phits2dicom_win.exe`; adjacent Linux and macOS converter
files are ignored. A missing role keeps only its dependent stages disabled and
is reported explicitly; a nonstandard or future layout can be entered through
custom-layout controls.

In standard mode, selecting an RT Plan derives a new CT2PHITS case output below
the effective RT-PHITS `work` directory. That output is derived state:
changing the RT Plan or RT-PHITS root replaces a stale non-empty value. Stable
tool profile settings and per-field Browse history may be stored only in the
ignored local GUI settings file. Case inputs, the derived CT2PHITS output,
confirmation, and overwrite controls are not persisted.

An existing calculation is reopened through the distinct **Open existing
case…** action. Selecting one 3D-CRT workspace triggers read-only validation of
the strict manifest, the current v5 IEC gantry/MLCX/collimator/CT-accelerator
topology contract, zero-error PHITS geometry diagnostics, and every recorded
active-output SHA-256. PHITS transport is reusable only when that current v5
geometry contract and all three Category-I counters validate. Any v4, older,
missing, mixed, or ambiguous geometry provenance or geometry-diagnostic
evidence requires newly prepared v5 segment inputs and rerunning PHITS,
Sumtally, and RTDOSE regardless of recorded angles, field, or CT FOV; a
final-DICOM mirror cannot repair transport produced with an obsolete geometry
convention. A
standard-profile `*-3dcrt` case may restore exactly one corresponding
`*-ct2phits` handoff below the validated RT-PHITS work root; no drive or DICOM
search is performed. When PHITS evidence is reusable, Workspace Prepare and
PHITS execution remain disabled and **Create DICOM RT Dose** runs only the
required downstream suffix after preserving conflicts in workspace-local
recovery history.

## Prepare Workspace Adapter

`dicomxphits-prepare-3dcrt-workspace` validates the RT Plan and generates the
strict segment manifest and PHITS workspace using package-owned runtime code.

For HFS with couch zero, the generated source direction is
`(sin(g), 0, cos(g))` in PHITS coordinates. The source remains one SAD upstream
of isocenter and the accelerator `tr3` transform maps its local `+Z` axis onto
that same direction. Under `DICOM = I + 10 * (-PHITS x, PHITS z, PHITS y)`, the
patient-coordinate beam direction is `(-sin(g), cos(g), 0)`. Gantry zero output
is unchanged.

This adapter writes:

- `segments/segment_manifest.json`
- `libpath.inp`
- `analysis/phits_generation_summary.json`
- `analysis/public_preparation_workspace_summary.json`

It does not execute PHITS. GUI controls keep PHITS, Sumtally, and
RTDOSE conversion as separate gated stages.

Workspace preparation accepts positive `--maxcas`, `--maxbch`, and
`--omp-threads` values, defaulting to `1000000`, `10`, and `8`. The effective
values are written to every newly generated segment input and recorded in both
preparation summaries. They do not alter existing workspaces or Sumtally
inputs.

It also accepts an optional `--calculation-config-path` for the 3D dose tally.
The closed v1 JSON contract uses inclusive first/last voxel centres and voxel
sizes in millimetres; exact decimal validation derives PHITS centimetre edges
and counts before the workspace is changed. One semantic mesh digest is bound
to every active segment. Omission preserves the legacy 101 x 101 x 101, 3 mm
3D tally byte for byte, and the PDD tally is unchanged in both cases. See
[Calculation Configuration](calculation-configuration.md).

This configuration is an upstream request, not downstream geometry authority.
Sumtally continues to compare complete geometry parsed from every actual active
segment output. RTDOSE continues to derive placement from the accepted actual
Sumtally output and rejects missing, stale, ambiguous, or inconsistent evidence.

## PHITS Segment Execution

`dicomxphits-run-segments` executes the active segment inputs from the strict
manifest and writes `analysis/segment_execution_summary.json`. Every active
segment must produce its manifest `expected_output_path` before Sumtally. It
uses PHITS's `file = ...` launcher input contract and runs from the workspace
root so the generated include files resolve.
Every generated segment begins with PHITS's documented `$OMP = N` command.
Because the adapter directly invokes the OpenMP executable, it requires that
directive and passes the same positive value as `OMP_NUM_THREADS=N`. `$` is
part of the PHITS command syntax and must not be removed.

## Sumtally Adapter

The Sumtally stage is split into `dicomxphits-generate-sumtally` and
`dicomxphits-run-sumtally`.

The primary Sumtally job covers all active strict 3D-CRT segments and records
this fixed contract:

- `sumtally_scope = all_active_segments`
- `sumtally_mode = totalfield`
- `weight_field = segment_mu`
- `sumtally_normalization = active_treatment_segments_totalfield_segment_mu_sum`
- `sumfactor = sum(active treatment segment_mu)`
- `rt_dose_conversion_hint.is_beam_mu_output = false`

For PHITS `isumtally = 2`, the external-tool equation is
`X = F * sum((r_j / sum(r)) * X_j)`. The public workflow sets each `r_j` to
the active treatment segment MU and `F` (`sumfactor`) to their finite positive
sum. The result is therefore
`sum(active_segment_mu * segment_dose_per_mu)`, in `GY`. A validated skipped
`SETUP` or other non-treatment beam remains in complete plan provenance but
has zero segment MU and contributes no file weight or `sumfactor`. This output
must not be treated as a per-beam `beamMU` RTDOSE input.

## RTDOSE Adapter

The RTDOSE stage is split into `dicomxphits-prepare-rtdose` and
`dicomxphits-run-rtdose`.

In the guided GUI, a successful Prepare summary changes the RTDOSE state to
`Prepared`, disables **Prepare RTDOSE**, and enables **Run RTDOSE**. The Run
action is the step that invokes phits2dicom and creates the DICOM output. The
GUI changes the state to `Completed` only when the execution summary contains
a successful independent final coordinate-placement validation and the current
versioned PLAN course-dose fraction contract. Legacy Prepare/Run success
summaries without placement or fraction proof are not accepted. The
GUI returns to `Not run` and permits explicit Prepare/Run actions to replace
only those legacy successful summaries; failed summaries and current evidence
retain the normal overwrite guards.
Selecting a workspace with a successful Prepare summary restores that state;
repeating Prepare is not required and does not replace the successful state
with a validation failure. If upstream Sumtally evidence is regenerated after
Prepare, select **Allow overwrite of downstream stage summaries** to re-enable
Prepare and generate a new binding before Run. This permission is not persisted,
and the RTDOSE adapter remains responsible for validating the replacement
evidence. The GUI reports `Completed` only when the Prepare summary matches
the current Sumtally binding and the execution summary records the exact current
Prepare-summary SHA-256. Stale successful summaries remain auditable but return
the GUI to `Not run` or `Prepared` and cannot enable a stale Run.

In existing-case mode, the primary action is **Create DICOM RT Dose**. Depending
on current verified evidence it runs Sumtally Generate through RTDOSE Run,
RTDOSE Prepare through Run, or RTDOSE Run alone. It stops on the first failed
accepted adapter. Completion displays the coordinate-corrected `.fixed.dcm`
path as the standard DICOM patient-coordinate output; internal IEC coordinates
are not mislabeled as a DICOM patient coordinate system.

It consumes the preceding all-active-segments totalfield Sumtally output and
records the conversion contract:

- `input_dose_state = sumtally_active_treatment_mu_sum`
- `sumtally_normalization = active_treatment_segments_totalfield_segment_mu_sum`
- `is_beam_mu_output = false`
- `input_dose_unit = GY`
- `output_dicom_dose_unit = GY`
- `public_model_base_factor = 1.0`
- `planned_fraction_count = NumberOfFractionsPlanned`
- `factor = 1.0 * NumberOfFractionsPlanned`
- `course_dose = dose_per_fraction * NumberOfFractionsPlanned`
- `totfact_per_MU = 8.7608E+11 source/MU` is already applied in PHITS
- `normalization_rule = approved_public_model_totfact_per_mu_applied_in_phits`

The adapter requires the frozen RT Plan used for workspace preparation, a
user-specified template DICOM, and a CT reference selected by the public
workflow priority. User-provided DICOM files are copied into the workspace
before use; source files are not modified in place. The RT Plan SOP Instance
UID, Frame of Reference, workflow mode, treatment-beam coverage, and MU totals
must match the accepted segment manifest before conversion can proceed. The
public PLAN path requires exactly one Fraction Group with a finite positive
integer `NumberOfFractionsPlanned`; it does not guess a default or combine
multiple Fraction Groups.
The supplied frozen RT Plan must match the full-file SHA-256 recorded in the
adjacent completed CT2PHITS workspace manifest. For a legacy handoff without
that record, rebuilding the segment geometry with the manifest's sampling
policy must reproduce the stored segments exactly.
Fraction-group referenced non-treatment beams such as `SETUP` are excluded from
active treatment coverage only when the manifest preserves them as skipped,
zero-segment-MU entries. Their referenced beam meterset may be zero but must be
finite and nonnegative. The manifest's plan, included, and normalization MU totals remain the full
referenced-beam totals. Their difference from the active treatment-segment MU
sum must be explained exactly by validated skipped non-treatment BeamMeterset
values. Only the active treatment-segment MU sum is used as Sumtally
`sumfactor`.
Sumtally Generate and Sumtally Run must also contain the same canonical
segment-manifest SHA-256 as the current workspace and matching SHA-256 values
for the generated PHITS wrapper and `sumtally.inp`. Sumtally Run executes only
the recorded wrapper path and fails before PHITS execution if either generated
input changed. Generate also records every active segment output and every
recursively resolved `infl` file consumed by the wrapper; Run revalidates the
dependency set and digests before PHITS execution. Missing or mismatched
evidence fails before RTDOSE conversion. The expected Sumtally dose output must
be newly created or have a changed SHA-256 from the recorded Run; timestamp-only
updates are rejected. RTDOSE Prepare verifies the recorded SHA-256, copies the
dose and companion phits.out into rtdose/DATfiles, and applies the IPP title
patch only to those private copies. It records source hashes before and after
Prepare and fails if an upstream file changes. Run revalidates both source and
prepared-copy evidence.
For a workspace changed by the historical in-place IPP title patch, Prepare
may recover the pre-patch bytes only when the hash-bound segment T-Deposit
title and historical LF/CRLF normalization exactly reproduce the Sumtally Run
SHA-256. It writes recovered bytes only to the private copy and rejects every
additional or ambiguous difference. Older handoffs without explicit mesh
fields may otherwise reconstruct the mesh from digest-bound, unchanged segment
outputs and accepted Sumtally output. Unproven reconstruction requires rerunning
Sumtally Generate and Run with the existing segment PHITS outputs.
RTDOSE Prepare also records the generated phits2dicom.inp SHA-256; Run verifies
it before converter launch. The template, CT reference, staged dose, and staged
phits.out referenced by that input are hashed and revalidated before launch.
The frozen RT Plan fraction count and versioned course-dose evidence are also
revalidated before launch. A changed count requires a new RTDOSE Prepare.
For a legacy factor-one weighted-average workspace, select **Allow overwrite
of downstream stage summaries**, then rerun **Sumtally Generate**, **Sumtally
Run**, **Prepare RTDOSE**, and **Run RTDOSE**. Existing digest-bound segment
PHITS outputs are reused; PHITS transport does not need to be rerun solely for
this normalization correction. Do not empirically rescale an old Sumtally or
DICOM output.
For a legacy RTDOSE labeled `PLAN` without current fraction-count provenance,
rerun **Prepare RTDOSE** and **Run RTDOSE**. Current digest-bound PHITS and
Sumtally results may be reused for this fraction-only correction. If the result
also uses the stale nonzero-gantry transport contract, regeneration must begin
with PHITS and continue through Sumtally and RTDOSE.
The produced RTDOSE must likewise be new or have a different SHA-256 from any
preexisting expected output. A timestamp-only change fails before plan-reference
synchronization.

The template DICOM must be a phits2dicom-compatible RTDOSE base template with
the overwrite tags required by phits2dicom already present. The public tree
includes `templates/phits2dicom_rtdose_template.dcm`, a sanitized zero-dose
RTDOSE template for this purpose. Prepare fails before execution when required
tags are missing. Public workflows must not fall back to
repository-local PHITS or RTphits sample files.

After successful conversion, the generated DICOM is explicitly labeled
`DoseUnits = GY` and `DoseSummationType = PLAN`. Its single
`ReferencedRTPlanSequence` item is synchronized to the validated frozen RT
Plan; stale fraction-group or beam references inherited from the template are
removed. The sidecar summary records the same semantics, exact plan-reference
validation, one-fraction input state, planned fraction count, base factor
`1.0`, and effective course factor. Plan-reference synchronization and
coordinate correction preserve the already course-scaled physical dose; they
do not apply fraction scaling after conversion. The result is absolute dose only
for the defined public education and research model. It is not evidence of clinical
commissioning, universal machine `Gy/MU` accuracy, vendor approval, or
agreement with a physical Elekta unit.

The conversion stage then creates the accepted separate `.fixed.dcm` file next
to the Sumtally dose output. The execution summary identifies it as
`coordinate_corrected_rtdose_output`. Final placement is derived from the
hash-bound frozen-plan isocenter and tally mesh, not from the converter CT
slice's `ImagePositionPatient`. Tally bounds are bin edges and output
`(frame, row, column)` maps to PHITS `(y, z, reversed x)` bin centres through
`I + 10 * (-x, z, y)` in DICOM millimetres. The CT position written into the
converter input is compatibility metadata only.

The corrected output uses shape `(ny, nz, nx)`, identity axial
`ImageOrientationPatient`, `PixelSpacing = [10*dz, 10*dx]`, and relative
`GridFrameOffsetVector[f] = 10*f*dy`. Stored dose values and
`DoseGridScaling` are preserved. The final file is reopened and its first,
centre, edge, and final voxel positions are independently checked with zero
relative tolerance and `1e-6 mm` absolute component tolerance. PLAN summation,
frozen-plan reference, Frame of Reference, and GY units are also checked before
success is reported. Missing or inconsistent mesh evidence, unsupported
orientation, placement residuals, or stale plan references fail before a
corrected output is accepted.

## GPR-comparing Boundary

`dicomxphits-run-gpr-compare` keeps GPR-comparing external. With no configured
tool root it writes a reasoned skip record. With a configured tool it can
prepare or explicitly execute `python -m rtgamma.main`. Execution requires
matching `FrameOfReferenceUID` values, `GY` dose units, a zero process return
code, and a fresh `run3d.json`. The resulting pass rate is research evidence,
not clinical certification. The accepted historical evidence uses global
`3% / 3 mm` with a `10%` cutoff. Because the CLI defaults are `3% / 2 mm` with
a `10%` cutoff, reproduction of the accepted criterion must pass
`--dd 3 --dta 3 --cutoff 10` explicitly.

## Manual Smoke Workflow

The smoke workflow is documented in `manual_smoke_workflow.md`. Automated
coverage uses synthetic-only mocked external tools and writes generated DICOM,
fake PHITS outputs, fake RTDOSE files, logs, and summaries only under pytest
temporary directories.

Real PHITS and phits2dicom smoke execution is optional local validation only,
not a CI requirement. Real DICOM files must not be placed in this repository.
