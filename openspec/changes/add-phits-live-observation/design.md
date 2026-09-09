# Design: optional, non-authoritative PHITS observation

## Evidence and version boundary

`gui_tool_profile.py` selects the `phits-3.35-windows` layout and
`bin/phits335_win_openmp.exe`. A layout name is not executable-version proof.
The renderer uses a 3D xyz mesh, `output=dose`, `axis=xy`, and `part=all`.
The existing runner executes in private staging and publishes outputs only
after validation; observing final workspace copies would show stale results.

The [official PHITS 3.35 manual](https://phits.jaea.go.jp/manual/manualE-phits335.pdf),
sections 3.2, 5.2.2 and 5.2.24, documents remaining batches in `batch.out`,
batch-end tally updates for `itall=0/1`, parallel-update qualifications, relative
errors and separate error files for 2D plots, and `file(22)` for the batch file.
The same manual describes editing the batch counter to stop; that write is
explicitly excluded here. Public HTML manuals are mutable and must not be used
to infer 3.35 compatibility. No official output fixtures are copied into Git.

Before enabling a parser, record its exact supported grammar and a matching
3.35 version marker from the owned run's output, together with the selected
runtime binding and OpenMP mode. Missing or ambiguous identity is unsupported,
not guessed from a filename. MPI, custom layouts/modes, other versions,
alternate output layouts and historical runs are unsupported in this stage.
The proposal does not authorize locating or launching an installed PHITS binary.

## Data flow and authority

1. The controller binds a new observation generation to workspace, run ID,
   segment ID/ordinals, input/runtime digests and its own staging allocation.
2. A bounded worker reads only the expected batch, version-header, dose and
   error files in that allocation. No directory discovery or external path
   supplied by a file is followed. Reject links/reparse points and path escapes
   using existing workspace protections; do not acquire a second execution lease.
3. The controller publishes small atomic observation records at
   `analysis/phits_observation.json`, schema
   `dicomxphits_phits_observation_v1`. This is disposable presentation data,
   not an extension of the execution summary and not a retry parent artifact.
4. The GUI accepts only its owned live run and current segment generation,
   checks the observation schema/binding/sequence, and displays availability.
   It never reads arbitrary staging paths itself.

The sidecar contains identity, sequence, parser/version identity, UTC sample
time, monotonic sample age, availability/reason, batch fields and aggregate
error fields. It contains no raw tally array. Its absence, corruption or write
failure only disables observation. Existing execution-summary persistence
failures retain their existing fatal behavior; this proposal does not soften it.
Downstream/retry validation neither trusts nor requires this sidecar.

Clear observation on segment transition, retry, run termination, selection
change and controller loss. A terminal detail is not retained as a new result
history. No adoption of orphaned/stale files from prior runs is allowed.

## Batch semantics

Display the observed remaining-batch integer and the unchanged prepared
`maxbch` as separately labelled facts. Require a reviewed full record and
`0 <= remaining <= prepared maxbch`; reject contradictory or regressing
within-generation samples. Do not compute a percent, completed-history count,
current-batch ordinal, or a new ETA from this counter. It can be externally
edited and is never evidence that a batch or segment completed. Zero remaining
still means only an observation; the authoritative success gate is unchanged.

## Relative-error semantics

Only the current segment's generated 3D dose tally is in scope; PDD and summed
or historical results are excluded. Parse all expected slices and cell counts,
with matching actual mesh, tally identity, particle, output mode and available
history/restart metadata in dose and error files. An incomplete or unmatched
pair is unavailable. Do not fill missing bins or reuse a partial array.

Use the entire prepared 3D mesh, not a clinical ROI. A cell contributes only
when dose and relative error are finite and strictly positive. Zero dose and
zero error are excluded and counted explicitly as unevaluable, not interpreted
as perfect precision. Negative, non-finite or malformed values invalidate the
sample. Positive relative errors above one are valid and are not clipped.
Report total cells, valid cells, excluded cells, coverage, and the median and
maximum of valid relative errors multiplied by 100 (percent). For an even valid
count the median is the arithmetic mean of the two middle values. No valid cells
means unavailable, never 0%. Excluded categories must not be double-counted.
These are descriptive per-cell statistics, not the uncertainty of mean dose or
the combined plan. Do not change `istdev`, `itall`, `epsout`, histories or tallies
to obtain more convenient observations.

## Concurrent writes, bounded work and availability

Read-only sampling cannot prove PHITS file writes are atomic. Require complete
supported syntax and consistent metadata plus unchanged file identity/size/time
before and after reads and agreement across two successive observations before
publishing a candidate. This is only a provisional snapshot, not proof of a
transaction or completed batch. If same-generation consistency cannot be
established, display unavailable. Do not label a mixed or torn sample current.
Show independent timestamps for batch and error observations; never imply they
belong to the same batch without matching evidence.

Poll no faster than once per second, permit only one sampling job and one
latest-result slot, and keep parsing off the Tk thread. Cap individual batch
and header reads at 64 KiB, tally files at 256 MiB each, numeric tokens at 64
characters, and cell count at the existing 10,000,000 limit before allocation.
Use chunked reads with a cooperative two-second sample deadline; exceeding a
limit yields resource-limit/unavailable without changing the simulation.
Accept a sidecar of at most 64 KiB. No unbounded queue or repeated full-file
parsing on the GUI thread is allowed.

Show waiting, available/provisional, updating, stale, unsupported, or unavailable
with a bounded reason. An unchanged accepted sample keeps its original age;
polling must not make it appear newly updated. After five seconds without a new
accepted sample label it stale even if a slow batch explains the delay. Earlier
values may remain visibly stale for the same segment, never as current data.
Observer cancellation on transition must not kill PHITS, block lease release
indefinitely, or write into a retired staging allocation.

## Validation and stopping rule

Use authored synthetic grammar fixtures and fake writers for valid multi-slice
outputs, partial overwrites, replaced files, mismatched metadata, unsafe paths,
unknown identity, numerical edge cases and resource bounds. Test interleaved
GUI selection/run changes, segment-boundary stopping, selective retry and
unchanged downstream refusal at zero remaining/low relative error. Prove that
observation leaves PHITS inputs, control files, outputs and successful-result
digests unchanged and does not change exit outcomes.

Actual Windows OpenMP output identity/flush behavior, parser compatibility and
desktop responsiveness under real PHITS remain unverified until separately
approved testing. If public evidence is insufficient for an exact parser
grammar, report that limitation before implementation instead of fabricating
support. Synthetic success is not an endorsement of real-tool compatibility.
