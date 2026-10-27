## ADDED Requirements

### Requirement: Research-Only Recorded Geometry Recovery Eligibility

Research acceptance SHALL require one failed active segment, zero lost and unrecovered counts, and a positive integer recovering total under the contract below. There SHALL be no acceptance cap on that total, region-pair count, or history ratio. The total and complete pair distribution MUST be recorded and agree. Every other active segment MUST satisfy ordinary success validation; ambiguous evidence MUST fail closed.

#### Scenario: Full eligibility is assessed

- **WHEN** research acceptance is assessed for a selected synthetic workspace
- **THEN** the following complete contract SHALL hold:

The system SHALL consider research acceptance only when all of the following
hold for the selected workspace:

- the segment execution summary has a supported schema and exactly one failed
  active segment, and every other active segment satisfies ordinary success
  validation;
- the failed segment has return code zero, and its only recorded failure reason
  is geometry diagnostics (no timeout, stop, missing output, digest mismatch,
  or other reason);
- the failed segment's `phits.out` re-parses, with bounded geometry-summary
  parsing, to a positive integer `geometry_recovering` total,
  `lost_particles == 0`, and `unrecovered_errors == 0`, with no parse errors.
  These totals MUST equal the counts recorded in the summary. Every reported
  region pair and its positive integer count MUST be recorded in the receipt,
  and the complete unambiguous pair distribution MUST sum to the recovering
  total; multiple region pairs are permitted;
- `phits.out` records completion of the final batch equal to the prepared
  `maxbch`; and
- the manifest and execution binding validate under the current geometry
  contract.

There MUST NOT be a numerical acceptance upper bound on the recovering total,
number of region pairs, or recovering-to-history ratio, nor a configurable
threshold. Existing bounded parsing and resource safeguards MUST remain in
force. Eligibility MUST NOT automatically create a receipt or authorize
downstream use without the explicit acknowledgement and reason. An `nlost`
parameter MUST NOT replace the zero-loss, completion, or integrity checks.

#### Scenario: Recovering counts above one and multiple region pairs

- **WHEN** a synthetic workspace has one failed segment with return code zero,
  a completed final batch, recovering total 12 split into two region pairs
  with counts 5 and 7, zero lost and unrecovered counts, and all evidence
  matches the recorded invocation
- **THEN** the system reports it as eligible for explicit research acceptance
  and records total 12 and both pairs in the preview without publishing

#### Scenario: Larger valid recovering count

- **WHEN** a larger positive recovering total and its complete pair
  distribution validate within the supported numeric format and all other
  eligibility conditions hold
- **THEN** neither the count, number of pairs, nor history ratio alone rejects
  eligibility, and an operator decision is still required

#### Scenario: Nonzero lost or unrecovered count

- **WHEN** either the lost or unrecovered count is nonzero, even if a lost
  count is below an `nlost` parameter recorded in the input
- **THEN** acceptance is unavailable and no artifact changes

#### Scenario: Geometry-clean count does not need this exception

- **WHEN** the recovering, lost, and unrecovered counts are all zero
- **THEN** this research exception grants no authority, and the ordinary
  terminal-success checks apply unchanged

#### Scenario: Missing or inconsistent recovering distribution

- **WHEN** pair counts are missing, negative, non-integer, ambiguous, or their
  sum differs from the recovering total
- **THEN** acceptance is unavailable without publishing any artifact

#### Scenario: Summary and companion output disagree

- **WHEN** the recorded diagnostic counts differ from the re-parsed `phits.out`
  counts, or `phits.out` lacks a recognized summary
- **THEN** acceptance is unavailable

#### Scenario: Incomplete batches or additional failures

- **WHEN** the final recorded batch is below `maxbch`, the return code is
  nonzero, another active segment is incomplete, or the failure has another
  recorded reason
- **THEN** acceptance is unavailable

### Requirement: Explicit Staging Selection and Invocation Binding

Acceptance SHALL use one explicitly selected safe staging directory directly below workspace `analysis`, proven to belong to the failed invocation. The selection and output-set contract below MUST hold; missing invocation evidence MUST fail closed.

#### Scenario: Selected staging and output set are assessed

- **WHEN** the user explicitly selects a retained staging directory for acceptance
- **THEN** the following complete contract SHALL hold:

Acceptance SHALL use only one retained staging directory that the user selects
explicitly, located directly below the workspace `analysis` directory. The
system MUST NOT scan for, match basenames of, or automatically choose staging
candidates. The selected staging directory and its files MUST be ordinary safe
paths, with no link or reparse point. The system SHALL prove from recorded
execution evidence that the staging directory belongs to the failed segment's
invocation. When that binding cannot be proven, acceptance MUST be unavailable.

The candidate output set SHALL be exactly the required tally outputs that the
manifest derives for the failed segment. Missing required outputs or additional
candidate files MUST make acceptance unavailable.

#### Scenario: Staging not selected

- **WHEN** no staging directory is selected explicitly
- **THEN** acceptance is unavailable without any directory scan

#### Scenario: Staging from another invocation

