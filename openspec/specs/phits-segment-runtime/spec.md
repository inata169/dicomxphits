# PHITS Segment Runtime Specification

## Purpose

Define the explicit, auditable calculation-size and OpenMP controls applied to
newly prepared fixed-field PHITS segment inputs and direct segment execution.
## Requirements
### Requirement: Explicit Prepared Segment Runtime Parameters

Workspace preparation SHALL accept decimal positive integers for segment
`maxcas`, `maxbch`, and OpenMP thread count, defaulting to `1000000`, `10`, and
`8`. It SHALL validate them before creating or modifying workspace artifacts,
render the exact effective values into every active segment PHITS input, and
record them in preparation evidence. These parameters MUST NOT change the
fixed-field geometry, machine model, dose calibration, MU semantics, or
Sumtally inputs.

#### Scenario: Default CLI preparation

- **WHEN** workspace preparation is invoked without explicit runtime options
- **THEN** every active segment input contains `maxcas = 1000000`,
  `maxbch = 10`, and `$OMP = 8`, and the summary records those values

#### Scenario: Explicit CLI preparation

- **WHEN** workspace preparation receives valid explicit runtime options
- **THEN** every active segment input and the preparation summary contain the
  exact selected values

#### Scenario: Invalid CLI runtime value

- **WHEN** any runtime option is zero, negative, fractional, boolean, empty, or
  non-decimal text
- **THEN** preparation fails before creating or modifying workspace artifacts

### Requirement: Documented OpenMP Directive and Direct Execution

Generated segment inputs SHALL place `$OMP = N` before the first PHITS section,
where `N` is the validated positive OpenMP thread count. The direct segment
execution adapter SHALL pass the same value as `OMP_NUM_THREADS=N` to the PHITS
child process. It MUST reject a missing or malformed generated directive rather
than silently executing with an unrecorded thread setting.

#### Scenario: Prepared OpenMP segment execution

- **WHEN** the adapter executes a generated segment containing `$OMP = 12`
- **THEN** it directly launches the selected PHITS executable with
  `OMP_NUM_THREADS=12`

#### Scenario: Unsupported directive spelling

- **WHEN** a prepared segment contains `OMP = 12` without the documented
  dollar sign
- **THEN** the adapter rejects the input instead of treating it as the supported
  OpenMP directive

#### Scenario: Invalid generated thread count

- **WHEN** a generated `$OMP` directive has a missing, zero, negative, or
  non-integer value
- **THEN** the adapter rejects the input before launching PHITS

### Requirement: Segment Success Shall Require Geometry-Clean PHITS Evidence

The direct PHITS segment adapter SHALL accept a segment as successful only when
the process returns zero, all currently required outputs exist, and the staged
PHITS companion output contains one recognized and unambiguous geometry
diagnostic summary with zero `Number of lost particles`, `Number of geometry
recovering`, and `Number of unrecovered errors` counts. A missing, malformed,
duplicate, contradictory, or nonzero required
diagnostic summary SHALL fail the segment before its tally is published for
downstream use.

The execution evidence SHALL record the parsed diagnostic status and counts.
The parser SHALL use bounded numeric fields from reviewed summary records and
MUST NOT treat an unrelated textual occurrence of a geometry term as a count.

#### Scenario: PHITS returns zero with clean geometry

- **WHEN** a fake PHITS run returns zero, creates every required output, and
  supplies one recognized summary whose geometry counts are all zero
- **THEN** the adapter may publish the segment as successful and records the
  clean diagnostic evidence

#### Scenario: PHITS reports a geometry error

- **WHEN** a fake PHITS run returns zero and creates a tally but the recognized
  summary reports a nonzero lost-particle, geometry-recovering, or unrecovered
  error count
- **THEN** the adapter fails the segment and does not publish that tally for
  Sumtally

#### Scenario: Geometry summary is not provable

- **WHEN** the required geometry summary is missing, malformed, duplicated, or
  contradictory
- **THEN** the adapter fails closed even when the process return code is zero
  and an expected tally exists
