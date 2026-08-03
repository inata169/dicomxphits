# Guided GUI Workflow Specification

## Purpose

Define the safe, usable desktop workflow that invokes the accepted CT2PHITS
frontend, validates a local tool profile without executing it, preserves the
frozen handoff, remembers stable local settings without persisting case or
safety state, and keeps later fixed-field 3D-CRT stages separately gated.

## Requirements

### Requirement: Integrated CT2PHITS GUI Stage

The GUI SHALL expose the accepted Windows CT2PHITS frontend as the first guided
stage and SHALL invoke `dicomxphits-run-ct2phits` without a shell. It MUST pass
the user-supplied CT DICOM root, source RT Plan, RT-PHITS root, new CT2PHITS
workspace, optional CT series UID, positive timeout, and explicit non-patient
phantom confirmation. It MUST NOT invoke `ct2phits_win.exe` directly or
duplicate the frontend's DICOM, workspace, process, or output validation.

#### Scenario: Confirmed guided execution

- **WHEN** a Windows user supplies the required paths, selects a new CT2PHITS
  workspace, and explicitly confirms non-patient phantom data
- **THEN** the GUI invokes the accepted CT2PHITS CLI with the corresponding
  arguments and displays its execution evidence

#### Scenario: Missing explicit confirmation

- **WHEN** the non-patient phantom confirmation is not selected
- **THEN** the GUI rejects CT2PHITS execution before starting a subprocess

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

### Requirement: Frozen CT2PHITS Handoff

After the CT2PHITS execution summary reports completion, the GUI SHALL set the
downstream preparation inputs to the documented frozen RT Plan, CT reference,
and DATfiles paths inside that CT2PHITS workspace. It SHALL keep the existing
manual validated-DATfiles handoff available as an advanced compatibility path.

#### Scenario: Completed frontend handoff

- **WHEN** the accepted CT2PHITS stage completes successfully
- **THEN** downstream preparation uses `<ct2phits-workspace>/RTPLAN.dcm`,
  `<ct2phits-workspace>/CT/CT000001.dcm`, and
  `<ct2phits-workspace>/DATfiles`

#### Scenario: Failed or incomplete frontend

- **WHEN** CT2PHITS execution fails or lacks a completed summary
- **THEN** the GUI does not claim or automatically apply a successful frozen
  handoff

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

### Requirement: Local GUI Settings and Independent Browse History

The GUI SHALL load and save backward-compatible local settings from the ignored
GUI settings path. It SHALL persist the selected installation folder, profile
mode, stable custom tool paths, valid segment `maxcas`, `maxbch`, and OpenMP
thread preferences, and a separate last Browse directory for each path field.
It SHALL revalidate restored tool and runtime settings on launch. It MUST NOT
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

#### Scenario: Repeated runtime preferences

- **WHEN** a user saves valid segment runtime values and later reopens the GUI
- **THEN** the GUI restores those values as local performance preferences

#### Scenario: Invalid or legacy runtime preferences

- **WHEN** the local settings file omits a runtime field or contains an invalid
  runtime value
- **THEN** the GUI uses the corresponding documented default without restoring
  unsafe or malformed state

#### Scenario: Independent Browse fields

- **WHEN** a user browses in two different path fields
- **THEN** reopening either dialog starts from that field's own most recently
  accepted directory

#### Scenario: Safety state restart

- **WHEN** the GUI starts with saved local settings
- **THEN** non-patient confirmation and overwrite permission are both false

### Requirement: Guided RTDOSE State and Reprepare Recovery

The GUI SHALL derive the guided RTDOSE state from readable, successful RTDOSE
Prepare and Run summaries. It SHALL present `Not run` when neither summary
proves success, `Prepared` when only Prepare proves success, and `Completed`
when Run proves success. In `Prepared`, it SHALL disable Prepare and enable Run
by default. It SHALL NOT claim success from an unreadable or unsuccessful
summary. When the user explicitly enables the non-persistent downstream-summary
overwrite permission while the state is `Prepared`, the GUI SHALL re-enable
Prepare so invalidated preparation evidence can be regenerated without
weakening the RTDOSE adapter's validation gates.

#### Scenario: Successful preparation

- **WHEN** RTDOSE Prepare has a readable successful summary and RTDOSE Run does
  not
- **THEN** the GUI shows `Prepared`, disables Prepare by default, enables Run,
  and guides the user to Run rather than repeating Prepare

#### Scenario: Successful conversion

- **WHEN** RTDOSE Run has a readable successful summary
- **THEN** the GUI shows `Completed` and disables both RTDOSE actions

#### Scenario: Unreadable or unsuccessful evidence

- **WHEN** an RTDOSE summary is missing, unreadable, malformed, or does not
  report success
- **THEN** that summary does not establish a successful guided state or unlock
  its dependent action

#### Scenario: Explicit reprepare recovery

- **WHEN** RTDOSE is `Prepared` and the user enables downstream-summary
  overwrite permission because upstream evidence must be regenerated
- **THEN** the GUI immediately re-enables Prepare and leaves the RTDOSE adapter
  responsible for accepting or rejecting the new preparation

#### Scenario: Non-persistent recovery permission

- **WHEN** the GUI is restarted after overwrite permission was selected
- **THEN** overwrite permission returns to false and `Prepared` again defaults
  to Run as the next action

### Requirement: Guided Visual Hierarchy and Accessibility

The GUI SHALL group source inputs, local tool settings, derived handoff,
downstream stages, and execution evidence in workflow order. It SHALL provide
visible keyboard focus, readable text and controls, and status information that
does not rely on color alone. Advanced fields SHALL be visually subordinate to
the primary workflow.

#### Scenario: Initial guided screen

- **WHEN** the GUI opens
- **THEN** the CT2PHITS source inputs and first safe action are visually primary,
  advanced fields are not mixed into the primary form, and the supported public
  scope remains visible

#### Scenario: Stage result

- **WHEN** a stage completes or fails validation
- **THEN** the GUI identifies the stage, status text, relevant summary path or
  controlled error, and the next available action without relying only on color

### Requirement: Exclusive Responsive Stage Execution

The GUI SHALL keep the Tk event loop responsive while an external stage runs
and SHALL prevent another external stage from starting concurrently. It SHALL
continue to use each accepted adapter's existing timeout and failure evidence
rather than adding a bypassing process-cancellation path.

#### Scenario: Stage in progress

- **WHEN** one external stage is running
- **THEN** all other stage actions are disabled and the active stage is shown as
  in progress until a controlled result is available

### Requirement: Synthetic GUI Validation Boundary

Automated GUI tests SHALL use temporary synthetic files and fake or mock runners.
They MUST NOT run real RT-PHITS, PHITS, Sumtally, phits2dicom, GPR-comparing, or
real DICOM workflows.

#### Scenario: Automated integrated-flow test

- **WHEN** the CT2PHITS-to-workspace GUI handoff is tested automatically
- **THEN** fake stage evidence and temporary placeholder paths are used without
  executing an external licensed tool