- **WHEN** the selected staging directory cannot be bound to the failed
  invocation's recorded evidence
- **THEN** acceptance is unavailable and no artifact changes

#### Scenario: Authoritative prospective staging binding

- **WHEN** a selected staging directory has evidence captured by the adapter
  under Prospective Retained Staging Invocation Evidence
- **THEN** acceptance SHALL revalidate the recorded workspace-relative staging
  path, producing execution ID, segment identity, and all retained input and
  output SHA-256 values against that formal record
- **AND** content equality without the recorded invocation binding SHALL NOT
  substitute for missing historical evidence

#### Scenario: Output set differs from manifest

- **WHEN** a manifest-derived tally is missing from staging or an unexpected
  file would be published
- **THEN** acceptance is unavailable

#### Scenario: Unsafe staging path

- **WHEN** the selected staging directory or a file in it is a link, a reparse
  point, or outside the workspace
- **THEN** acceptance is unavailable

### Requirement: Preview-Bound Confirmed Apply

The system SHALL provide a read-only preview and confirmation-bound apply under the contract below. Apply MUST require the exact plan digest, explicit research-only acknowledgement, and execution lease, preserve original evidence, and publish outputs new-only with the receipt last.

#### Scenario: Preview and apply contracts are enforced

- **WHEN** a user previews or applies acceptance of a synthetic failed segment
- **THEN** the following complete contract SHALL hold:

The system SHALL provide a read-only preview that derives one canonical plan
digest. The digest binds the contract version, the workspace-relative source
and destination paths, the summary, preflight, manifest, execution-binding,
`phits.out`, and staging digests, the re-parsed diagnostics, and the expected
destination state. Preview MUST NOT write any file or start any external tool.

Apply SHALL require the exact confirmed plan digest and an explicit
research-only acknowledgement, and SHALL acquire the workspace execution lease.
It SHALL recompute the plan immediately before mutation and SHALL validate every
source and destination before its first write. A destination that already
exists with identical bytes MAY be reused. Any differing destination, plan
change, or missing acknowledgement MUST fail before any write. Apply SHALL
publish missing outputs new-only and then create the receipt new-only as its
final step. An existing receipt MUST cause failure without overwrite.

Apply MUST NOT edit, replace, move, or delete the segment execution summary,
preflight record, manifest, `phits.out`, or the staging tree. The failed
segment MUST remain recorded as failed.

#### Scenario: Confirmed plan is current

- **WHEN** apply receives the exact current plan digest and the acknowledgement,
  and every source revalidates
- **THEN** it publishes only the missing manifest-derived outputs and then the
  receipt, and every original evidence file keeps its exact bytes

#### Scenario: Destination conflict

- **WHEN** a published destination already exists with different bytes
- **THEN** apply fails before any write and leaves no partial publication

#### Scenario: Missing acknowledgement or stale plan

- **WHEN** the acknowledgement is absent or any bound fact differs from the
  confirmed preview
- **THEN** apply fails before mutation and requires a new preview

#### Scenario: Receipt already exists

- **WHEN** the receipt path already exists
- **THEN** apply fails without overwriting it

### Requirement: Versioned Workspace-Relative Receipt

The fixed receipt at `analysis/research_geometry_recovery_acceptance.json` SHALL use a version distinct from prototype schemas and record every field in the receipt contract below. All stored artifact paths MUST be workspace-relative; unsupported or malformed receipts MUST grant no authority.

#### Scenario: Complete receipt contract is enforced

- **WHEN** an acceptance receipt is created or validated for a synthetic workspace
- **THEN** the following complete contract SHALL hold:

The receipt at `analysis/research_geometry_recovery_acceptance.json` SHALL use a
schema version distinct from any prototype schema. It SHALL record:
`research_only: true`; a fixed purpose; the creation time in UTC; the tool
version; the confirmed plan digest; the summary, preflight, manifest, and
execution-binding SHA-256 values; the accepted segment identity; the recorded
and re-parsed geometry diagnostics including the recovering total and every
region-pair count; the revised acceptance-policy identity with zero lost and
unrecovered counts and no recovering-count or ratio cap; the `phits.out`
relative path and SHA-256;
the completed batch count and `maxbch`; the staging relative path; each staging
and published output with relative path, size, and SHA-256; the operator
acknowledgement and a free-text reason; and a `not_for` list naming clinical
use, commissioning, patient QA, and vendor certification.

The receipt MUST NOT contain absolute paths, user names, patient data, or DICOM
identifiers. The system SHALL reject free-text input that contains an absolute
path. A receipt with an unsupported or prototype schema MUST be rejected.

#### Scenario: Receipt is created

- **WHEN** apply succeeds on synthetic data
- **THEN** the receipt contains every required field with workspace-relative
  paths only

#### Scenario: Operator accepts a recorded distribution

- **WHEN** the operator explicitly accepts a fully validated recovering total
  and region-pair distribution for research output and provides a reason
- **THEN** the receipt binds that exact total, every pair count, the reviewed
  plan digest, the revised policy identity, acknowledgement, and reason
