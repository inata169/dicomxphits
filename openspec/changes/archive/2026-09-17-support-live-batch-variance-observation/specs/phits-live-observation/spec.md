## ADDED Requirements

### Requirement: Explicit Live Batch-Variance Pair Support

Live observation SHALL accept the public generator's single explicit
`istdev = -1` input directive without changing the input or treating that
directive as sufficient output compatibility evidence. Duplicate, malformed,
or other explicit variance directives SHALL remain unsupported.

For positively identified PHITS 3.35 Windows OpenMP fresh primary 3D dose/error
pairs, live Isocenter-voxel observation SHALL support both history-variance
metadata (`istdev = 2`) and reviewed batch-variance metadata (`istdev = 1`).
Both files MUST agree on variance mode, mesh, role pairing, source-weight and
count metadata, prepared maxcas, and restart/seed identity. Batch-variance counts
MUST be positive integral values no greater than prepared maxbch. Unknown,
mixed, partial, non-finite, or contradictory records MUST yield unavailable.

The observer SHALL display only the reported finite positive Isocenter-voxel
relative error multiplied by 100, with the existing positive-dose and unique
bin-interior requirements. It MUST NOT recompute variance, convert batches to
histories, derive convergence/ETA, or change any calculation setting. The
extended parser identity MUST NOT falsely identify batch-variance acceptance
as the legacy history-only format.

Existing ownership, provenance, read bounds, successive-sample confirmation,
staleness, reset, and non-authoritative behavior SHALL remain unchanged. This
extension SHALL NOT widen accepted modes in Sumtally, Structure evaluation, or
other shared-parser callers outside live observation.

#### Scenario: Generated default input

- **WHEN** a public-generated input contains a single `istdev = -1`
- **THEN** observation setup accepts it while output identity and pair validation remain mandatory

#### Scenario: Complete batch-variance pair

- **WHEN** a fresh matching batch-variance pair satisfies the prepared runtime budget and all existing live observation checks
- **THEN** the GUI may show its provisional single Isocenter-voxel relative-error percentage without changing the simulation

#### Scenario: Mixed or invalid variance metadata

- **WHEN** the pair has differing variance modes, invalid batch counts, a conflicting seed, or an unsupported variance code
- **THEN** no new voxel error value is published and execution/completion authority is unchanged

#### Scenario: Existing history-variance observation

- **WHEN** a matching history-variance pair satisfies the existing supported format
- **THEN** its live observation remains available under the same existing guards

#### Scenario: Shared post-completion consumers

- **WHEN** a shared parser is used outside live observation
- **THEN** this extension does not grant that caller new batch-variance acceptance
