## ADDED Requirements

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
