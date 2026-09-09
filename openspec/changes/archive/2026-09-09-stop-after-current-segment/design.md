# Design: verified segment-boundary stopping

## Existing contracts

`run_segments` holds inherited workspace execution ownership throughout its
invocation, writes atomic segment-boundary records, and validates inputs,
outputs, geometry evidence, and retry provenance. Its loop currently continues
through active segments without a user-stop channel. GUI `run_stage` currently
waits through `subprocess.run`; a Tk worker alone cannot communicate a stop
request to that running controller. Do not add a signal/kill shortcut.

## Controller ownership and request channel

Add an opt-in `--control-stdin` controller mode used by the GUI's PHITS adapter.
Other stage adapters keep their existing behavior. The GUI owns a dedicated pipe
to its direct segment controller; PHITS continues receiving its existing input
through its separate child pipe. No stop request is sent to PHITS itself.

Use bounded newline-delimited UTF-8 JSON records (maximum 4096 encoded bytes per
record), identifying operation `stop-after-current`, resolved workspace, current
run ID, and a unique request ID. The GUI derives the run ID from accepted current
invocation evidence, never a historical record. No machine-wide discovery,
workspace sidecar control file, cross-GUI takeover, or remote control endpoint.
CLI callers may opt into the same channel; ordinary invocations without it keep
their current behavior. Keyboard interrupts and controller death are not safe
stop acknowledgements. EOF does not silently request stopping or kill a child.

Only the owning coordinator may accept requests, commit a new segment launch,
and write execution summaries. A reader may queue messages but cannot publish
summary state or release the workspace lease. Serialize acceptance with launch:
if a request wins, the next segment cannot commit; if launch wins, that segment
is the current one which is allowed to finish. Acknowledgement records that
segment identity, or null if no launch is committed. Never imply that clicking
the button alone has already stopped admission of new work.

Malformed, oversized, wrong-workspace, wrong-run, or terminal-run messages cannot
change execution state. Report rejection without granting stop acknowledgement.
Duplicate valid requests are idempotent; stop-pending cannot be withdrawn.
Keep the inherited OS lease through child exit, validation, publication, and
terminal evidence. A blocked or failed control pipe must not freeze Tk or kill
the controller. Drain controller output without pipe deadlocks.

## State and race ordering

An accepted request is durably acknowledged with `stop_requested` metadata while
overall stage status remains `running`. The GUI shows request sent until that
acknowledgement, then Stop pending / stopping after the identified segment.
Read the control channel while PHITS is running; do not wait until all segments
finish before acknowledging. No bounded time to actual stop is promised.

At the boundary, finish the existing staged-output checks and persist the
segment result. Evaluate terminal state in this order:

1. Any observed execution, evidence, publication, or required-persistence failure
   takes precedence over a requested stop (`failed` or `gate_failed`). Do not
   start a later segment after an acknowledged request even if the current one
   fails. Without a stop request, existing failure behavior is unchanged.
2. If every active entry is verified successful, use terminal `success`, even
   if the final-segment completion overlaps a stop request. A late request cannot
   downgrade or rewrite an already committed terminal record.
3. Otherwise, when a stop was acknowledged and no segment remains running,
   persist terminal `stopped`; unstarted active entries remain `pending`.

Requests accepted before the first launch stop without launching a segment when
work remains. Between segments they stop before the next launch. Zero-target
validated retry plans remain the existing no-op, not a new stopped attempt.
Failure to persist acknowledgement must not authorize another launch. The
current child still finishes under ownership; no successful safe stop may be
claimed without its required durable terminal evidence. Controller death leaves
the last nonterminal snapshot interrupted, even if a stop was requested.

## Versioned evidence and retry compatibility

Use `dicomxphits_public_segment_execution_v5` rather than extending the strict
v4 status vocabulary in place. Keep all existing bindings and producer/timing
semantics. Add a nullable acknowledged stop record containing request ID,
target run/workspace, acknowledgement UTC/monotonic timing, and boundary segment
identity. A `stopped` record requires that acknowledgement, no running/failed
entries, at least one pending active entry, consistent counts, and current valid
binding/provenance for all retained and newly completed successes.

The stopped controller returns a distinct exit code 4; existing success (0),
exception (2), and failed summary (3) behavior remains. GUI presentation requires
matching exit and validated summary, not exit code alone. Contradictory or
missing terminal evidence is an error/incomplete outcome, not safe stopping.

Readers continue accepting valid v2/v3/v4 under their established contracts.
Selective execution accepts eligible v4 and v5 sources, including v5 stopped
attempts; new attempts write v5 and reset stop metadata. Parent chains may mix
v4 and v5 without rewriting old records or bypassing existing digest validation.
Legacy evidence without retry identity remains ineligible. Stop controls are
available only for owned new invocations with a complete retry-capable binding;
missing identity is explained, not reconstructed from old results.

Stopped evidence never authorizes Sumtally or recovery, even if historical
downstream summaries succeeded. Resumption always uses the stage-2 preview and
fresh validation, retaining successful file bytes and modification times. The
stop channel never grants overwrite, preservation, or downstream permissions.

## GUI scope

Add one Stop after current segment action on PHITS, for ordinary and selective
owned runs with supported evidence. Keep other stage actions, repeated launches,
and workspace selection disabled until the controller exits and terminal state
is validated. The stop action is the narrow permitted control exception, not
another stage. Bind request and terminal callbacks to run/workspace identity.
After stopping, display User stopped, completed/remaining counts, and the explicit
Run incomplete segments next action; do not label stopped as completed or failed.
While pending, label any full-run ETA as such or hide it: it is not a guaranteed
time to stop. Window close, immediate cancellation, and signal policies are not
expanded; lost ownership/GUI connection cannot imply a verified safe stop.

## Verification

Use fake runners, deterministic synchronization barriers and injected clocks to
exercise before-first, in-segment, between-segment, and final-segment races.
Cover current/earlier failure precedence, input/output changes, persistence and
control failures, repeated/stale/malformed requests, all-complete no-op, retry
after stop, resetting requests, and mixed-version provenance. Test GUI pending
acknowledgement, responsiveness, identity changes, exit/evidence disagreement,
and downstream refusal. Use only synthetic Python processes for inherited
ownership and pipe lifecycle tests, including controller death with a live child.

Run focused checks, compile, full pytest, public-tree audit, strict OpenSpec,
and Git diff/status checks. Approval and implementation precede promotion and
archive; proposal-only validation is not evidence that stopping works. Real
PHITS or interactive real-workspace testing requires separate exact approval.