- **AND** a different diagnostic count or distribution invalidates that binding

#### Scenario: Prototype or malformed receipt

- **WHEN** the receipt is empty, is not a JSON object, lacks a required field,
  uses an unsupported schema, or contains an absolute path
- **THEN** it grants no authority

### Requirement: Receipt-Bound Downstream Authority

`validate_segment_execution_for_downstream` SHALL be the single branch point accepting ordinary terminal success or a fully revalidated fixed-path receipt. All four downstream stages MUST enforce the authority contract below; receipt existence alone MUST bypass nothing.

#### Scenario: Complete downstream authority is checked

- **WHEN** Sumtally Generate, Sumtally Run, RTDOSE Prepare, or RTDOSE Run assesses upstream authority
- **THEN** the following complete contract SHALL hold:

`validate_segment_execution_for_downstream` SHALL be the single branch point
that authorizes downstream processing. It SHALL accept either ordinary terminal
success, validated exactly as before this change, or a receipt that fully
revalidates. Full revalidation means that every recorded digest matches the
current summary, preflight, manifest, execution binding, `phits.out`, and
published outputs, and that the eligibility requirement still holds. Sumtally
Generate, Sumtally Run, RTDOSE Prepare, and RTDOSE Run SHALL each invoke this
gate and recompute digests at that stage.

The existence of a receipt file MUST NOT bypass any check. When no valid receipt
exists, every ordinary validation, including generation-time successful-summary
validation and finished-preflight validation, MUST behave exactly as before
this change. The gate MUST consider only the fixed receipt path and MUST NOT
scan for alternative or historical receipts.

#### Scenario: Valid receipt at every stage

- **WHEN** a fully revalidating receipt exists and the four downstream stages
  run in order with fake runners
- **THEN** each stage revalidates the receipt and proceeds

#### Scenario: Tampered or stale binding

- **WHEN** any single byte of the summary, preflight, manifest, `phits.out`,
  published output, or receipt changes
- **THEN** every downstream stage fails closed

#### Scenario: Receipt existence without validity

- **WHEN** an invalid or empty file exists at the receipt path
- **THEN** downstream stages remain disabled, exactly as when no receipt exists

#### Scenario: Ordinary path unchanged

- **WHEN** no receipt exists and the summary is not terminal success
- **THEN** Sumtally and RTDOSE fail closed with the same behavior as before this
  change

### Requirement: Research Exception Propagation and Audit

Every downstream summary authorized by a receipt SHALL carry the receipt digest and accepted segment identity under the audit contract below. The system SHALL provide read-only independent receipt verification and MUST preserve DICOM, dose, units, coordinates, MU, and normalization.

#### Scenario: Downstream audit contract is enforced

- **WHEN** receipt-authorized downstream processing or independent verification is requested
- **THEN** the following complete contract SHALL hold:

When downstream authority comes from a receipt, the Sumtally generation,
Sumtally execution, RTDOSE preparation, and RTDOSE execution summaries SHALL
each record a `research_exception` object that contains the receipt SHA-256 and
the accepted segment identity. Validation of a later stage SHALL require that
this marker is consistent with the current receipt. This change MUST NOT alter
RTDOSE DICOM attributes, dose values, units, coordinates, MU, or normalization.

The system SHALL provide an independent `--verify-only` mode that revalidates
the receipt and its bindings without writing.

#### Scenario: Marker propagated

- **WHEN** downstream stages run under receipt authority
- **THEN** every downstream summary records the same receipt digest and segment
  identity

#### Scenario: Independent verification

- **WHEN** a user runs verify-only on an unchanged synthetic workspace
- **THEN** it reports success and writes nothing

### Requirement: Relocated Receipt Revalidation

A receipt SHALL revalidate after a bounded workspace relocation that is accepted
by portable workspace recovery, using only workspace-relative identities.

#### Scenario: Workspace moved

- **WHEN** a synthetic workspace with a valid receipt is relocated through the
  accepted relocation path
- **THEN** the receipt revalidates without change

### Requirement: Edited PHITS Evidence Grants No Authority

The workflow MUST NOT offer, document, or accept manual editing of `phits.out`,
the segment execution summary, or the preflight record as a recovery method.
User documentation SHALL describe this capability as the only supported route
for eligible recovered geometry events without a rerun, and SHALL state that its
output is research-only.

#### Scenario: Evidence edited by hand

- **WHEN** `phits.out` or the summary is edited after a receipt was created
- **THEN** receipt validation fails and downstream stages remain disabled

### Requirement: Synthetic-Only Automated Acceptance Validation

Automated tests for this capability SHALL use only temporary synthetic
workspaces, synthetic tally and `phits.out` content, and fake external-tool
runners. They MUST NOT use real DICOM, real calculation outputs, licensed
tools, or paths outside test-controlled temporary storage.

#### Scenario: Automated acceptance is tested

- **WHEN** eligibility, preview, apply, gating, propagation, relocation, or
  retry refusal is exercised
- **THEN** all artifacts are synthetic and no real external process starts
