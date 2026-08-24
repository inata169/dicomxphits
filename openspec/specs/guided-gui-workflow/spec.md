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
Prepare and Run summaries whose required current-workspace artifacts and
portable bindings also validate. It SHALL present `Not run` when neither
summary proves success, `Prepared` when only Prepare proves current success,
`Completed` when Run proves current success, and a distinct recovery-needed
state when copied historical success cannot prove the current artifact. In
`Prepared`, it SHALL disable Prepare and enable Run by default. It SHALL NOT
claim success from an unreadable or unsuccessful summary, a missing current
output, an unsafe path binding, or failed current evidence. When the user
explicitly enables the non-persistent downstream-summary overwrite permission
while preparation must be regenerated, the GUI SHALL enable the safe recovery
action while leaving the RTDOSE adapter's validation gates authoritative.

#### Scenario: Successful preparation

- **WHEN** RTDOSE Prepare has a readable successful summary and all required
  preparation artifacts validate in the current workspace, while RTDOSE Run
  does not prove current success
- **THEN** the GUI shows `Prepared`, disables Prepare by default, enables Run,
  and guides the user to Run rather than repeating Prepare

#### Scenario: Successful conversion

- **WHEN** RTDOSE Run has a readable successful summary and its documented
  coordinate-corrected output exists at the accepted current path and passes
  the recorded binding and semantic evidence
- **THEN** the GUI shows `Completed` and disables both RTDOSE actions

#### Scenario: Historical success with missing current output

- **WHEN** a copied RTDOSE Run summary reports success but the accepted current
  coordinate-corrected output is missing or cannot be safely rebound
- **THEN** the GUI does not show `Completed`, displays that recovery is needed,
  and keeps unsafe dependent actions disabled

#### Scenario: Unreadable or unsuccessful evidence

- **WHEN** an RTDOSE summary is missing, unreadable, malformed, does not report
  success, or fails current-workspace evidence validation
- **THEN** that summary does not establish a successful guided state or unlock
  its dependent action

#### Scenario: Explicit reprepare recovery

- **WHEN** RTDOSE preparation is historical or invalidated by regenerated
  upstream evidence and the user enables downstream replacement permission
- **THEN** the GUI enables the applicable preparation recovery and leaves the
  RTDOSE adapter responsible for accepting or rejecting the new evidence

#### Scenario: Non-persistent recovery permission

- **WHEN** the GUI is restarted after replacement permission was selected
- **THEN** replacement permission returns to false and recovery actions again
  require explicit permission

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

### Requirement: Guided Existing-Workspace Recovery

The GUI SHALL provide an explicit existing-workspace selection path that is
distinct from Browse controls that construct a proposed new workspace. It
SHALL inspect portable evidence without external execution, display the highest
current verified stage and the first stage requiring recovery, and provide one
safe next action. It MUST NOT require the user to infer relocation recovery by
repeatedly invoking stages and interpreting existing-output errors.

#### Scenario: Existing relocated workspace selected

- **WHEN** a user explicitly selects a workspace whose recorded root differs
  from its current root
- **THEN** the GUI performs bounded read-only inspection and displays current,
  historical-recoverable, or invalid evidence without running an external tool

#### Scenario: Existing same-computer workspace selected after restart

- **WHEN** the GUI is restarted and the user explicitly selects an existing
  3D-CRT workspace
- **THEN** the GUI reconstructs the current verified stage from workspace
  evidence without requiring CT2PHITS, Workspace Prepare, or PHITS to be
  invoked as probes

#### Scenario: Standard frozen handoff is available

- **WHEN** the selected workspace name ends in `-3dcrt` and the corresponding
  `-ct2phits` directory below the validated standard RT-PHITS work root has a
  completed summary and all three documented handoff artifacts
- **THEN** the GUI restores the frozen RT Plan, CT reference, and DATfiles from
  that one validated bounded candidate without scanning other directories

#### Scenario: Standard frozen handoff is unavailable

- **WHEN** the deterministic CT2PHITS handoff candidate is absent or invalid
- **THEN** the GUI requests one existing CT2PHITS workspace selection and does
  not require three independent path selections or guess a replacement

#### Scenario: Verified PHITS with historical downstream summaries

- **WHEN** PHITS segment evidence is current and verified but copied Sumtally
  or RTDOSE evidence requires regeneration
