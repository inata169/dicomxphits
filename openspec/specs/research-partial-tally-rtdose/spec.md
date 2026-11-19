# research-partial-tally-rtdose Specification

## Purpose

Define explicit research-only RT Dose export from a validated saved
partial PHITS tally after a recorded terminal stack overflow.

## Requirements

### Requirement: Identifiable Retained Partial Tally Snapshot

Research partial-tally export SHALL require a prepared public fixed-field
3D-CRT full-plan workspace with exactly one active treatment segment. That
segment MUST have authoritative retained-staging evidence from a PHITS 3.35
Windows OpenMP invocation whose terminal failure is Windows status
`0xC00000FD`. Recorded progress from that invocation MUST establish that the
last planned batch was reported and that the final geometry diagnostic
summary is absent. Unknown failures, timeout, user stop, known positive
geometry diagnostics, contradictory evidence, and ambiguous provenance MUST
be rejected. Missing diagnostics MUST remain recorded as unavailable.

The operator SHALL explicitly select the bound retained staging directory.
The system MUST revalidate the workspace manifest, preparation, execution
identity, preflight when present, staged inputs, and every consumed output
against the existing authoritative records. It MUST require safe
workspace-relative paths and the exact manifest-derived tally set. Each
required tally MUST pass bounded format and content checks. The primary dose
and error pair MUST match the prepared mesh, contain finite data for every
bin, and agree on the saved batch, histories per batch, variance mode, source
weight, and restart seed. Each other required tally MUST agree on the saved
batch, histories per batch, variance mode, and restart seed. The saved
batch count MUST be positive and exactly one below the prepared budget.
The saved restart seed MUST agree with the recorded start seed of the
reported last batch.
Progress, timestamps, or file presence alone MUST grant no export authority.

#### Scenario: The last batch was reported and the preceding batch was saved

- **GIVEN** a synthetic prepared case with one active segment and four planned batches
- **WHEN** its recorded stack overflow follows the report of batch four and the intact retained tally set records batch three
- **THEN** the preview reports three of four batches saved and final geometry diagnostics unavailable

#### Scenario: Retained evidence cannot establish one complete snapshot

- **WHEN** a tally is missing, truncated, mismatched, changed, linked, outside the workspace, or from another invocation, or the snapshot fails the supported batch or failure contract
- **THEN** export is unavailable and no source or destination artifact changes

### Requirement: Confirmed Export With Independent Authority

The GUI SHALL offer an explicit research-only export action on an eligible
failed workspace. Preview SHALL be read-only and SHALL present the failed
segment, exit code, saved and planned counts, unavailable diagnostics, and
research-only disposition. Export SHALL require explicit acknowledgement of
that preview. It MUST acquire exclusive workspace mutation ownership,
revalidate the evidence and destination state before writes, and require a
new preview if the confirmed state changed. It MUST revalidate the bound
inputs and intermediates before each tool launch and before final publication.

The system SHALL use private intermediates and a dedicated research output
location. It MUST preserve the source execution records, original tallies,
and any ordinary downstream artifacts. The original PHITS stage MUST remain
failed. The export MUST NOT authorize ordinary Sumtally, RTDOSE, selective
retry, or existing geometry-recovery actions. Export MUST run only the
existing tally aggregation and DICOM conversion operations. It MUST NOT
launch or resume segment particle transport.

#### Scenario: The operator confirms a current snapshot

- **WHEN** the operator acknowledges the exact preview and all evidence still validates
- **THEN** only the explicitly requested research export runs
- **AND** the original failed record and ordinary workflow authority remain unchanged

#### Scenario: The preview is abandoned or becomes stale

- **WHEN** the operator cancels, omits acknowledgement, or a bound input or destination changes before export
- **THEN** no external tool starts and no artifact is published

### Requirement: Preserved Dose Semantics and Verifiable Provenance

Research export SHALL enforce the existing full-plan delivery, coordinate,
calibration, MU, fraction-count, physical dose, and RT Dose validation
contracts on the accepted tally snapshot. It MUST use the saved tally's
normalization and MUST NOT scale the dose by the saved/planned batch ratio.
The final DICOM SHALL include a valid `DoseComment` containing
`RESEARCH ONLY`, `PARTIAL PHITS`, and the saved/planned batch counts. Adding
the comment MUST preserve the numerical and spatial attributes and the
validated frozen-plan reference.

The final output SHALL be published new-only with a versioned JSON receipt
in a separate research export location. The receipt MUST bind the confirmed
preview and source execution, exit code, saved and planned batch counts,
histories per batch, unavailable geometry diagnostics, consumed tally
digests, and final RT Dose SHA-256. Paths in the receipt MUST be
workspace-relative. The export MUST be presented as available only after
both the DICOM and receipt validate. Failure or interruption MUST leave the
source evidence intact and MUST NOT expose a partial bundle as an accepted
export. Re-open MUST validate the `DoseComment`, semantic binding, and digest
against the receipt before presenting an existing result.

#### Scenario: A labelled research dose is published

- **WHEN** a synthetic snapshot completes aggregation and conversion with fake runners
- **THEN** the reopened DICOM has the required comment and its physical dose, placement, and frozen-plan reference satisfy the existing contracts
- **AND** its SHA-256 matches the receipt, with no saved/planned-ratio correction

#### Scenario: A final result is missing or altered

- **WHEN** an export stops partway or its DICOM, required label, or receipt is later missing, mismatched, or altered
- **THEN** no complete research export is reported
