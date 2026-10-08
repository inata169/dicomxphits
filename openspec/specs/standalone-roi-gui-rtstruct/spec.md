# standalone-roi-gui-rtstruct Specification

## Purpose
Provide a standalone desktop interface for completed PHITS region statistics
and bind explicitly selected RT Structure contours to the native PHITS mesh
using validated frozen CT, RT Plan, and preparation evidence.

## Requirements

### Requirement: Explicit independent desktop selection

The system SHALL offer a separate desktop GUI for the independent completed
PHITS ROI analysis. It SHALL allow explicit selection of a directory or ZIP,
the official combined dose, its paired combined error, any required retained
dose, and the generation, execution, and manifest evidence. It MUST NOT
silently choose among multiple candidates, alter source cases, execute an
external calculation, or grant GUI/workflow completion authority.

#### Scenario: A completed case is selected

- **WHEN** the user explicitly selects one supported completed snapshot and
  its required pair and evidence
- **THEN** the GUI can show its analysis independently of the public GUI and
  without changing the case

#### Scenario: Candidate inputs are ambiguous

- **WHEN** multiple candidate ZIP members or run directories are present
- **THEN** the GUI requires explicit selection and offers no automatic result

### Requirement: Distinct sphere and RT Structure inputs

The GUI SHALL retain an editable sphere with default centre `(0, 0, 0)` cm
and radius `0.25 cm`, showing analytic volume, 1 mm sampling Points and
volume, and native Grid Points and volume separately. For an RT Structure,
it SHALL require explicitly selected RT Structure, RT Plan, and matching CT
series/reference inputs and one unique selected ROINumber. ROIName SHALL be
display-only. It MUST NOT identify an ROI by name alone or relabel a sphere
as an imported Structure.

#### Scenario: The default sphere is shown

- **WHEN** the user keeps the default sphere and 1 mm sampling
- **THEN** the GUI identifies 81 sampling Points and 0.081 cm3 sampling
  volume separately from the analytic sphere volume and native grid count

#### Scenario: Chamber is present by name

- **WHEN** a selected RT Structure contains an ROI named Chamber
- **THEN** the user must still select its unique ROINumber and supply the
  matching RT Plan and CT geometry before Structure analysis is available

### Requirement: Evidence-bound DICOM-to-PHITS membership

The adapter SHALL validate the selected RT Structure contour and frame,
RT Plan isocenter, CT-series geometry/evidence, and accepted PHITS mesh
binding before deriving membership.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** It SHALL map the selected Structure to a transient Boolean mask on the exact native `(x, y, z)` PHITS grid. It MUST fail closed on missing or conflicting identity, unsupported contour or orientation, out-of-grid or boundary ambiguity, and MUST NOT interpolate, resample, invent a contour, or change the accepted DICOM/PHITS coordinate and physical-tolerance contracts.

#### Scenario: One matching Structure is geometrically bound

- **WHEN** all selected identities and coordinate evidence agree and its
  contour maps unambiguously to native PHITS cell centres
- **THEN** only those native cells contribute to its independent statistics

#### Scenario: RT Structure alone is supplied

- **WHEN** the CT or RT Plan binding required to locate the contour is absent
- **THEN** Structure statistics remain unavailable with a specific reason
  rather than a guessed Chamber result or sphere substitution

### Requirement: Correct scalar meaning and safe reporting

The GUI SHALL display the validated one-fraction mean dose and spatial
variation separately from voxel r.err. It SHALL label the existing
`voxel_dose_sum_cgy` value as a grid-dependent sum of selected cell doses,
not a point dose, Structure mean, energy integral, or course dose. Optional
CSV/JSON publication SHALL be explicit, new-only, outside source cases and
the public repository, and SHALL omit automatic DICOM identifiers, absolute
source paths, and raw grids.

#### Scenario: One or two cells are selected

- **WHEN** the selected region contains one cell or two cells with doses
  `d1` and `d2`
- **THEN** the one-cell sum equals its mean, while the two-cell sum is
  `d1 + d2` and its mean is `(d1 + d2)/2`, with no claim that the sum is a
  physical region dose

#### Scenario: Structure geometry fails

- **WHEN** selected DICOM geometry cannot be validated
- **THEN** the GUI shows an unavailable Structure result and publishes no
  misleading numeric replacement

### Requirement: Synthetic validation and bounded real-data checks

Automated tests SHALL use only project-authored synthetic PHITS and DICOM
fixtures. They SHALL cover input selection, coordinate binding, one/many/no
cell populations, boundary and frame failures, GUI state, and new-only
reports. Any local real-data check SHALL use explicitly selected read-only
inputs outside the repository, and its results MUST NOT be committed. The
result MUST NOT claim clinical validation or extend the public GUI's
post-completion Structure r.err authority.

#### Scenario: Compatibility is checked locally

- **WHEN** a synthetic fixture or an explicitly selected local case passes
- **THEN** the report states the validated input and statistical scope
  without claiming clinical or general DICOM/PHITS compatibility

### Requirement: Guided case-member suggestions and manual override

The standalone GUI SHALL allow the user to browse and edit each case-internal
source member and separately browse required external DICOM inputs.

#### Scenario: Apply the complete validation contract

- **WHEN** this capability is used
- **THEN** For a selected dicomxphits case, it MAY fill a field only when one canonical path-suffix match is unambiguous, and SHALL identify the value as a suggestion that the user can replace. If multiple viable candidates remain, the field SHALL stay empty until the user selects one. Suggestions MUST NOT grant analysis or workflow authority; the original source, pair, evidence, and DICOM validators SHALL still run before a result is shown.

#### Scenario: One canonical pair exists

- **WHEN** a selected case has exactly one canonical combined dose and its
  paired combined error in a standard location
- **THEN** the GUI may show both as editable suggested inputs, while analysis
  remains gated by full validation

#### Scenario: Error exists only in one saved run

- **WHEN** the official combined dose has no co-located error but exactly one
  saved run has a co-located dose and error candidate
- **THEN** the GUI suggests the saved error and retained dose together, and
  the reader verifies their bytes and provenance before computing statistics

#### Scenario: Candidate layouts conflict

- **WHEN** more than one viable combined pair, saved run, or evidence member
  fits a field
- **THEN** the affected field remains empty and the user can choose a member
  manually, without an automatic result

#### Scenario: External DICOM is required

- **WHEN** the user requests RT Structure analysis
- **THEN** the GUI keeps the RT Structure DICOM, RT Plan, CT reference, and
  ROI number separately explicit; a suggested preparation JSON never stands
  in for the RT Structure file

### Requirement: English and Japanese display menu

The standalone ROI GUI SHALL provide a visible English/Japanese language menu,
initially use Japanese, and switch application-owned labels, buttons, headings,
guidance, and contextual messages in place. Switching MUST preserve inputs,
ROI selection, queued cases, results, and analysis state. Export schemas,
numeric values, units, source diagnostics, and user or DICOM names SHALL retain
their existing values.

#### Scenario: Switch with a populated session

- **WHEN** the user switches between English and Japanese after selecting
  files and an ROI or computing results
- **THEN** the displayed interface changes language without clearing values,
  changing selection, recalculating results, or writing reports

#### Scenario: Switch during analysis

- **WHEN** the user changes language while analysis is running
- **THEN** action guards remain unchanged and the completion message uses
  the language selected at completion

#### Scenario: Open a file dialog or inspect a diagnostic

- **WHEN** the user opens a native picker or receives a source diagnostic
- **THEN** application context follows the selected language while native
  OS controls and original diagnostic text may retain their original language

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
