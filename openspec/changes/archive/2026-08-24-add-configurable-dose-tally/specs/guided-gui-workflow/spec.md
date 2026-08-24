# Guided GUI Workflow Delta

## ADDED Requirements

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
