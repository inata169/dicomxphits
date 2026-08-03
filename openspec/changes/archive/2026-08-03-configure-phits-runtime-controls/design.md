# Design: Configure Windows PHITS Runtime Controls

## Context

The standard Windows tool profile is explicitly a PHITS 3.35 layout, but it
currently hard-codes `bin/phits_win.exe`. The user's installed 3.35 tree also
contains `bin/phits335_win_openmp.exe`, which is the intended executable for
parallel segment execution. The same installation contains platform-specific
`phits2dicom_lin.exe`, `phits2dicom_mac.exe`, and
`phits2dicom_win.exe`; treating all three as eligible Windows candidates makes
an otherwise standard installation fail validation.

`render_ct_runtime_input` already has internal defaults for histories,
batches, and OpenMP threads. It writes `$OMP = N` before the first PHITS
section. `run_segments.phits_environment` reads that directive and sets
`OMP_NUM_THREADS` because the adapter invokes the selected executable directly
rather than through `phits.bat`.

The PHITS 3.36 user manual documents `$OMP=N` as the supported input command
for shared-memory parallel execution. It separately states that direct
command-line execution of an OpenMP executable requires `OMP_NUM_THREADS`.
Removing the dollar sign would therefore replace documented syntax with an
unsupported PHITS parameter and is not part of this change.

## Goals

- Make the PHITS 3.35 Windows standard profile choose its OpenMP executable.
- Make the three existing segment runtime constants explicit and editable at
  the workspace-preparation boundary.
- Keep each prepared workspace self-describing and reproducible.
- Reject malformed settings before any workspace files or external processes
  are created.
- Preserve the official `$OMP` syntax and the direct-executable environment
  mapping.

## Non-Goals

- Changing the current manual run or rewriting an existing workspace.
- Automatically choosing a thread count from host hardware.
- Supporting MPI or hybrid execution.
- Changing Sumtally's separately controlled input parameters.
- Changing dose calibration, geometry, DICOM semantics, or clinical scope.
- Discovering arbitrary executable names or future PHITS layouts outside the
  bounded standard-profile contract.

## Decisions

### 1. Keep the standard PHITS 3.35 layout exact and bounded

The standard profile will resolve
`<installation>/bin/phits335_win_openmp.exe`. It will not silently fall back
to the serial executable. A missing OpenMP executable remains a visible
profile error, and users with another supported local layout can explicitly
select the custom profile.

For phits2dicom, the standard Windows profile will check the exact
`<installation>/utility/RTphits/bin/phits2dicom_win.exe` path. Linux and macOS
executables in the same distribution are not Windows candidates. Both paths
remain below the explicitly selected installation folder and receive the
existing file and containment validation.

### 2. Configure runtime values when creating the workspace

The Workspace page will expose three fields:

- `maxcas` (histories per batch), default `1000000`
- `maxbch` (number of batches), default `10`
- OpenMP threads, default `8`

All fields accept decimal positive integers only. There is no arbitrary upper
bound, but zero, negative values, booleans, fractions, whitespace-only input,
and non-decimal text fail before workspace preparation starts. The GUI passes
the effective values to new CLI options `--maxcas`, `--maxbch`, and
`--omp-threads`. The CLI applies the same validation so GUI bypass cannot
weaken the contract.

These settings affect only PHITS segment inputs created by the preparation
stage. The stage's existing no-overwrite behavior prevents a setting change
from silently rewriting an already prepared workspace.

### 3. Preserve one source of truth for OpenMP threads

Every generated segment input will retain the documented first-line form
`$OMP = N`. The direct-executable segment adapter will continue reading that
line and setting `OMP_NUM_THREADS=N` for the child process. This keeps the
prepared input, the executed environment, and the GUI-selected value aligned.

The supported GUI and CLI range is positive integers. Although PHITS batch
launchers document `$OMP=0` as an all-core shortcut, `OMP_NUM_THREADS` for a
direct OpenMP executable requires an explicit positive thread count. The GUI
therefore does not offer zero.

### 4. Persist convenience values and record execution evidence

The ignored local GUI settings file will persist the last valid values because
they are stable machine/performance preferences and contain no case or patient
data. Missing, legacy, malformed, or unreadable settings fall back to
`1000000`, `10`, and `8`.

`phits_generation_summary.json` and the enclosing workspace preparation
summary will record the effective values. Each generated input remains the
authoritative per-segment execution artifact. No PHITS executable is run by
workspace preparation.

## Risks and Mitigations

- **Very large history or batch values can create long runs.** The GUI labels
  their meaning and validates type and positivity, while leaving research
  sizing under explicit user control.
- **An OpenMP executable may be absent in a nonstandard installation.** The
  standard profile fails visibly; custom mode remains available instead of
  silently selecting a slow serial binary.
- **A user may interpret `$` as a comment marker.** GUI and README guidance
  identify `$OMP` as official PHITS syntax and explain the environment mapping.
- **Legacy local settings may contain no new fields.** Versioned,
  backward-compatible loading supplies the documented defaults.

## Validation Strategy

- Unit-test standard resolution with the exact PHITS 3.35 OpenMP and Windows
  phits2dicom paths, plus missing/wrong-platform cases.
- Unit-test GUI default loading, persistence migration, positive-integer
  validation, and workspace command construction.
- Unit-test CLI validation before workspace mutation and exact propagation to
  every generated segment input and summary.
- Retain the segment-runner assertion that `$OMP = N` becomes
  `OMP_NUM_THREADS=N`.
- Run only synthetic/mock automated checks; do not invoke PHITS or private
  DICOM tooling.
