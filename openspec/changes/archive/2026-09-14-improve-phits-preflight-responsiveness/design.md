# Design

## Decisions and limits

Do not recursively enumerate or hash the configured PHITS installation. The
execution binding covers the exact explicitly selected PHITS executable plus
the existing workspace-local inputs and evidence. Before every PHITS child
commitment, resolve the selected executable, require the existing absolute-path,
regular-file and configured-path safety checks, calculate its SHA-256, and
match the invocation-bound executable path and digest. Do not search for an
executable, infer dependencies from filenames, clone an installation or add a
persistent hash cache.

Files elsewhere in the configured installation are outside this binding. Their
addition, removal or mutation does not by itself reject execution or retry, and
the workflow makes no claim to detect it. This is an explicit reduction of the
old installation-wide identity contract, justified by the observed repeated-scan
cost. It does not reduce workspace input, result or downstream validation.

The old stop contract requires retry-capable evidence. Do not fabricate that
evidence during an incomplete scan. Introduce a distinct preflight receipt at
`analysis/segment_preflight.json`, schema
`dicomxphits_segment_preflight_v1`, bound to resolved workspace, GUI nonce and
controller run ID. Acquire the same exclusive workspace ownership before
publishing it or accepting cancellation. It is not an execution summary.

Required receipt facts: schema, identities, phase, monotonic elapsed time,
UTC update time, monotonically increasing sequence, scanned file/byte counts,
request identity when present, and whether a first child was committed. A
terminal `cancelled_before_launch` requires that commitment to be false and
durable acknowledgement. No partial binding, result or total-count estimate
can grant execution, retry or downstream authority. Use distinct CLI exit 5
only with a matching terminal cancellation receipt; retain stopped exit 4.

The receipt also records a rejected preparation request identity when
commitment won the race. A finished receipt binds the actual execution-summary
SHA-256 and its result run ID; this may be an unchanged, fully revalidated parent
for a selective no-op. Finished preparation alone is not execution success:
existing execution-summary and downstream validators still decide eligibility.

## State and control

1. Acquire ownership; publish `preparing` before bounded binding checks. Missing
   or malformed identity/evidence fails closed and cannot unlock a control.
2. Hash only the selected executable and bound workspace files, with control
   checkpoints before each file open and between reads of at most 1 MiB. Publish
   bounded progress at most four times per second; show counts already read,
   not a percentage based on an invented total. Do not walk the installation
   tree to obtain membership or totals.
3. Before the first child commitment, Cancel preparation and commitment share
   the same serialization boundary. Acknowledgement prevents all child launch.
   Abort only preparation work; close scanner handles and persist cancellation
   without finishing a full binding that cannot authorize any result anyway.
4. If commitment wins the race, reject preparation cancellation explicitly;
   never convert it silently into a kill or segment stop. The existing explicit
   Stop after current segment remains the available action.
5. During subsequent verification, service existing boundary-stop requests at
   bounded hashing checkpoints. Acknowledgement prevents another commitment,
   but all validation required for committed/retained results and terminal v5
   stopping still finishes. Show `verifying results`, not an invented active
   segment. Recheck the selected executable immediately before any next child
   commitment, not by rescanning its installation.

A blocked OS read is not an opportunity to kill a thread or process. The
checkpoint bound is a work bound, not a universal wall-clock deadline. Display
stalled/unavailable progress honestly; never claim accepted or terminal state
from a sent message, timer, or missing process alone.

## Preservation and recovery

The separately approved Windows receipt-publication fix retries only atomic
replacement of analysis/segment_preflight.json for WinError 5 or 32: at most
three attempts, with two requested 50 ms waits (100 ms total requested delay,
not a wall-clock guarantee for OS calls). Reuse the same flushed temporary bytes
and retain workspace ownership/directory guards; revalidate the target before
each attempt. Persistent denial still raises, without successful publication or
downstream authority. Other outputs, guard failures, tool runs and preparation
scans are not retried. This restores publication under brief reader contention;
it does not guarantee success against a reader held beyond the bounded waits.

Keep source attempt summaries and outputs byte-for-byte unchanged if a selective
attempt cancels during preflight. A newer preflight receipt takes precedence
over older success for current-attempt presentation and dependent actions.
It cannot become a retry source. Read-only recovery offers a new explicit
preflight: a cancelled ordinary attempt reruns all gates, while a cancelled
selective attempt must revalidate its unchanged original parent and preview.
No automatic resumption, old staging reuse, or source-summary migration.

Once any child is committed, existing v5 terminal/evidence rules are unchanged.
Known validation failures take precedence over cancellation or stopping; a
crash before durable terminal receipt remains interrupted, never cancelled.
The lease covers cleanup of owned scanner resources and durable publication.
No touching pre-existing failed workspaces or staging.

Required result evidence follows the existing segment-success contract: every
declared primary tally output remains required, together with the statistical-
error companion of the manifest-selected 3D output and the existing logs. PHITS
may instead embed relative error in a secondary tally's primary output, as in
the PDD `r.err` column. Separate error companions for secondary tallies remain
retained and hashed when PHITS produces them, but their absence alone does not
invalidate an otherwise completed segment. This does not change PHITS inputs,
tally physics or dose processing.

PHITS `batch.out` is different from those immutable result artifacts. It is a
control/progress file whose bytes may change during execution or through an
explicit user edit. The observer may read it and publication may retain a
snapshot, subject to the same containment and no-link protections, but its path,
digest or remaining-batch value is not required completion evidence and is not
compared as immutable retained-result evidence. In particular, changing
`0 <--- number of remaining batches` to `-1 <--- number of remaining batches`
does not by itself produce an artifact-mutation error. Any resulting nonzero
process exit, missing required output, invalid geometry evidence, incomplete
summary, stopped state or failed ownership/evidence check still fails closed.

For provisional relative-error presentation, use the error value from the
manifest-selected primary 3D dose companion only. Continue requiring a complete
matching primary-dose/error pair to establish supported mesh identity and data
integrity. The Isocenter voxel is the unique cell whose existing PHITS mesh-bin
interior contains `(0, 0, 0)` in the already defined isocenter-origin coordinate
system. Do not interpolate, select a nearest cell, change coordinate transforms
or introduce a physical tolerance. If isocenter is outside the configured mesh
or lies on a bin boundary, or the selected dose/error value is not evaluable
under the existing numeric checks, display the observation as unavailable.

Report only that provisional Isocenter-voxel `r.err` percentage and sample age.
Do not calculate or display full-mesh minimum, maximum, median, mean, standard
deviation or coverage. Do not read `deposit-pdd.out` for the representative
value and do not inspect DICOM RT Structure contours or calculate structure-
based statistics. The label must state that the value is a single reference
voxel, not whole-volume or clinical uncertainty and not completion evidence.

## Compatibility and approval boundary

All preflight readers must reject unknown versions and stale workspace/run
bindings. They must not read an installation merely because a historical
receipt names it. Downstream gates explicitly recognize the new non-success
receipt; older readers must not receive fabricated v5 success/stopped evidence.
New execution evidence explicitly identifies the bounded executable scope rather
than recording an installation membership list. Compatibility readers continue
to parse historical execution summaries and preserve their workspace/result
meaning without rewriting them. Any new child launch, including selective retry,
must bind the currently selected executable under the revised scope and must not
reintroduce an installation-wide scan; historical installation membership is not
silently represented as newly verified bounded evidence.
