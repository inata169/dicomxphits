# Design

## Scope and dispatch

Simplify the complete `Observer.sample` path, including identity/batch handling,
guarded reads and hashes, decoding/parsing, pair checks, Isocenter selection and
candidate-record construction. Prefer the smallest understandable data flow;
do not add a framework or a parallel implementation merely to reduce timings.
Worker scheduling, atomic publication and GUI rendering remain unchanged.

Use a normal imported helper selected explicitly by the live observer. Keep
the existing scalar parsing route as the default for shared-parser callers.
Do not ship the experiment's dynamic source replacement or monkeypatch a
global parser. An internal opt-in hook may reuse structural/pair validation;
tests must show that Sumtally and Structure consumers retain their existing
numeric behavior and accepted modes. No format widening or parser/schema
identity change is intended.

## Simplification of one complete attempt

First identify actual repeated computation and allocation by source review and
bounded synthetic instrumentation. Retain a short before/after map showing
which work was removed or combined and where each validation still occurs.
No unmeasured claim that read/hash or state handling is the main cost is made.

Candidates include hashing bytes as they are read instead of traversing the
joined buffer again, avoiding repeated decoding/slicing of the same snapshot,
passing already parsed metadata rather than parsing it again, and constructing
only records needed by the existing candidate state machine. Adopt a candidate
only if it demonstrably removes work without adding disproportionate complexity.
These are options to evaluate, not a requirement to rewrite every stage.

Reuse is confined to immutable bytes and derived values inside one attempt.
Do not cache file validation across attempts, skip a fresh read because size or
mtime is unchanged, or infer content identity from metadata alone. Each fresh
attempt still hashes all bytes used by the existing content signatures. If
hashing is combined with reading, its digest must match hashing the exact
returned byte sequence, including the existing header-prefix behavior.

Keep safe-path checks, regular-file/link/reparse rejection, shared-handle
semantics, before/after handle identity, post-read path identity, read limits
and deadline checks. These checks protect different moments and are not
duplicate work. Preserve short handles and PHITS write/delete access. Any
internal change to a shared reader must preserve all caller-visible contracts
and pass its existing consumer tests; no caller gains new accepted inputs.

Preserve separate batch/error outcomes and ages, counter-regression rejection,
two successive matching snapshots, timestamp retention, timeout/staleness and
owner/generation reset. Do not collapse independently failing observations into
one result or reuse a previous accepted value as newly validated evidence.
No validation, file guard or acceptance transition may be deleted merely because
a fixture or timing run succeeds without it.

## Numeric validation and resource handling

The common fast path recognizes only the validated nine-character spelling
`digit.three-digits E sign two-digits` without the explanatory spaces, for
example `1.234E-03`. Validate every position before bulk conversion; NumPy's
conversion tolerance is not a grammar validator. Check converted count,
finiteness and nonnegativity for every cell. Other accepted spellings, including
D/d exponents, signs and negative zero, retain scalar validation/conversion.
Preserve bitwise float results on accepted differential fixtures.

Tokenize incrementally within the existing numeric page text. Proposed bounds
are at most 64 KiB of scanned text per step, at most 4096 conversion tokens per
chunk, and at most 64 carried token characters across a text boundary. Preserve
the original ASCII whitespace/token semantics; reject a 65th token character
and excess cells without constructing the rest of a page-wide token list.
Check the same absolute sample deadline before/after each scan/conversion step,
including whitespace-only and scalar-fallback chunks. Never reset the deadline
per file, page or chunk. Exact helper signatures remain an implementation choice.

These limits bound new numeric scratch allocations, not total process memory.
Raw pair bytes, decoded text/page copies and output arrays remain bounded by
current file/cell limits; proven unnecessary copies may be removed within an
attempt. Do not claim streaming of the entire file
or constant total memory. Record allocation evidence and deterministic chunk
bounds without requiring extreme multi-million-token allocations on this PC.
The deadline remains cooperative; bounded operations can overshoot slightly,
but an expired attempt cannot publish a newly accepted value.

All page, mesh, role, source-weight, seed, newly-started output, maxcas and
maxbch checks remain mandatory. Validation covers invalid cells away from
Isocenter as well as the selected voxel. Zero or nonpositive selected dose/error
continues to mean unavailable. No diagnosis of zero values belongs here.

