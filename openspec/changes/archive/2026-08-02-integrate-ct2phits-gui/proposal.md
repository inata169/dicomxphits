# Integrate the CT2PHITS GUI Workflow

## Why

The public GUI currently starts at downstream workspace preparation and asks
the user to provide DATfiles that were created manually. That workflow no
longer matches the accepted Windows CT2PHITS frontend added in pull request 3.
The GUI also presents every path with equal visual weight, does not persist
stable local tool settings, reuses the most recent file-dialog location across
unrelated fields, and reports low-level failures without enough stage context.

## What Changes

- Add the existing `dicomxphits-run-ct2phits` adapter as the first guided GUI
  stage without reimplementing or bypassing its safety checks.
- Separate source-case inputs, local tool settings, derived CT2PHITS handoff,
  downstream stage controls, and execution evidence into a clear workflow.
- Suggest safe paths from an explicitly selected RT Plan and configured roots,
  without recursively discovering DICOM data or external installations.
- After successful CT2PHITS execution, automatically use the frozen RT Plan,
  CT reference, and DATfiles produced by that workspace for downstream
  preparation.
- Persist stable local settings and a separate Browse location for each path
  field in the ignored local GUI settings file. Never persist overwrite or
  non-patient confirmation state.
- Modernize the Tkinter interface with a keyboard-usable `ttk` layout, an
  accessible dark navy and blue visual system, stage status, focused errors,
  and non-blocking stage execution.
- Preserve the existing manual validated-DATfiles handoff as an advanced path
  for compatibility, while making the integrated frontend the default flow.
- Add synthetic/mock tests and update public GUI documentation.

## Impact

- Affected capability: new `guided-gui-workflow` contract integrating the
  accepted `ct2phits-frontend` capability
- Affected runtime: `src/dicomxphits/gui.py` and, if needed for maintainable
  separation, a small GUI-state or theme helper under `src/dicomxphits/`
- Affected tests: `tests/test_gui.py` plus focused GUI state and command tests
- Affected local configuration: ignored `config/dicomxphits.gui.local.json`
- Affected documentation: GUI launch and workflow guidance
- Unchanged boundaries: fixed-field 3D-CRT scope, DICOM geometry and coordinate
  meaning, PHITS physics, dose, MU, machine model, and all CT2PHITS frontend
  validation and external-execution gates
