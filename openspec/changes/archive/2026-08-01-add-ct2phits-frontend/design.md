# CT2PHITS Frontend Design

## Context

CT2PHITS is an external Windows tool distributed through RT-PHITS. Existing
`dicomxphits` code already validates eight raw DATfiles and prepares the six CT
assets used by downstream workspace preparation. The missing boundary was the
safe orchestration from a DICOM CT directory through the external batch file to
those validators.

The input and coordinate contracts come from the reviewed legacy specifications
`openspec/50-ct2phits-procedure.md` and
`openspec/51-cttrans-coordinate-fix.md`. The frontend must preserve those
contracts without reimplementing HU conversion, coordinate transformation, or
the physical model.

## Goals and Non-Goals

### Goals

- Select one internally consistent axial HFS CT series.
- Prepare an isolated and reproducible RT-PHITS workspace.
- Invoke the verified batch adapter and capture auditable execution evidence.
- Distinguish the nine generated files, eight raw downstream files, and six
  prepared assets.
- Reuse existing validation and coordinate-transformation code.

### Non-Goals

- Reimplement CT2PHITS, HU conversion, coordinate conversion, or physics.
- Invoke `ct2phits_win.exe` directly.
- Run PHITS, Sumtally, phits2dicom, or GPR-comparing.
- Bundle official distribution files or persist real DICOM or calculation
  results in the repository.
- Claim clinical suitability or Linux validation of the real RT-PHITS tool.

## Decisions

### Separate CLI Stage

The frontend is a standalone CLI rather than an implicit part of workspace
preparation. This preserves explicit external-execution authorization and makes
failure evidence available before downstream work starts.

### External Workspace Boundary

The workspace MUST be a new directory below the supplied RT-PHITS root and
outside the public repository. Existing output is never overwritten. Selected
CT slices are copied with deterministic names so the external input is stable
without modifying source DICOM files.

### Verified Batch Adapter

Windows invokes `RTphits_win.bat` through `cmd.exe`. The frontend does not
discover installations and never calls the executable directly. It requires
the supplied batch file and HU table before creating a workspace.

### Output Contracts

CT2PHITS generates nine files: the eight raw DATfiles accepted by
`validate_raw_ct2phits_datfiles()` plus `CTtrans.dat`. `CTtrans.dat` is retained
in the inventory only. `prepare_ct2phits_assets()` reuses the existing reviewed
coordinate logic and creates the six downstream assets, including the validated
`CTtrans.inp`.

### Auditable Failure Handling

The stage records stdout and stderr even on failure. A summary records timeout,
return code, failure reason, paths, inventory, and hashes. Missing, empty,
symbolic-link, or stale generated outputs fail closed.

### Test Boundary

Automated tests use synthetic DICOM and fake runners only. Real RT-PHITS smoke
execution is optional, human-directed, external to the repository, and not a CI
requirement.

## Risks and Mitigations

- External batch behavior can vary by installation. Require the reviewed file
  layout, capture logs, and validate outputs rather than trusting process exit
  alone.
- DICOM ambiguity can select the wrong series. Reject multiple series unless a
  Series Instance UID is explicitly selected and validate geometry metadata.
- Old DATfiles can masquerade as new results. Require a new workspace and reject
  outputs older than the current execution start.
- Coordinate roles can be confused. Keep `CTtrans.dat` inventory-only and reuse
  the existing `CTtrans.inp` generator.

## Migration Plan

The feature is additive. Existing callers may continue supplying already
validated DATfiles. At approved task completion, promote the accepted delta
requirements into `openspec/specs/ct2phits-frontend/spec.md` and archive this
change on the same branch before handoff.

## Completion State

The accepted requirements were promoted and this change was archived with
human authorization on 2026-08-01. Workplace Dev Container cross-validation
and Draft PR creation remain explicitly deferred, non-blocking handoff items.
