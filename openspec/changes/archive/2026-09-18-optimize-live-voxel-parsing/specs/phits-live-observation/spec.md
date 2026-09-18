## ADDED Requirements

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
