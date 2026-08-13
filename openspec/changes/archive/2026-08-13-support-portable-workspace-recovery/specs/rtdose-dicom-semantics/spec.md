# RTDOSE DICOM Semantics Delta

## MODIFIED Requirements

### Requirement: Final RT Dose Semantic Validation

RTDOSE Run SHALL reopen the documented coordinate-corrected output and validate
its plan summation type and frozen-plan reference before reporting stage
success. A successful execution summary SHALL record the validated summation
type, referenced plan identity, current workspace-relative output identity, and
output SHA-256 without using the template's original values as evidence. When
an existing workspace is inspected after relocation, a copied successful
execution summary SHALL establish current success only when the bounded mapped
coordinate-corrected output exists, matches its recorded SHA-256, and passes
the recorded semantic binding. Missing, changed, external, or ambiguously
mapped output MUST NOT be presented as a completed RTDOSE result.

#### Scenario: Synchronized final output

- **WHEN** conversion, metadata synchronization, and coordinate correction all
  complete and the final output references the frozen plan exactly
- **THEN** RTDOSE Run reports success and records the current relative output,
  its SHA-256, and final semantic-validation evidence

#### Scenario: Verified output after workspace relocation

- **WHEN** a copied successful summary's final output exists at the equivalent
  bounded path below the current workspace and matches its recorded digest and
  semantic evidence
- **THEN** current-workspace inspection may accept the RTDOSE result as
  completed without rerunning conversion

#### Scenario: Relocated output is absent or changed

- **WHEN** a copied summary reports success but the bounded current output is
  absent, differs from its recorded digest, or cannot be safely mapped
- **THEN** current-workspace inspection does not accept Completed state and
  requires controlled downstream recovery

#### Scenario: Final output remains stale or malformed

- **WHEN** the final output lacks PLAN semantics, has zero or multiple plan
  references, or references another plan
- **THEN** RTDOSE Run reports failure and does not present the file as an
  accepted workflow result
