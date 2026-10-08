## ADDED Requirements

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
