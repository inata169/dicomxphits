# Design

## Decisions and limits

Preserve the complete runtime binding. Removing files or replacing SHA-256 with
size/mtime would weaken current guarantees without a proven dependency model.
Do not clone an installation, discover a new installation, or add a persistent
hash cache. The current task improves visibility and control responsiveness,
not the throughput of a full successful calculation.

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

1. Acquire ownership; publish `preparing` before a recursive scan. Missing or
   malformed identity/evidence fails closed and cannot unlock a control.
2. Enumerate and hash with checkpoints before each entry/open and between reads
   of at most 1 MiB. Publish bounded progress at most four times per second;
   show counts already read, not a percentage based on an invented total.
3. Before the first child commitment, Cancel preparation and commitment share
   the same serialization boundary. Acknowledgement prevents all child launch.
   Abort only preparation work; close scanner handles and persist cancellation
   without finishing a full binding that cannot authorize any result anyway.
4. If commitment wins the race, reject preparation cancellation explicitly;
   never convert it silently into a kill or segment stop. The existing explicit
   Stop after current segment remains the available action.
5. During subsequent verification, service existing boundary-stop requests at
   scanner checkpoints. Acknowledgement prevents another commitment, but all
   validation required for committed/retained results and terminal v5 stopping
   still finishes. Show `verifying results`, not an invented active segment.

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

## Compatibility and approval boundary

All preflight readers must reject unknown versions and stale workspace/run
bindings. They must not read an installation merely because a historical
receipt names it. Downstream gates explicitly recognize the new non-success
receipt; older readers must not receive fabricated v5 success/stopped evidence.
Install-wide scanning is retained, including its known cost. Any proposal to
reduce its scope must establish complete runtime dependencies and mutation
detection before a separate human decision. This proposal grants no such work.
