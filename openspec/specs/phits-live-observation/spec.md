# phits-live-observation Specification

## Purpose

Provide optional, read-only remaining-batch and single Isocenter-voxel
relative-error observations for owned PHITS 3.35 Windows OpenMP segments
without changing calculation inputs, execution authority, completion evidence
or downstream safety gates.
## Requirements
### Requirement: Owned Non-Authoritative Observation

The controller SHALL optionally publish bounded, atomic presentation data at
`analysis/phits_observation.json` using schema `dicomxphits_phits_observation_v1`,
bound to its workspace, invocation, current segment generation and input/runtime
identity. It MUST read only expected regular files in its owned staging and
reject links, reparse points and path escapes. Missing or invalid observation
MUST NOT authorize or prevent execution, retry, stopping or downstream use.
Existing mandatory execution evidence and v2-v5 summary contracts SHALL remain
unchanged. Observation MUST NOT modify PHITS inputs, outputs, batch control,
parameters, process signals or lease ownership.

#### Scenario: Low error or zero remaining batches

- **WHEN** an observation reports low relative error or zero remaining batches
- **THEN** no segment is marked complete and no downstream gate is unlocked without existing terminal-success evidence

#### Scenario: Observer fails

- **WHEN** sampling, parsing or sidecar publication fails
- **THEN** detail becomes unavailable without changing the PHITS outcome or weakening mandatory evidence validation

#### Scenario: Old or unsafe observation source

- **WHEN** a source belongs to another invocation, retired staging or an unsafe path
- **THEN** it is not sampled or adopted as current observation

### Requirement: Explicit Supported Batch Observation

Observation SHALL support only positively identified PHITS 3.35 Windows OpenMP
output with reviewed syntax and bound prepared runtime values. A filename or
layout alone MUST NOT establish version compatibility. The GUI SHALL show
observed remaining batches and prepared total separately, requiring an integer
remaining count between zero and the prepared total and rejecting within-run
regressions. It MUST NOT derive completion, histories, percent progress or ETA
from that counter. Other modes, versions or unrecognized records SHALL report
unsupported without changing the simulation.

#### Scenario: Supported counter

- **WHEN** a complete supported record reports 7 remaining against a prepared budget of 10
- **THEN** the GUI labels these as observed remaining and prepared total, not 3 verified completed batches

#### Scenario: Version or counter is ambiguous

- **WHEN** identity is absent, syntax is unknown, or the counter is contradictory
- **THEN** batch detail is unavailable rather than inferred from a filename or fragment

### Requirement: Descriptive Current-Segment Relative Error

Observation SHALL use only a complete matching dose/error pair for the current
manifest-selected primary 3D dose tally. Mesh, tally role, particle, output mode
and available history/restart metadata MUST agree. It SHALL locate the unique
mesh cell whose bin interior contains `(0, 0, 0)` in the existing PHITS
isocenter-origin coordinate system and report that cell's finite positive
relative error as percent only when its paired dose is also finite and positive.

The observer MUST NOT interpolate, select a nearest cell, add a coordinate
tolerance or change the existing mesh/coordinate mapping. If isocenter is
outside the mesh or lies on a bin boundary, the pair is incomplete or
mismatched, or the selected dose/error value is zero, negative, malformed or
non-finite, the relative-error detail SHALL be unavailable. The observer MUST
NOT substitute a value from `deposit-pdd.out`, compute full-mesh minimum,
maximum, median, mean, standard deviation or coverage, inspect DICOM RT
Structure contours, or calculate structure-based statistics.

The displayed value SHALL be identified as a provisional single Isocenter-voxel
reference, not whole-volume, ROI, combined-dose or clinical uncertainty and not
completion, convergence or automatic-stopping evidence. Tally and variance
settings MUST NOT change. Any future RT Structure relative-error evaluation
SHALL remain a separate post-completion capability and MUST NOT replace or
augment this live observation.

#### Scenario: Unique Isocenter-containing voxel is evaluable

- **WHEN** a complete matching primary 3D dose/error pair has one mesh-bin
  interior containing `(0, 0, 0)` with finite positive dose and relative error
- **THEN** observation reports only that cell's provisional `r.err` percentage
  and identifies it as an Isocenter-voxel reference

#### Scenario: Isocenter is not inside one voxel

- **WHEN** isocenter is outside the primary 3D mesh or lies on a bin boundary
- **THEN** relative-error detail is unavailable without interpolation, nearest-
  cell selection, coordinate tolerance or another-source fallback