- **THEN** the GUI identifies Sumtally Generate as the first recovery action
  and does not instruct the user to rerun CT2PHITS, Workspace Prepare, or PHITS

#### Scenario: Recovery requires replacement permission

- **WHEN** historical downstream summaries or outputs conflict with fresh
  recovery evidence
- **THEN** the GUI explains that the conflicting Sumtally and RTDOSE material
  will move into a new workspace-local recovery history, confirms that PHITS
  segment outputs remain unchanged, and requires explicit non-persistent
  permission before enabling the recovery action

#### Scenario: Missing Sumtally generation summary after verified PHITS

- **WHEN** the generation summary is missing but another accepted downstream
  summary records matching manifest and active-segment output digests
- **THEN** the GUI reports that PHITS results remain reusable and offers
  Sumtally Generate as the first recovery action instead of exposing a raw file
  error

#### Scenario: One primary RT Dose action

- **WHEN** verified PHITS evidence permits downstream recovery and the user
  confirms workspace-local preservation of conflicting downstream artifacts
- **THEN** one Create DICOM RT Dose action runs only the required suffix of
  Sumtally Generate, Sumtally Run, RTDOSE Prepare, and RTDOSE Run, stopping on
  the first failed accepted adapter

#### Scenario: Existing case protects expensive upstream stages

- **WHEN** a verified existing workspace is open for downstream recovery
- **THEN** new-case Workspace Prepare and PHITS execution actions are disabled
  and the GUI states that the existing PHITS outputs will remain unchanged

#### Scenario: Recovery completes

- **WHEN** the accepted RTDOSE Run summary and its current corrected artifact
  validate
- **THEN** the GUI displays the `.fixed.dcm` path as the standard DICOM patient-
  coordinate output and provides a direct way to open its folder

#### Scenario: Recovery cannot continue

- **WHEN** a required summary or artifact is missing or invalid
- **THEN** the GUI explains the user-visible problem, whether verified PHITS
  results remain reusable, and the next safe action without using a raw
  exception or internal JSON pathname as the only dialog text

#### Scenario: Relocation evidence is invalid

- **WHEN** a required artifact is missing, changed, external, or ambiguously
  mapped
- **THEN** the GUI keeps dependent actions disabled and identifies the failed
  evidence and required safe resolution without relying only on red text

### Requirement: Shared Fixed 6 MV Model Presentation

The GUI SHALL show `Beam model: Elekta Precise 6 MV public research model` and
`Nominal energy: 6 MV (fixed)` in a shared read-only area visible from the
CT2PHITS, Workspace, PHITS, Sumtally, and RTDOSE pages. It MUST NOT add an
energy selector or present 10 MV or another energy as supported.

#### Scenario: User changes workflow page

- **WHEN** the user navigates among any of the five workflow pages
- **THEN** the same fixed 6 MV public research-model identity remains visible

#### Scenario: User reviews available controls

- **WHEN** the GUI is constructed
- **THEN** no editable nominal-energy or beam-model selector exists

### Requirement: Explicit Help Project Identity and Version

The GUI SHALL provide a `Help` menu containing `Web site` and `About` actions.
Only an explicit user selection of `Web site` MAY request the operating
system's default browser for
`https://github.com/inata169/dicomxphits`. `About` SHALL display the current
package version and author `Hiroki Inata (inata169)` using package-owned
identity. GUI startup, page navigation, and opening About MUST NOT open a
browser, perform a network request, or run an update check.

#### Scenario: User explicitly selects Web site

- **WHEN** the user selects `Help` then `Web site`
- **THEN** the GUI requests the default browser for exactly the public
  repository HTTPS URL and does not change workflow or stage state

#### Scenario: Browser request fails

- **WHEN** the operating system cannot accept the explicit repository browser
  request
- **THEN** the GUI reports a controlled local error and leaves workflow and
  stage state unchanged

#### Scenario: User opens About

- **WHEN** the user selects `Help` then `About`
- **THEN** a local dialog displays the current package version and
  `Hiroki Inata (inata169)` without external communication

#### Scenario: Offline GUI startup

- **WHEN** the GUI starts without network access
- **THEN** the Help menu and local About information remain available without
  starting a browser, update check, or network request

