## ADDED Requirements

### Requirement: Explicit post-completion Structure evaluation

The system SHALL offer Structure relative-error evaluation only in a distinct
`Post-completion Structure r.err` section on the Sumtally page after the
current workspace has verified terminal success for the all-active-segments
Sumtally operation. Each evaluation SHALL require an explicit user action and
explicit selection of one validated RT Structure Set and exactly one unique
`ROINumber`. It MUST NOT run automatically, evaluate multiple ROIs in one
request, or select an ROI by `ROIName`. The GUI MAY show `ROIName` only as an
in-memory display label.

The evaluator MUST NOT replace or augment live Isocenter-voxel observation and
MUST NOT affect PHITS progress, convergence, stopping, completion, Sumtally or
RTDOSE eligibility, or any other downstream authority.

#### Scenario: User requests one eligible Structure evaluation

- **WHEN** verified all-active-segments Sumtally success exists for the current
  workspace and the user explicitly selects one validated RT Structure Set and
  one unique `ROINumber` and requests evaluation
- **THEN** the system evaluates only that ROI in the distinct post-completion
  Sumtally-page section

#### Scenario: Evaluation is not explicitly requested

- **WHEN** Sumtally completes but the user has not explicitly requested one
  Structure evaluation
- **THEN** no Structure relative-error evaluation starts and live observation
  remains unchanged

#### Scenario: ROI identity is invalid

- **WHEN** the selected `ROINumber` is missing or duplicated, its matching ROI
  Contour item is missing or duplicated, or the selected ROI is empty
- **THEN** evaluation is unavailable without name matching, multi-ROI merging,
  or another-ROI fallback

### Requirement: Authoritative combined dose and error evidence

The evaluator SHALL use only the validated all-active-segments Sumtally
combined 3D dose and its paired combined statistical-relative-error grid. It
SHALL bind both grids to terminal Sumtally success, the current workspace,
canonical manifest, mesh geometry, supported combined-`r.err` semantics, and
immutable file and evidence digests. Combined-error parsing and its pairing
with combined dose SHALL be implemented and verified before the evaluator is
available.

The evaluator MUST NOT use live or per-segment values, `deposit-pdd.out`, a
historical workspace result, or an unverified output as a fallback.

#### Scenario: Valid combined evidence is available

- **WHEN** current terminal Sumtally evidence proves the combined dose and
  error files, their matching mesh, immutable digests, and supported combined
  statistical-error semantics
- **THEN** those paired grids are the sole numerical source for evaluation

#### Scenario: Combined error meaning or binding is unproved

- **WHEN** combined `r.err` semantics, dose/error pairing, terminal evidence,
  manifest binding, geometry, or an immutable digest is absent or invalid
- **THEN** evaluation is unavailable without falling back to PDD, live,
  per-segment, historical, or unverified data

### Requirement: Fail-closed Structure and grid mapping

The evaluator SHALL map Sumtally dose-voxel centres into DICOM patient
coordinates using the existing accepted RTDOSE affine. It SHALL accept only
`CLOSED_PLANAR` contours bound to the same validated Frame of Reference and
frozen CT series, construct Structure membership on that frozen CT
voxel-centre mask, and include a dose voxel only when its centre lies in one
unique CT voxel cell whose mask value belongs to the selected ROI.

The evaluator MUST NOT interpolate contours or grids, apply partial-volume
weights, introduce a new coordinate tolerance, or infer membership when a
dose-voxel centre lies on a CT-cell boundary or lacks a unique mapping.

#### Scenario: Dose-voxel centre maps uniquely

- **WHEN** an eligible Sumtally dose-voxel centre maps through the accepted
  RTDOSE affine into one unique frozen-CT voxel cell within the selected
  `CLOSED_PLANAR` ROI mask
- **THEN** the evaluator treats that dose voxel as mapped to the Structure

#### Scenario: Contour or coordinate evidence is incompatible

- **WHEN** contour type, Frame of Reference, frozen CT series, accepted RTDOSE
  affine, or required mapping evidence is absent or incompatible
- **THEN** the entire evaluation is unavailable without coordinate inference
  or a new tolerance

#### Scenario: Membership is ambiguous or absent

- **WHEN** a required dose-voxel centre is on a CT-cell boundary, maps to more
  than one CT cell, or no dose voxel maps to the selected Structure
- **THEN** the entire evaluation is unavailable without interpolation or
  partial-volume inclusion

### Requirement: Complete numeric validation and fixed low-dose population

Before filtering, the combined dose and error grids SHALL have complete
matching supported metadata, shape, and cell count, and every required value
SHALL parse as a finite non-negative number. Any malformed, non-finite, or
negative required value or any grid mismatch SHALL make the entire evaluation
unavailable rather than be silently discarded.

The evaluator SHALL derive one finite positive `Dmax` from the entire validated
combined 3D dose grid and use it only as a non-displayed threshold reference.
Within the mapped Structure it SHALL form the above-threshold population only
from voxels satisfying `D > 0.5 * Dmax`. Version 1 MUST NOT expose this fixed
threshold as a user control. From that population, only voxels with `D > 0`
and `r.err > 0` SHALL be statistically eligible. Zero `r.err` SHALL be excluded
and counted, not reported as zero-percent uncertainty. Fewer than two eligible
voxels SHALL make evaluation unavailable.

