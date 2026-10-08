## ADDED Requirements

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