#### Scenario: Incomplete or mismatched pair

- **WHEN** a slice is missing or dose and error metadata disagree
- **THEN** no new relative-error value is published

#### Scenario: Isocenter value is not evaluable

- **WHEN** the Isocenter voxel dose or relative error is zero, negative,
  malformed or non-finite
- **THEN** relative-error detail is unavailable and not represented as zero

#### Scenario: Other statistical sources are present

- **WHEN** PDD relative error, other mesh cells or RT Structure data are present
- **THEN** they do not replace or augment the single primary 3D Isocenter-voxel
  live reference

#### Scenario: Post-completion Structure evaluation exists

- **WHEN** a separately approved post-completion Structure evaluation is
  available
- **THEN** its statistics remain outside the live observation and do not alter
  live progress, convergence, stopping, completion, or downstream authority

### Requirement: Bounded Provisional Snapshots and Reset

Sampling SHALL run off the GUI thread, no faster than once per second, with one
in-flight job, one latest-result slot, bounded file/token/cell sizes and a
cooperative two-second deadline. Batch/header reads SHALL be at most 64 KiB,
each tally at most 256 MiB, tokens at most 64 characters, cells at most
10,000,000, and sidecars at most 64 KiB. Limit failures SHALL disable detail only.
Samples SHALL require complete supported syntax, stable before/after file
metadata and agreement across two successive observations; they MUST still be
labelled provisional, never atomic PHITS results. Batch/error sample ages SHALL
remain independent. Unchanged values MUST NOT receive a new sample timestamp.
After five seconds without a new accepted sample the GUI SHALL mark it stale.
Transitions, new invocations, workspace changes and owner loss MUST clear live
observation; delayed workers MUST NOT republish retired-generation data.

#### Scenario: Writer replaces or truncates a tally

- **WHEN** bytes or file identity change during sampling or a record is incomplete
- **THEN** the GUI shows updating/unavailable or explicitly stale prior values, never a new mixed snapshot

#### Scenario: Late worker after segment transition

- **WHEN** a completed sampling job refers to the previous segment generation
- **THEN** its result is discarded without replacing current observation

#### Scenario: Large or slow source

- **WHEN** a sampling resource limit is reached
- **THEN** the job yields unavailable and the GUI remains responsive without controlling PHITS

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

### Requirement: Equivalent Complete Observation Simplification

The live observer SHALL permit simplification of redundant computation, copies
and temporary data across one complete synchronous observation attempt while
preserving every existing validation obligation and observable state transition.
Reusing derived data MUST be limited to the same immutable snapshot within that
attempt. The implementation MUST NOT use cross-attempt caches or unchanged file
metadata as substitutes for fresh content reads and validation.

Guarded reads and any combined hashing SHALL preserve exact byte-content
signatures, safe-path and regular-file checks, link/reparse rejection, shared
access, before/after handle identity and post-read path identity checks, limits
and the shared deadline. Combining checks MUST NOT erase checks protecting
different times or sources. Shared-reader consumers MUST retain their existing
contracts. Batch/error outcomes and ages, counter-regression rejection,
successive-snapshot confirmation, timestamp retention and generation reset
SHALL remain unchanged, as SHALL worker scheduling and atomic publication.

#### Scenario: Read and hash work is combined

- **WHEN** an optimized read computes a digest while collecting bytes
- **THEN** it produces the same bytes and content signature as the existing guarded read, including prefix behavior, and still rejects replacement or truncation

#### Scenario: Metadata matches but content changes

- **WHEN** a later observation sees the same file size and timestamp with different bytes
- **THEN** fresh reading and hashing detect the changed content rather than reusing prior validated evidence

#### Scenario: One observation channel fails

- **WHEN** batch parsing fails while dose/error validation succeeds, or the reverse
- **THEN** the channels preserve their existing independent outcomes, confirmation state and sample ages

#### Scenario: Apparently duplicate safety checks

- **WHEN** checks before opening, during reading and after reading protect different freshness or path boundaries
- **THEN** simplifying the pipeline preserves those protections rather than removing them as redundant work

### Requirement: Equivalent Live Numeric Fast Path

Live observation SHALL support an explicitly selected optimized numeric path
that validates every cell in each complete dose/error pair. It MUST preserve
the scalar grammar, token limits, accepted numeric results, finite/nonnegative
checks, exact cell counts and all existing structural, pair, provenance and
prepared-runtime validation. Bulk conversion MUST follow full grammar validation
of its supported numeric subset; other supported spellings SHALL retain scalar
validation and conversion.

