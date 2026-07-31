# Launchers

This directory contains launchers for the public package.

`run_gui_venv.ps1` starts `dicomxphits-gui` with the repository-root
`.venv\Scripts\python.exe`. It does not select an arbitrary existing virtual
environment, install dependencies, or call private workflow entry points.
