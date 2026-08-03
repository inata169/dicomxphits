# Workflow Stages

The v1.0.0 workflow is staged. A later stage must not run
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
- Workspace preparation requires the raw `DATfiles` emitted by `ct2phits.exe`
  for a confirmed non-patient phantom and one CT DICOM slice from that same
  series. Pass them with `--ct-datfiles-root`, `--ct-reference-dicom`, and
  `--confirm-non-patient-phantom`.
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
during setup validation. A missing or ambiguous role keeps only its dependent
stages disabled and is reported explicitly; a nonstandard or future layout can
be entered through custom-layout controls.

In standard mode, selecting an RT Plan derives a new CT2PHITS case output below
the effective RT-PHITS `work` directory. That output is derived state:
changing the RT Plan or RT-PHITS root replaces a stale non-empty value. Stable
tool profile settings and per-field Browse history may be stored only in the
ignored local GUI settings file. Case inputs, the derived CT2PHITS output,
confirmation, and overwrite controls are not persisted.

## Prepare Workspace Adapter

`dicomxphits-prepare-3dcrt-workspace` validates the RT Plan and generates the
strict segment manifest and PHITS workspace using package-owned runtime code.

This adapter writes:

- `segments/segment_manifest.json`
- `libpath.inp`
- `analysis/phits_generation_summary.json`
- `analysis/public_preparation_workspace_summary.json`

It does not execute PHITS. GUI controls keep PHITS, Sumtally, and
RTDOSE conversion as separate gated stages.

## PHITS Segment Execution

`dicomxphits-run-segments` executes the active segment inputs from the strict
manifest and writes `analysis/segment_execution_summary.json`. Every active
segment must produce its manifest `expected_output_path` before Sumtally. It
uses PHITS's `file = ...` launcher input contract and runs from the workspace
root so the generated include files resolve.

## Sumtally Adapter

The Sumtally stage is split into `dicomxphits-generate-sumtally` and
`dicomxphits-run-sumtally`.

The primary Sumtally job covers all active strict 3D-CRT segments and records
this fixed contract:

- `sumtally_scope = all_active_segments`
- `sumtally_mode = totalfield`
- `weight_field = segment_mu`
- `sumtally_normalization = all_segments_totalfield_segment_mu`
- `rt_dose_conversion_hint.is_beam_mu_output = false`

This output must not be treated as a per-beam `beamMU` RTDOSE input by later
stages.

## RTDOSE Adapter

The RTDOSE stage is split into `dicomxphits-prepare-rtdose` and
`dicomxphits-run-rtdose`.

It consumes the preceding all-active-segments totalfield Sumtally output and
records the conversion contract:

- `input_dose_state = sumtally_mu_weighted`
- `sumtally_normalization = all_segments_totalfield_segment_mu`
- `is_beam_mu_output = false`
- `input_dose_unit = gy_per_mu`
- `output_dicom_dose_unit = GY`
- `factor = 1.0`
- `totfact_per_MU = 8.7608E+11 source/MU` is already applied in PHITS
- `normalization_rule = approved_public_model_totfact_per_mu_applied_in_phits`

The adapter requires the frozen RT Plan used for workspace preparation, a
user-specified template DICOM, and a CT reference selected by the public
workflow priority. User-provided DICOM files are copied into the workspace
before use; source files are not modified in place. The RT Plan SOP Instance
UID, Frame of Reference, workflow mode, treatment-beam coverage, and MU totals
must match the accepted segment manifest before conversion can proceed.
The supplied frozen RT Plan must match the full-file SHA-256 recorded in the
adjacent completed CT2PHITS workspace manifest. For a legacy handoff without
that record, rebuilding the segment geometry with the manifest's sampling
policy must reproduce the stored segments exactly.
Fraction-group referenced non-treatment beams such as `SETUP` are excluded from
active treatment coverage only when the manifest preserves them as skipped,
zero-segment-MU entries. Their referenced beam meterset may be zero but must be
finite and nonnegative. The manifest's plan, included, and normalization MU
totals remain the full referenced-beam totals, so this validation does not
alter the existing Sumtally normalization.
Sumtally Generate and Sumtally Run must also contain the same canonical
segment-manifest SHA-256 as the current workspace and matching SHA-256 values
for the generated PHITS wrapper and `sumtally.inp`. Sumtally Run executes only
the recorded wrapper path and fails before PHITS execution if either generated
input changed. Generate also records every active segment output and every
recursively resolved `infl` file consumed by the wrapper; Run revalidates the
dependency set and digests before PHITS execution. Missing or mismatched
evidence fails before RTDOSE conversion. The expected Sumtally dose output must
be newly created or have a changed SHA-256 from the recorded Run; timestamp-only
updates are rejected. Its SHA-256 is verified by RTDOSE Prepare before the IPP
title patch, and the post-patch SHA-256 is verified by RTDOSE Run.
Legacy workspaces regenerate and rerun Sumtally using their existing unchanged
segment PHITS outputs before RTDOSE preparation.
RTDOSE Prepare also records the generated `phits2dicom.inp` SHA-256; RTDOSE Run
verifies it immediately before launching the converter. The workspace template,
CT reference, prepared Sumtally dose, and companion `phits.out` referenced by
that input are also hashed during Prepare and revalidated before launch.
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
validation, and the approved factor identity. The result is absolute dose only
for the defined public education and research model. It is not evidence of clinical
commissioning, universal machine `Gy/MU` accuracy, vendor approval, or
agreement with a physical Elekta unit.

The conversion stage then creates the accepted separate `.fixed.dcm` file next
to the Sumtally dose output. The execution summary identifies it as
`coordinate_corrected_rtdose_output`. It transposes
the supported PHITS2DICOM voxel layout from `[frames, rows, columns]` to
`[rows, frames, columns]`, updates `PixelSpacing`,
`GridFrameOffsetVector`, and `ImagePositionPatient`, and preserves the physical
volume center and dose values. The final file is reopened and its PLAN
summation, frozen-plan reference, Frame of Reference, and GY units are checked
before success is reported. Ambiguous frame offsets, unsupported orientation,
or stale plan references fail before a corrected output is accepted.

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