#### Scenario: Eligible population is formed

- **WHEN** both complete grids are valid, global `Dmax` is finite and positive,
  and at least two mapped Structure voxels satisfy `D > 0.5 * Dmax` and
  `r.err > 0`
- **THEN** the evaluator uses exactly those eligible voxels for the approved
  statistics and counts any above-threshold zero-`r.err` voxels as excluded

#### Scenario: A required grid value is invalid

- **WHEN** any required dose or error value is malformed, non-finite, or
  negative, or supported metadata, shape, or cell count does not match
- **THEN** the entire evaluation is unavailable without silently dropping the
  invalid cell

#### Scenario: Threshold reference or population is insufficient

- **WHEN** global `Dmax` is absent or not finite and positive, no mapped
  Structure voxel satisfies `D > 0.5 * Dmax`, or fewer than two voxels remain
  after positive-`r.err` filtering
- **THEN** evaluation is unavailable and is not reduced to a single-voxel
  statistic

### Requirement: Bounded unweighted relative-error statistics

For the eligible unweighted voxel population, the evaluator SHALL convert each
`r.err` to percent and report only its arithmetic mean, median, and P95. For an
even population, median SHALL be the arithmetic mean of the two central sorted
values. P95 SHALL use linear interpolation at zero-based sorted position
`0.95 * (n - 1)`.

The result SHALL also report the mapped Structure voxel count, count satisfying
`D > 0.5 * Dmax`, final eligible count, and zero-`r.err` exclusion count. It
MUST NOT display global `Dmax` or any relative-error minimum, maximum, standard
deviation, whole-3D-mesh aggregate, or PDD-derived value.

#### Scenario: Statistics are reported

- **WHEN** a valid evaluation has an eligible sorted percent population
- **THEN** the result reports the unweighted arithmetic mean, defined median,
  linearly interpolated P95, and four approved population counts

#### Scenario: Disallowed summaries are requested

- **WHEN** a result is presented
- **THEN** it contains no displayed `Dmax`, relative-error minimum, maximum,
  standard deviation, whole-mesh aggregate, or PDD-derived substitute

### Requirement: Non-clinical presentation and deterministic persistence

Every displayed result SHALL include the exact statement `Monte Carlo
statistical relative error within the selected Structure; not clinical dose
error, convergence, patient QA, or an acceptance criterion.` The fixed
low-dose threshold and unweighted voxel basis SHALL also be visible with the
statistics.

The system SHALL derive a canonical `evaluation_sha256` from the evaluation
contract version and threshold plus the current canonical manifest, validated
Sumtally combined dose/error outputs and semantics, selected RT Structure Set
digest and `ROINumber`, and frozen CT, Frame of Reference, and accepted
RTDOSE-affine evidence. It SHALL atomically publish a new, versioned scalar
summary only at
`analysis/structure_relative_error/<evaluation_sha256>.json` below the current
workspace and MUST NOT replace an existing path.

The record SHALL contain the evaluation identity and evidence digests, approved
statistics and counts, and enough versioned metadata to validate their exact
meaning. It MUST NOT contain raw dose or error arrays, RT Structure content,
patient identifiers, or `ROIName`. Version 1 MUST NOT export the result to CSV,
DICOM, or another format.

#### Scenario: A new result is published

- **WHEN** evaluation completes and the deterministic target does not exist
- **THEN** the system atomically publishes one versioned scalar-summary JSON at
  the exact workspace-relative evaluation path without raw or identifying data

#### Scenario: Export is considered

- **WHEN** a Structure relative-error result is available in version 1
- **THEN** the GUI offers no CSV, DICOM, or other export action

### Requirement: Exact stale-result invalidation

Before displaying a persisted result, the system SHALL recompute the canonical
evaluation identity from current validated evidence and consider only the exact
safe regular JSON record at its deterministic path. It MUST NOT scan the result
directory for alternative or historical records. The record schema, canonical
identity, evidence digests, scalar values, counts, and statistical definitions
SHALL validate before display.

Any changed, missing, malformed, unsafe, stale, or mismatched input, output,
mapping, contract, or record evidence SHALL make the result unavailable. The
system MUST NOT overwrite an existing record, display a prior identity as
current, substitute another result, or grant downstream authority.

#### Scenario: Current persisted result is redisplayed

- **WHEN** the exact deterministic record is a safe regular file and all of its
  versioned contents and current evidence bindings validate
- **THEN** the GUI may redisplay its approved statistics and labels

#### Scenario: Evidence changes after evaluation

- **WHEN** any identity-bound input, output, mapping evidence, threshold, or
  contract version changes
- **THEN** the recomputed identity differs and the previous result is not shown
  as current

#### Scenario: Exact record is invalid or absent

- **WHEN** the exact deterministic record is absent, unsafe, malformed, or
  inconsistent with current evidence
- **THEN** evaluation is unavailable without a directory scan, historical
  fallback, overwrite, or downstream effect
