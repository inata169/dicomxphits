## MODIFIED Requirements

### Requirement: Complete Execution Binding for Retry

Retry SHALL require evidence captured before the original execution that binds
the current manifest, all workspace-local segment inputs, preparation/model/
calibration identity, effective runtime settings and relevant environment, and
the explicitly configured PHITS executable's resolved path and SHA-256. The
controller MUST NOT recursively enumerate or hash the configured PHITS
installation. Bound workspace file membership and SHA-256 values MUST match,
and the selected executable MUST pass its path/file checks and match its bound
SHA-256 immediately before every new child commitment. New retry evidence SHALL
identify the bounded executable scope. Historical installation-tree evidence
MUST NOT be rewritten or represented as newly verified bounded evidence.

Retained successes MUST additionally have every required output with its
recorded digest, zero return code and geometry-clean evidence. Every declared
primary output remains required, while only the manifest-selected primary 3D
dose output requires a separate statistical-error companion. An optional error
companion for another declared output is immutable evidence when present.
`batch.out` is mutable control/progress state and MUST NOT be a required output
or immutable digest gate. Any other missing or mismatched required evidence
SHALL reject the entire retry before execution and advise preparing a new
workspace.

#### Scenario: Input changes while output remains intact

- **WHEN** any bound workspace input, include, model, calibration, runtime
  setting, environment or selected executable identity changes
- **THEN** selective execution is rejected before launching any segment

#### Scenario: Installation sibling changes

- **WHEN** a file other than the selected executable changes in the configured
  installation while all bounded evidence remains valid
- **THEN** retry does not enumerate or hash that sibling and does not reject on
  an installation-wide mutation claim

#### Scenario: Mutable batch control changes

- **WHEN** a retained segment's `batch.out` content or remaining-batch value
  changes while every required immutable result still matches
- **THEN** that content change alone does not reject retry or authorize success

#### Scenario: Retry source has historical installation-tree evidence

- **WHEN** otherwise eligible v4 or v5 source evidence records the older
  installation-wide binding
- **THEN** the source remains unchanged, the current selected executable and
  workspace evidence are freshly validated without scanning the installation,
  and any new attempt records the bounded executable scope

#### Scenario: Previously successful segment is damaged

- **WHEN** a success lacks a required output, matching digest or clean geometry
  evidence
- **THEN** retry rejects the plan rather than silently recalculating that segment

#### Scenario: Older summary or moved workspace

- **WHEN** a source is v2/v3, lacks retry evidence, or differs from the recorded
  resolved root
- **THEN** selective execution is unavailable without rewriting or migrating the
  source record
