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

### Requirement: Shared Public Project Identity

The GUI SHALL show the public repository address
`https://github.com/inata169/dicomxphits` and author `Hiroki Inata` as
read-only shared information. Displaying this information MUST NOT itself open
a browser, perform a network request, or run an update check.

#### Scenario: Offline GUI startup

- **WHEN** the GUI starts without network access
- **THEN** the repository address and author remain visible without attempting
  external communication

### Requirement: Minimum Shared Activity Log Visibility

The common Activity log text area SHALL keep at least two complete log lines
visible at the documented 1360 x 820 normal window and 1120 x 720 minimum
window while retaining its vertical scrolling and automatic scrolling to the
latest appended entry. The bounded sizing adjustment MUST apply to the common
log used by every workflow page and MUST NOT unnecessarily rearrange stage
controls, colors, fonts, or button placement.

#### Scenario: Normal Windows layout

- **WHEN** the GUI is displayed at 1360 x 820
- **THEN** at least two complete Activity log entries are simultaneously
  visible and the latest appended entry scrolls into view

#### Scenario: Minimum Windows layout

- **WHEN** the GUI is displayed at 1120 x 720
- **THEN** at least two complete Activity log entries remain visible without
  making the primary workflow controls inaccessible

#### Scenario: Log exceeds the visible area

- **WHEN** more Activity log entries exist than fit in the text area
- **THEN** the existing vertical scrolling remains available and appending an
  entry scrolls to the newest line