The optimization MUST preserve current fresh batch/history variance support,
Isocenter selection and positive-dose/positive-error requirements. It SHALL NOT
widen accepted modes, change default parsing behavior for post-completion
consumers, alter parser identity or sidecar schema, or confer execution,
completion, stopping or downstream authority.

#### Scenario: Valid canonical and fallback values

- **WHEN** a supported fresh pair contains canonical values and other supported numeric spellings
- **THEN** complete validation yields the same numeric values and Isocenter percentage as the scalar reference

#### Scenario: Malformed cell away from Isocenter

- **WHEN** any cell has invalid syntax, excessive token length, a negative or non-finite value, or the pair has missing or extra cells
- **THEN** the observer publishes no newly accepted voxel value even when the Isocenter cell itself is positive

#### Scenario: Unevaluable Isocenter or mismatched pair

- **WHEN** the selected dose/error is zero or the pair violates existing mesh, role, identity, metadata or runtime checks
- **THEN** fast conversion does not bypass the existing unavailable outcome

#### Scenario: Post-completion parser call

- **WHEN** Sumtally or Structure evaluation uses a shared parser without live opt-in
- **THEN** its existing scalar numeric path and accepted modes remain unchanged

### Requirement: Bounded Numeric Scratch and Deadline Checkpoints

The live numeric path SHALL use bounded tokenization and conversion chunks
without building a page-wide token-object list. New numeric scratch allocation
MUST be bounded independently of page cell count, with explicit limits for
scanned text, conversion tokens and any carried partial token. It MUST check
the same cooperative two-second sample deadline between bounded steps,
including whitespace-only scans and scalar fallback. Existing file, token,
cell, worker and scheduling limits SHALL remain unchanged.

An expired or resource-limited attempt MUST NOT publish a newly accepted value
or refresh the prior accepted timestamp. Existing updating, unavailable,
staleness, two-successive-observation confirmation and generation-reset behavior
SHALL remain in force. The bound on numeric scratch MUST NOT be presented as
a constant bound on total file/array memory or a hard process timeout.

#### Scenario: Large single numeric page

- **WHEN** an otherwise supported page contains substantially more cells than a conversion chunk
- **THEN** numeric scratch remains within declared chunk/carry bounds and every cell is still validated

#### Scenario: Token spans chunks

- **WHEN** a token crosses a scan boundary or a long whitespace run spans multiple scans
- **THEN** token semantics are preserved, overlong tokens are rejected, and deadline checks continue between bounded steps

#### Scenario: Deadline expires during conversion

- **WHEN** a checkpoint finds the shared sample deadline expired
- **THEN** observation reports the existing resource-limit outcome without accepting partial validation or changing PHITS execution

### Requirement: Provisional Synthetic Performance Evidence

Acceptance evidence for the integrated live optimization SHALL include five
declared complete synchronous observation attempts on an authored 101-cubed
positive-Isocenter pair with authored identity/runtime/batch records. Timing
MUST include guarded reads/hashes, full parsing/pair validation and candidate
handling. Every attempt's duration and outcome, timeout count, median, mean
and maximum SHALL be retained; completed-parse timings SHALL be distinguished
from timeout-censored attempts.

The provisional performance criterion SHALL be an all-attempt median at most
two seconds, with a majority of attempts completing full validation within the
unchanged deadline and two successive matching observations accepting the
authored value. It MUST NOT be represented as an all-attempt speed guarantee,
a PHITS runtime improvement, real-GUI verification or clinical validation.
Deterministic correctness/resource checks SHALL remain mandatory independently
of timing. Hardware/load limitations and unperformed verification MUST be
reported, and universal CI wall-clock pass assertions MUST NOT be introduced.

#### Scenario: Median passes with an occasional timeout

- **WHEN** five declared attempts meet the median and functional conditions but include a deadline rejection
- **THEN** the timing result may be provisionally accepted only with that failed attempt, timeout count and unchanged deadline behavior explicitly reported

#### Scenario: Fast early failures

- **WHEN** short durations result from unsupported identity or failed validation rather than successful complete parsing
- **THEN** those durations alone cannot satisfy provisional performance acceptance

#### Scenario: Integrated measurement is pending

- **WHEN** only an isolated prototype benchmark is available or suitable timing conditions are pending
- **THEN** it remains feasibility evidence and integrated performance acceptance is recorded as incomplete
