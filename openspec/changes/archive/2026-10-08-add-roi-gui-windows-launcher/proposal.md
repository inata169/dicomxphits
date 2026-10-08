# Change: Add a Windows launcher for the standalone ROI GUI

## Why

The user requested a batch entry point for the standalone ROI GUI. A shortcut
can start in a different working directory, so the launcher needs to locate
the checkout's Python and GUI script from its own directory. The first PR
review identified that this supported entry point was missing from the current
OpenSpec contract.

## What Changes

- Record the repository-root Windows batch launcher as an entry point for the
  independent ROI GUI.
- Specify checkout-relative Python and script resolution, a clear failure when
  the virtual environment is absent, and propagation of the GUI process status.
- Keep the existing GUI, analysis, DICOM, physics, and report contracts intact.

## Impact

The batch launcher, English and Japanese usage guides, and the standalone ROI
GUI specification are affected. The user requested the launcher and explicitly
authorized addressing PR review feedback without another approval step. This
proposal records the already implemented launcher contract for PR #91; it does
not authorize any additional runtime capability.
