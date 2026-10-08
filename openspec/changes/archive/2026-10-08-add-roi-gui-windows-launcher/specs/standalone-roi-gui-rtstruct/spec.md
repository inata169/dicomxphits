## ADDED Requirements

### Requirement: Windows batch entry point for the standalone ROI GUI

The repository SHALL provide `run_phits_roi_stats_gui.bat` at its root as a
Windows entry point for the independent ROI GUI. The launcher SHALL resolve
the GUI script and `.venv/Scripts/python.exe` relative to the batch file's
directory, so its behavior does not depend on the caller's working directory.
It SHALL report a missing virtual-environment Python with a nonzero exit
status and SHALL return the GUI process's exit status when launched.

#### Scenario: Start from a shortcut with another working directory

- **WHEN** a shortcut targets the batch file in the checkout and starts from
  another directory
- **THEN** the launcher uses that checkout's virtual-environment Python and
  standalone GUI script

#### Scenario: Virtual-environment Python is absent

- **WHEN** the launcher cannot find `.venv/Scripts/python.exe` beside the
  checkout's GUI script
- **THEN** it reports the missing dependency and exits unsuccessfully

#### Scenario: GUI process exits

- **WHEN** the GUI process exits with a status code
- **THEN** the launcher returns that status code to its caller