## Provisional performance protocol

Use an authored 101 x 101 x 101 dose/error pair with varying canonical values
and a known positive Isocenter value. Supply authored identity, prepared runtime
and batch files so that the real integrated synchronous `Observer.sample`
entry point performs identity/batch reads, guarded pair reads/hashes, full
validation, selection and candidate confirmation. Fixture generation is outside
the timer. This measures observation latency, not PHITS simulation speed.
Use the same complete measurement boundary before and after simplification.
Instrumented stage/allocation measurements explain changes but do not replace
uninstrumented whole-attempt acceptance timings.

Declare five consecutive measured attempts before starting; use the same
unchanged fixture and observer, with the normal minimum sampling interval.
Select median as the primary statistic before timing. Report every elapsed
time and state/reason, median, mean, maximum, successful full-parse count and
timeout count. Do not discard slow attempts or replace them with extra trials.
A timeout is a censored failed attempt, not evidence of completed parsing.
Report timings of completed parses separately from all-attempt timings.

Provisional acceptance requires an all-attempt median at most two seconds,
a majority of attempts that complete full-pair validation within the deadline,
and two successive valid matching observations that accept the authored value.
These functional conditions prevent rapid early failures from satisfying the
timing criterion. Later unchanged samples must not refresh the timestamp;
timeout must retain only explicitly stale prior data or yield unavailable.
Timeouts do not alone defeat provisional median-based acceptance, but their
count and resulting presentation remain mandatory evidence.

Record supported Python/NumPy versions, mesh/file sizes, cache conditions and
known concurrent load without inspecting unrelated user applications. Do not
run full pytest concurrently with timing. On 2026-09-18 the human explicitly
replaced the idle-load wait with measurement during the reported ongoing
seven-thread PHITS calculation. Record this as user-reported concurrent load;
do not inspect or control that GUI. Eight-thread load remains unverified.
Historical isolated results
remain feasibility evidence, not a replacement for integrated-path measurement.

Do not add a universal CI wall-clock assertion. Use deterministic synthetic
tests for expired deadlines and checkpoint coverage. Background worker/sidecar
behavior is covered separately with mocks; the sample benchmark excludes GUI
rendering and publication latency. Real GUI display, real-output timings,
cold-disk performance and different machines remain explicitly unverified.

## Alternatives and boundaries

Raising the deadline, skipping distant-cell validation, accepting zero values,
or relaxing source provenance are excluded. A cache or incremental architecture
would require a separate approved design. The approximate 1.5-second prototype
engineering target is not the new acceptance gate; the human selected provisional
median at most two seconds. Neither that criterion nor a passing synthetic
benchmark establishes clinical accuracy or convergence.

## Implemented work reduction and preserved checks

Source inspection found a separate full-buffer SHA256 traversal after chunked
reads and a prototype page-sized token list followed by a page-sized numeric
array/copy. The implementation hashes the same bytes during existing bounded
reads, scans at most 65536 characters plus a bounded carry, converts at most
4096 tokens at once, and writes into the existing output-array view. No
dynamic source replacement or new dependencies are used.

Identity and batch files already have distinct roles and bounded reads; no
redundant metadata parse was demonstrated there. Candidate records encode
independent outcomes and timestamps, so that state machine was retained.
Structural parsing and pair validation remain shared, and scalar numeric
parsing remains the default for non-live callers. Whole-file decode/page copies
remain; removing them would enlarge the structural-parser change without
evidence that it is needed for the approved provisional target.

Synthetic allocation inspection, excluding the pre-existing input string but
including the output array, measured traced peaks of 790972 bytes for 10201
cells and 1707035 bytes for 100000 cells. Corresponding isolated prototype
peaks were 891329 and 6816226 bytes. These are page-helper allocations, not
whole-observer RSS, timing acceptance or worst-case memory guarantees.

Complete integrated benchmark tooling is available as
`tools/benchmark_live_observation.py`. It creates only authored files in a new
directory and refuses an existing destination. `--check-only` uses a small
pair to verify bitwise scalar/fast equivalence and two-sample confirmation,
without a performance acceptance run. Normal mode measures five complete
101-cubed observations and writes every outcome, cache/load notes and statistics.
