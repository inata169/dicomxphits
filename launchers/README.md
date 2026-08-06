# Launchers

This directory contains launchers for the public package.

`run_gui_venv.cmd` is the default Windows launcher. It starts
`dicomxphits-gui` with the repository-root `.venv\Scripts\python.exe` and is
not governed by PowerShell's `.ps1` script execution policy.

`run_gui_venv.ps1` provides the equivalent PowerShell entry point where local
policy permits unsigned repository scripts. If PowerShell reports
`PSSecurityException` or a digital-signature error for a Download ZIP copy, keep
that policy in place and use `run_gui_venv.cmd`.

Both launchers add the repository-local `.venv\Scripts` directory to the child
process PATH. They do not select an arbitrary existing virtual environment,
install dependencies, or call private workflow entry points.

The GUI starts with CT2PHITS case setup, keeps later external stages separate,
and uses only the package's public CLI adapters. Standard Windows setup asks
for one PHITS installation folder and validates bounded PHITS 3.35-style
relative candidates without launching an external tool. Nonstandard layouts
remain explicit advanced settings. Validated stable tool paths and
field-specific Browse locations may be stored in the ignored local GUI settings
file; case inputs, derived case output, and safety confirmations are never
restored automatically.
