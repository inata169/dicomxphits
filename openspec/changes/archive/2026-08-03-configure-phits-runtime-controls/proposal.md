# Configure Windows PHITS Runtime Controls

## Why

The guided Windows workflow currently resolves the serial
`bin/phits_win.exe` launcher even when the PHITS 3.35 distribution contains
the OpenMP executable requested for practical segment calculations. A manual
non-patient phantom test therefore started a substantially slower serial run.

Workspace preparation also embeds the fixed defaults `maxcas = 1000000`,
`maxbch = 10`, and `$OMP = 8` in every segment input without exposing them in
the GUI. Users cannot deliberately choose the histories, batches, or OpenMP
thread count for a new research workspace, and the preparation summary does
not present those choices as explicit runtime evidence.

The PHITS manual defines `$OMP=N` as the supported directive before the first
input section. The dollar sign is therefore required syntax, not a disabled
setting. When dicomxphits directly invokes an OpenMP executable, its segment
adapter also maps the same value to `OMP_NUM_THREADS`.

## What Changes

- Resolve `bin/phits335_win_openmp.exe` as the standard PHITS 3.35 Windows
  executable instead of the serial `bin/phits_win.exe`.
- Resolve the Windows-specific `phits2dicom_win.exe` deterministically in the
  standard Windows profile so the distributed Linux and macOS executables do
  not make that role ambiguous.
- Add explicit GUI fields for PHITS `maxcas`, `maxbch`, and OpenMP thread
  count, with defaults `1000000`, `10`, and `8` respectively.
- Validate all three values as positive integers before workspace creation and
  pass them through the accepted workspace-preparation CLI.
- Render the selected values into every newly prepared segment input and
  preserve the official `$OMP = N` syntax. Continue to set
  `OMP_NUM_THREADS=N` when the segment adapter directly invokes PHITS.
- Record the effective values in preparation evidence and persist the last
  valid GUI values as non-sensitive local performance settings.
- Keep Sumtally generation settings and existing prepared workspaces
  unchanged.
- Add synthetic/mock tests and update the Windows GUI documentation.

## Impact

- Affected capabilities: `guided-gui-workflow` and new
  `phits-segment-runtime` contract
- Affected runtime: `src/dicomxphits/gui.py`,
  `src/dicomxphits/gui_tool_profile.py`,
  `src/dicomxphits/prepare_3dcrt_workspace.py`, and the existing PHITS input
  rendering boundary
- Affected tests: synthetic GUI command/configuration tests, standard-profile
  layout tests, workspace preparation tests, and segment environment tests
- Affected local configuration: ignored `config/dicomxphits.gui.local.json`
- Affected documentation: Windows guided workflow and runtime-control guidance
- Unchanged boundaries: fixed-field 3D-CRT geometry, DICOM interpretation,
  machine model, dose calibration, MU semantics, CT2PHITS execution contract,
  Sumtally inputs, and protected-data rules
- External execution: not authorized by this proposal; automated validation
  remains synthetic/mock only and the currently running manual calculation is
  not modified
