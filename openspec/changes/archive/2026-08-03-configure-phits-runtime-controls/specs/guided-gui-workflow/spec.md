# Guided GUI Workflow Delta

## ADDED Requirements

### Requirement: Explicit Segment Runtime Controls

The GUI SHALL expose decimal positive-integer controls for segment `maxcas`,
`maxbch`, and OpenMP thread count on the workspace-preparation stage. It SHALL
default them to `1000000`, `10`, and `8`, pass the effective values through the
accepted workspace-preparation CLI, and reject invalid values before starting
a subprocess. It SHALL explain that these values apply to newly prepared
segment inputs and do not rewrite existing workspaces or control Sumtally.

#### Scenario: Default runtime preparation

- **WHEN** a user keeps the initial runtime controls and prepares a new
  workspace
- **THEN** the GUI requests segment inputs with `maxcas = 1000000`,
  `maxbch = 10`, and `$OMP = 8`

#### Scenario: Explicit runtime preparation

- **WHEN** a user enters three valid positive integers and prepares a new
  workspace
- **THEN** the GUI passes those exact values to workspace preparation and the
  resulting evidence presents them as the effective segment runtime settings

#### Scenario: Invalid runtime value

- **WHEN** any runtime control is empty, zero, negative, fractional, or
  non-decimal text
- **THEN** the GUI identifies the invalid field and starts no subprocess

#### Scenario: Existing prepared workspace

- **WHEN** runtime controls change after a workspace has already been prepared
- **THEN** the GUI does not rewrite that workspace and requires the existing
  new-workspace preparation contract for the new values to take effect

## MODIFIED Requirements

### Requirement: Validated Local Tool Profile

The GUI SHALL provide a standard PHITS 3.35 Windows tool-profile mode in which
the user selects one PHITS installation folder. It SHALL resolve the PHITS
root, RT-PHITS root, `bin/phits335_win_openmp.exe`, and
`utility/RTphits/bin/phits2dicom_win.exe` only from the documented bounded
relative paths below that explicitly selected folder. It MUST report a missing
role without guessing, MUST validate the required RT-PHITS batch and HU-table
markers, and MUST NOT launch any external tool during profile resolution or
setup validation. Linux and macOS phits2dicom executables distributed beside
the Windows executable MUST NOT make the standard Windows role ambiguous.

#### Scenario: Supported PHITS 3.35 Windows installation

- **WHEN** the selected installation folder contains the required markers,
  `bin/phits335_win_openmp.exe`, and
  `utility/RTphits/bin/phits2dicom_win.exe`
- **THEN** the GUI selects the two Windows executables, displays the effective
  paths, and marks the local tool profile ready without executing a program

#### Scenario: OpenMP executable missing

- **WHEN** the standard profile lacks `bin/phits335_win_openmp.exe` even if a
  serial PHITS executable is present
- **THEN** the GUI identifies the OpenMP executable as missing and does not
  silently fall back to serial execution

#### Scenario: Other-platform converter siblings

- **WHEN** Linux or macOS phits2dicom executables are present beside
  `phits2dicom_win.exe`
- **THEN** the GUI still resolves the exact Windows executable without an
  ambiguity error

#### Scenario: Search boundary

- **WHEN** the user selects an installation folder
- **THEN** the GUI checks only the documented relative paths below that folder
  and does not search drives, registries, environment variables, or unrelated
  directories

### Requirement: Local GUI Settings and Independent Browse History

The GUI SHALL load and save backward-compatible local settings from the ignored
GUI settings path. It SHALL persist the selected installation folder, profile
mode, stable custom tool paths, valid segment `maxcas`, `maxbch`, and OpenMP
thread preferences, and a separate last Browse directory for each path field.
It SHALL revalidate restored tool and runtime settings on launch. It MUST NOT
persist per-case CT or RT Plan inputs, a derived CT2PHITS workspace,
non-patient confirmation, or overwrite permission, and MUST fall back safely
when the local settings file is missing, invalid, or unreadable.

#### Scenario: Repeated runtime preferences

- **WHEN** a user saves valid segment runtime values and later reopens the GUI
- **THEN** the GUI restores those values as local performance preferences

#### Scenario: Invalid or legacy runtime preferences

- **WHEN** the local settings file omits a runtime field or contains an invalid
  runtime value
- **THEN** the GUI uses the corresponding documented default without restoring
  unsafe or malformed state

#### Scenario: Safety state restart

- **WHEN** the GUI starts with saved local settings
- **THEN** non-patient confirmation and overwrite permission are both false
