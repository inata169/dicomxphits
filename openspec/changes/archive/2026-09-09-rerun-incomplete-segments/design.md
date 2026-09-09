# Design: selective segment execution

## Baseline and boundaries

`run_segments` currently creates a new v3 invocation and runs all active entries.
`phits_staging_contract` enumerates workspace-local inputs and recursive includes;
`persistent_segment_outputs` enumerates declared outputs and companion files.
`WorkspaceOutputGuard` protects paths against replacement but is not a mutual
exclusion lock for execution. GUI exclusion currently applies to one GUI process.

Reuse these mechanisms and the strict manifest, model, calibration, geometry,
digest, and downstream validators. Do not change calculation parameters. Do not
parse batch progress, implement stop controls, resume PHITS checkpoints, combine
partial tallies, or modify random seeds or statistical normalization.

## New evidence baseline

New direct runs write `dicomxphits_public_segment_execution_v4`. Each record
contains the established progress fields plus a versioned execution binding:

- canonical manifest digest and ordered unique segment identities;
- relative paths and SHA-256 values for every active segment input and its
  complete recursive input dependency set, including referenced CT/material and
  model inputs; both membership and bytes are bound;
- preparation evidence identifying the source handoff and effective fixed-model,
  calibration, geometry and calculation configuration consumed by preparation;
- actual rendered runtime settings, relevant child environment, the explicitly
  configured PHITS executable's content identity, and configured runtime
  dependencies needed to establish identical execution conditions;
- per-success required output paths/digests, zero return code, clean geometry
  evidence, original producing invocation, and original timing.

The implementation must enumerate dependencies from the supported prepared
input/tool configuration, not scan a machine or infer version identity from a
filename. Unsupported dependency forms or missing required identity evidence
make selective execution unavailable. Synthetic executable identities are used
in automated tests. Tool identity is comparison evidence, not vendor certification.

Capture binding before launch, compare the actual staged inputs to it, and
revalidate before accepting segment success and at retry boundaries. A changed
input observed at a boundary invalidates reuse even if outputs still exist.
The preview is advisory: execution rechecks all evidence under exclusive
ownership. Caches must not authorize launch or terminal success.

Existing v2/v3 summaries retain their established read-only presentation and
terminal downstream behavior. They are never upgraded in place for retry, even
if current files appear unchanged. This first retry release requires the same
resolved workspace root and tool identity as the new baseline; relocation-aware
downstream inspection remains supported independently.

## Planning and execution

Expose a read-only plan through the existing segment CLI, proposed as
`--plan-incomplete`, and execution as `--run-incomplete`. The GUI has a distinct
Run incomplete segments action. A plan identifies its workspace, source record
digest, retained successes, incomplete targets, and inactive/skipped entries.

Eligible sources are valid v4 failed/gate-failed records, or orphaned running
records whose execution ownership can be proven released. A success record is
a no-op after validation. A malformed record, missing binding, or unprovable
ownership rejects the action. A segment recorded successful whose evidence fails
validation rejects the entire plan rather than scheduling replacement.

After confirmation, acquire exclusive ownership and revalidate. Preserve the
source summary and its digest in an exclusively created workspace-local attempt
history before replacing the current summary. Failure to preserve it starts no
child. Write the new non-success current record atomically before launch, with
one new run ID and parent attempt identity. Retained entries preserve their
producer run IDs and timing; new results belong to the new invocation.

Execute only pending, interrupted-running, failed, or gate-failed active entries
from the beginning in manifest order. Never promote old staging. Preflight the
complete target write set: no target, error output, companion log, cleanup path,
or shared root output may overlap retained artifacts or bound inputs. Reject
collisions before mutation. Existing guarded fresh-staging publication is used
only for selected incomplete segments. Retained artifacts are not rewritten,
touched, moved, or deleted; inspect bytes and modification times in tests.

Persist each boundary atomically. A later failure preserves earlier verified
entries but remains overall incomplete. Terminal success requires a fresh full
check of all retained and newly produced successes, with exactly one result per
active manifest identity. No partial result is accumulated statistically.

## Execution ownership and crash handling

Use one canonical workspace lock for both ordinary and selective PHITS entry
points. The lock must cover preflight, staging, publication, and terminal evidence.
It must exclude a second controller while any launched PHITS child can still
write. Directory protection alone, a GUI busy flag, PID existence alone, or a
timeout-based lock-file deletion is insufficient.

Use supported OS ownership mechanisms and synthetic child-process tests to
verify controller-death behavior. If ownership cannot be proven released, fail
closed; do not kill a process or automatically remove an uncertain lock. A
read-only plan must not mutate lock/evidence files. Repository-controlled
conflicting workspace mutations must also reject active ownership. This is
cooperative application exclusion, not protection against arbitrary user edits.

## GUI and downstream behavior

Show retained and scheduled segment lists before execution. Revalidate the
preview snapshot on confirmation; a changed selection or evidence requires a
new preview. Keep Tk responsive and prevent repeated clicks or another stage
from launching. Freeze relevant workspace selection controls during execution
and check the resolved selected root again for polling and terminal callbacks.
This explicitly covers the unresolved PR #60 selection-change finding.

Display retained successes separately from newly completed successes. Overall
verified count is their sum; elapsed time belongs to the new invocation, and ETA
uses only successful durations measured in that invocation. A retained count
alone does not create an estimate. All-success/no-target plans start no process
and leave the record unchanged, directing the user to ordinary downstream gates.

Sumtally and workspace recovery use the same v4 all-active-success validator.
Old successful downstream summaries cannot override a current incomplete record.
Historical downstream collisions retain the existing explicit recovery workflow;
selective PHITS execution neither archives nor regenerates downstream files.

## Validation and delivery

Test success/failure/interruption with synthetic workspaces and fake runners,
including changed input/dependency/model/runtime/executable bindings, altered or
missing success artifacts, malformed records, duplicate identities, output
collisions, stale previews, repeated attempts, publication failures, and GUI
selection changes. Verify real temporary process exclusion without real PHITS.

Run focused and related suites, full public checks, and strict OpenSpec
validation. Keep the change active until approval, implementation, validation,
and accepted-delta promotion/archive are complete. Each later development stage
requires its own proposal and approval.
