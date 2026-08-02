# Guided GUI Workflow Delta

## ADDED Requirements

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

### Requirement: Safe Path Suggestions

The GUI SHALL keep every external input and workspace path visible and editable.
After explicit RT Plan selection it MAY suggest the selected file's parent as
the CT DICOM root and MAY derive new workspace names from a sanitized filesystem
filename stem and user-configured roots. It MUST NOT recursively discover DICOM
datasets, external installations, or private tools.

#### Scenario: Empty related fields

- **WHEN** a user selects an RT Plan and related case fields are empty
- **THEN** the GUI suggests only paths derived from that selection and already
  configured roots without scanning unrelated filesystem content

#### Scenario: Existing user value

- **WHEN** a related field already contains a user value
- **THEN** the GUI preserves that value instead of silently replacing it

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

### Requirement: Local GUI Settings and Independent Browse History

The GUI SHALL load and save backward-compatible local settings from the ignored
GUI settings path. It SHALL maintain a separate last Browse directory for each
path field. It MUST NOT persist non-patient confirmation or overwrite permission
and MUST fall back safely when the local settings file is missing, invalid, or
unreadable.

#### Scenario: Repeated stable configuration

- **WHEN** a user selects stable local tool paths and later reopens the GUI
- **THEN** the GUI restores those paths from the ignored local settings file

#### Scenario: Independent Browse fields

- **WHEN** a user browses in two different path fields
- **THEN** reopening either dialog starts from that field's own most recently
  accepted directory

#### Scenario: Safety state restart

- **WHEN** the GUI starts with saved local settings
- **THEN** non-patient confirmation and overwrite permission are both false

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
