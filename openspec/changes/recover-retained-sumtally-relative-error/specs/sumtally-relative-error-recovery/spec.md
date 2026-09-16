## ADDED Requirements

### Requirement: Explicit retained-evidence recovery preview

The system SHALL provide a read-only recovery preview only for one explicitly
selected unchanged workspace and one explicitly selected preserved Sumtally
staging directory directly below that workspace. It MUST NOT scan for staging
directories, select a candidate implicitly, normalize a relocated workspace,
or start PHITS, Sumtally, phits2dicom, or another external tool.

The preview SHALL fail closed unless the canonical manifest, successful
Sumtally generation and terminal execution summaries, generated wrapper and
includes, current official combined dose, retained wrapper and includes, and
retained combined dose/error pair all have supported schemas, safe paths,
matching geometry and semantics, and exact current digests. The retained dose
MUST be byte-identical to the official dose and its recorded terminal digest,
and the retained generated inputs MUST match the generation evidence.

An eligible preview SHALL derive one canonical `recovery_plan_sha256` that
binds the contract version, workspace-relative source and destination paths,
all authority-bearing evidence digests, validated pair semantics and geometry,
and expected destination state.

#### Scenario: One retained pair is eligible

- **WHEN** the user explicitly selects one ordinary preserved staging
  directory and every required current and retained artifact exactly validates
- **THEN** the system returns a read-only recovery preview with a canonical
  plan digest and does not change the workspace

#### Scenario: Candidate selection would require discovery

- **WHEN** no staging directory is explicitly selected or more than one
  candidate would need to be searched or inferred
- **THEN** recovery is unavailable without scanning, basename matching, or
  automatic candidate selection

#### Scenario: Retained evidence differs

- **WHEN** a retained input or dose differs from current recorded evidence, or
  the retained dose/error pair has unsupported or mismatched semantics,
  geometry, values, or digests
- **THEN** preview fails without mutation or external-tool execution

### Requirement: Confirmation-bound new-only recovery apply

Recovery apply SHALL require the exact explicitly confirmed
`recovery_plan_sha256`, acquire the workspace execution lease, retain guarded
path identities, and recompute the complete plan immediately before mutation.
Any mismatch MUST fail before a write. Apply MUST NOT execute an external tool
or edit, replace, move, or delete the original generation summary, execution
summary, official combined dose, RTDOSE evidence, or preserved staging tree.

Apply SHALL atomically create the official combined-error output new-only and
then atomically create one versioned supplemental receipt new-only at
`analysis/sumtally_relative_error_recovery_summary.json`. The receipt SHALL use
workspace-relative artifact identities and bind the original summary digests,
canonical manifest and input digests, official dose/error digests, validated
geometry and semantics, confirmed plan digest, and recovery contract version.
It MUST NOT contain raw grids, DICOM content, identifying data, or a clinical
conclusion.

#### Scenario: Confirmed plan remains current

- **WHEN** apply recomputes the explicitly confirmed plan without change and
  both destinations are absent
- **THEN** it publishes the official error and supplemental receipt new-only
  without changing historical or downstream evidence

#### Scenario: Plan changes before apply

- **WHEN** any selected path, source, summary, artifact, digest, semantic fact,
  geometry fact, or destination state differs from the confirmed preview
- **THEN** apply fails before mutation and requires a new preview

#### Scenario: External execution is considered

- **WHEN** recovery preview or apply is requested
- **THEN** no PHITS, Sumtally, phits2dicom, or other external-tool process is
  started

### Requirement: Fail-closed partial-publication resume

An official error file without the supplemental receipt SHALL grant no
Structure-evaluation authority. The system MAY resume an interrupted apply
only when the fixed receipt is absent and the existing official error is an
ordinary safe file whose complete bytes and digest exactly match the
revalidated retained error and current dose/error contract. The resumed apply
SHALL recompute and confirm a new plan before publishing only the receipt.

Any different existing error, existing invalid receipt, linked or reparse
target, or conflicting destination MUST fail without overwrite, rename,
deletion, fallback, or external execution.

#### Scenario: Error was published before interruption

- **WHEN** the receipt is absent and the existing official error exactly
  matches the currently revalidated retained error
- **THEN** a newly previewed and confirmed apply may publish only the new-only
  supplemental receipt

#### Scenario: Existing destination conflicts

- **WHEN** the official error differs or any receipt already exists but does
  not validate as the exact current receipt
- **THEN** recovery fails closed and changes no existing file

### Requirement: Supplemental receipt authority is Structure-only

The post-completion Structure evaluator SHALL accept the exact supplemental
receipt only when the original Sumtally execution has terminal success, direct
combined-error evidence is absent, the receipt schema and canonical identity
validate, and the current official combined dose/error pair independently
revalidates against every receipt, generation, execution, manifest, geometry,
semantic, and digest binding.

The receipt MUST NOT change or grant PHITS completion, Sumtally completion,
RTDOSE eligibility, RTDOSE currentness, convergence, stopping, clinical, or
other downstream authority. The evaluator MUST consider only the fixed receipt
path and MUST NOT scan for alternative, historical, or backup receipts.

#### Scenario: Exact supplemental evidence is current

- **WHEN** direct combined-error evidence is absent and the fixed receipt plus
  current official dose/error pair fully revalidate
- **THEN** the pair may become authoritative only for the existing explicit
  post-completion Structure evaluation

#### Scenario: Supplemental evidence is stale or conflicting

- **WHEN** any bound artifact or evidence changes, direct and supplemental
  evidence conflict, or the fixed receipt is absent, malformed, linked,
  mismatched, or unsupported
- **THEN** Structure evaluation remains unavailable without another receipt,
  historical fallback, or downstream effect

### Requirement: Synthetic-only automated recovery validation

Automated recovery tests SHALL use only temporary synthetic workspaces,
synthetic tally content, and fake or mock external-tool runners. They MUST NOT
use patient DICOM, licensed tools, real calculation outputs, facility values,
or paths outside test-controlled temporary storage.

#### Scenario: Automated recovery is tested

- **WHEN** preview, apply, resume, path security, stale evidence, or receipt
  consumption is exercised in automated validation
- **THEN** all artifacts are synthetic and every external-tool runner proves
  that no real execution starts