### Requirement: Minimum Shared Activity Log Visibility

The common Activity log text area SHALL keep at least two complete log lines
visible at the documented `1360 x 820` normal window and `1120 x 720` minimum
window while retaining its vertical scrolling and automatic scrolling to the
latest appended entry. The bounded sizing adjustment MUST apply to the common
log used by every workflow page.

#### Scenario: Normal Windows layout

- **WHEN** the GUI is displayed at `1360 x 820`
- **THEN** at least two complete Activity log entries are simultaneously
  visible and the latest appended entry scrolls into view

#### Scenario: Minimum Windows layout

- **WHEN** the GUI is displayed at `1120 x 720`
- **THEN** at least two complete Activity log entries remain visible

#### Scenario: Log exceeds the visible area

- **WHEN** more Activity log entries exist than fit in the text area
- **THEN** the existing vertical scrolling remains available and appending an
  entry scrolls to the newest line

### Requirement: Minimum-Window Workflow Action Reachability

The GUI SHALL place only the current workflow page-content region in a common
vertically scrollable viewport and SHALL keep the shared Activity log outside
that viewport. At the documented `1120 x 720` minimum window, the user MUST be
able to reach the primary action area on CT2PHITS, Workspace, PHITS, Sumtally,
and RTDOSE by scrolling or normal keyboard traversal. Selecting a different
workflow page SHALL return its shared viewport to the top.

Making an action reachable MUST NOT bypass or change its current busy-state,
tool-readiness, overwrite, RTDOSE evidence, existing-case, recovery, or
upstream-protection gate. A reachable action that is not currently authorized
MUST remain disabled.

#### Scenario: User visits all five pages at minimum size

- **WHEN** the GUI is displayed at `1120 x 720` and the user visits each
  workflow page
- **THEN** vertical scrolling or keyboard traversal reaches that page's
  primary action area without moving the shared Activity log out of its common
  region

#### Scenario: User changes page after scrolling

- **WHEN** the user scrolls one page and then selects another workflow page
- **THEN** the newly selected page begins at the top and its lower controls
  remain reachable through the same viewport

#### Scenario: Reachable action remains gated

- **WHEN** a primary action is visible or keyboard-reachable but its current
  safety or provenance prerequisites are not satisfied
- **THEN** the action remains disabled under the existing stage-gating logic

#### Scenario: Existing-case recovery protects upstream work

- **WHEN** an existing verified case is open and its downstream recovery action
  is reachable
- **THEN** the applicable upstream CT2PHITS, Workspace Prepare, and PHITS
  actions remain disabled and the recovery action runs only the already
  accepted downstream suffix when all current gates pass

### Requirement: Minimal Calculation Configuration Handoff

The GUI Workspace page SHALL provide one optional Calculation config file path
and Browse action adjacent to workspace-preparation settings. An empty path
SHALL omit the calculation-config CLI option and preserve the legacy 3D dose
tally default. A non-empty path SHALL be validated as an existing regular file
and passed as one argument to the accepted workspace-preparation command; the
canonical loader SHALL perform semantic validation before workspace mutation.

The GUI MUST NOT expose PHITS bin edges, arbitrary tally text, a device preset,
or per-segment mesh controls. The first version SHALL NOT persist the selected
calculation-config path in local GUI settings and SHALL NOT pass it to PHITS,
Sumtally, or RTDOSE stage commands after workspace preparation.

#### Scenario: Calculation configuration is omitted in the GUI

- **WHEN** the Workspace page Calculation config field is blank
- **THEN** workspace preparation omits the calculation-config option and uses
  the existing legacy 3D tally geometry

#### Scenario: Valid calculation configuration is selected

- **WHEN** the user selects an existing regular calculation-config file and
  starts preparation
- **THEN** the GUI passes its resolved path as one workspace-preparation CLI
  argument and leaves canonical content validation to the preparation boundary

#### Scenario: Calculation configuration path is not a file

- **WHEN** the non-empty field names a missing path or directory
- **THEN** the GUI reports the field error and starts no preparation subprocess

#### Scenario: Downstream stage command is built

- **WHEN** PHITS, Sumtally, or RTDOSE actions are constructed for a prepared
  workspace
- **THEN** the calculation-config path is not forwarded because downstream
  stages consume bound workspace evidence and actual tally outputs
