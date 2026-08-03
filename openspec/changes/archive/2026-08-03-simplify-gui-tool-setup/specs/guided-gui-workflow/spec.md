# Guided GUI Workflow Delta

## ADDED Requirements

### Requirement: Validated Local Tool Profile

The GUI SHALL provide a standard tool-profile mode in which the user selects
one PHITS installation folder. It SHALL resolve the PHITS root, RT-PHITS root,
PHITS executable, and phits2dicom executable only from a bounded set of
supported relative candidate paths below that explicitly selected folder. It
MUST report a missing or ambiguous role without guessing, MUST validate the
required RT-PHITS batch and HU-table markers, and MUST NOT launch any external
tool during profile resolution or setup validation.

#### Scenario: Supported standard installation

- **WHEN** the selected installation folder contains one supported candidate
  for every required tool role and marker
- **THEN** the GUI displays the effective paths and marks the local tool
  profile ready without executing an external program

#### Scenario: Missing standard component

- **WHEN** a required role or marker has no supported candidate below the
  selected installation folder
- **THEN** the GUI identifies that role as missing and keeps dependent external
  stages disabled

#### Scenario: Ambiguous executable candidates

- **WHEN** more than one candidate is eligible for a role and no documented
  deterministic selection rule applies
- **THEN** the GUI reports the ambiguity and does not silently choose an
  executable

#### Scenario: Search boundary

- **WHEN** the user selects an installation folder
- **THEN** the GUI checks only supported relative candidates below that folder
  and does not search drives, registries, environment variables, or unrelated
  directories

### Requirement: Explicit Custom Tool Layout

The GUI SHALL provide a visually subordinate custom-layout mode that must be
explicitly selected before individual tool paths are used. Custom paths SHALL
remain visible and editable and MUST pass the same role, file-type, RT-PHITS
batch, and HU-table validation as a standard profile before dependent external
stages are enabled.

#### Scenario: Valid nonstandard installation

- **WHEN** the user explicitly selects custom-layout mode and supplies every
  required valid path
- **THEN** the GUI accepts the profile and displays its effective paths

#### Scenario: Incomplete custom installation

- **WHEN** a custom path is missing, has the wrong file type, or lacks a
  required RT-PHITS marker
- **THEN** the GUI identifies the invalid role and keeps dependent external
  stages disabled

### Requirement: Automatic CT2PHITS Case Workspace

In standard tool-profile mode the GUI SHALL derive a visible per-case
CT2PHITS workspace below the effective RT-PHITS root from the sanitized source
RT Plan filename. It SHALL treat this path as derived state rather than a
stable tool setting and SHALL recompute it whenever the source RT Plan or
effective RT-PHITS root changes. The normal workflow MUST NOT require manual
workspace entry and MUST continue to reject an existing workspace, the
RT-PHITS root itself, a path outside the accepted RT-PHITS boundary, or a path
inside the dicomxphits repository.

#### Scenario: Standard case setup

- **WHEN** a ready standard tool profile and source RT Plan are selected
- **THEN** the GUI displays a new case workspace derived below the RT-PHITS
  `work` directory without requiring a separate workspace selection

#### Scenario: Source input changes

- **WHEN** the source RT Plan or effective RT-PHITS root changes after a
  workspace was derived
- **THEN** the GUI replaces the stale derived path with the value for the
  current inputs even though the prior field was non-empty

#### Scenario: Derived output already exists

- **WHEN** the derived workspace already exists
- **THEN** the GUI reports that a new output path is required and does not
  overwrite or reuse the directory

## MODIFIED Requirements

### Requirement: Safe Path Suggestions

The GUI SHALL keep every effective external input and workspace path visible.
Standard-profile tool paths and the normal CT2PHITS workspace MAY be read-only
derived values in the primary workflow, while an explicitly selected advanced
custom-layout mode SHALL keep its supported overrides visible and editable.
After explicit RT Plan selection the GUI MAY suggest the selected file's parent
as the CT DICOM root and MAY derive new workspace names from a sanitized
filesystem filename stem and user-configured roots. It MUST NOT recursively
discover DICOM datasets, search for external installations outside an
explicitly selected installation folder, or inspect private tools beyond the
bounded supported path candidates required to validate the local tool profile.

#### Scenario: Empty related case field

- **WHEN** a user selects an RT Plan and the CT DICOM field is empty
- **THEN** the GUI suggests only a path derived from that selection without
  scanning unrelated filesystem content

#### Scenario: Derived workspace state

- **WHEN** standard tool-profile mode is active and the RT Plan or effective
  RT-PHITS root changes
- **THEN** the GUI recomputes its owned CT2PHITS workspace while preserving
  unrelated explicit user values

#### Scenario: Explicit custom value

- **WHEN** advanced custom-layout mode is active and a supported override
  contains an explicit user value
- **THEN** the GUI preserves that value instead of silently replacing it with a
  standard-layout candidate

### Requirement: Local GUI Settings and Independent Browse History

The GUI SHALL load and save backward-compatible local settings from the ignored
GUI settings path. It SHALL persist the selected installation folder, profile
mode, stable custom tool paths, and a separate last Browse directory for each
path field. It SHALL revalidate restored tool settings on launch. It MUST NOT
persist per-case CT or RT Plan inputs, a derived CT2PHITS workspace,
non-patient confirmation, or overwrite permission, and MUST fall back safely
when the local settings file is missing, invalid, or unreadable.

#### Scenario: Repeated standard configuration

- **WHEN** a user validates and saves a standard local tool profile and later
  reopens the GUI
- **THEN** the GUI restores the selected installation folder, revalidates its
  derived roles, and reports current readiness

#### Scenario: Legacy flat settings

- **WHEN** an existing settings file contains the previously supported flat
  tool-path keys
- **THEN** the GUI preserves them, selects standard mode only when they match a
  supported standard layout, and otherwise retains them as an explicit custom
  layout

#### Scenario: Independent Browse fields

- **WHEN** a user browses in two different path fields
- **THEN** reopening either dialog starts from that field's own most recently
  accepted directory

#### Scenario: Safety state restart

- **WHEN** the GUI starts with saved local settings
- **THEN** non-patient confirmation and overwrite permission are both false
