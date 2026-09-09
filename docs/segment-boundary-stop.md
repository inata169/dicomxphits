# Stop after the current PHITS segment

This control requests a verified segment boundary in the fixed 6 MV, 3D-CRT
education/research workflow. It does not interrupt a PHITS calculation, resume
partial statistics, or guarantee how soon the current segment will finish.

## GUI

1. Start ordinary PHITS execution or an explicitly confirmed incomplete-segment
   attempt. The Stop after current segment button becomes available only after
   the GUI recognizes its owned v5 invocation and complete retry identity.
2. Click **Stop after current segment**. Sending or sent is not acknowledgement.
   Wait for **Stop pending**, which reflects the controller's durable acceptance.
3. The segment committed at acceptance finishes and undergoes the normal input,
   output, geometry and publication checks. No following segment is launched.
4. A verified partial stop displays **User stopped**, with completed and remaining
   counts. Sumtally remains disabled. Use **Run incomplete segments** and confirm
   a fresh plan when ready to continue; the prior stop request is not inherited.

The controller serializes request acceptance and launches. If a launch wins the
race, that segment is the one allowed to finish; a click alone cannot guarantee
that the segment currently painted on screen is still current at acceptance.
Requests cannot be withdrawn. Other stages and workspace selection stay locked
until terminal evidence is checked. Full-run ETA is hidden while stop is pending.

If any execution or evidence check fails, the result is failure/incomplete, not
a successful user stop. If all active segments finish successfully, the result
is normal completion, even when the request overlaps the final segment.
Controller death or lost GUI connection is not proof of safe stopping. Existing
inherited workspace ownership prevents takeover while a surviving child writes.

## Controller input contract

The GUI uses an opt-in `--control-stdin` flag on the segment CLI. An automation
owning that controller may use the same dedicated stdin pipe. Send one UTF-8
newline-delimited JSON object, at most 4096 encoded bytes including newline:

```json
{"operation":"stop-after-current","workspace_root":"<exact recorded resolved workspace>","run_id":"<current invocation>","request_id":"<unique ASCII letters-digits-underscore-hyphen ID>"}
```

The controller's running summary, not pipe write success, acknowledges the
request through `stop_requested`. Request IDs are 1-128 characters. Wrong
identity, unknown fields, malformed/oversized messages, and unsupported evidence
cannot acknowledge stopping. No global stop file or cross-controller endpoint
exists. Closing stdin does not request a stop. Do not send this record to PHITS.

CLI exits remain 0 for success, 2 for an exception, and 3 for a failed execution
summary. Exit 4 specifically denotes validated user stopping. A GUI must verify
matching workspace, run ID, summary and artifacts rather than trust that number.

## Compatibility and limits

New runs write v5. Valid v2/v3/v4 records remain readable. Eligible v4 and v5
results can be explicitly retried without rewriting their parent evidence;
new retry attempts use v5. Missing retry identity does not enable stop controls,
and historical files are not upgraded by hashing their current contents.

No immediate kill, batch-boundary stop, signal-based stop, timeout change,
checkpoint rescue, statistical continuation or additional history is included.
Real PHITS, real data, old failed external workspaces and remaining staging were
not used for verification. Tests use synthetic workspaces, fake PHITS runners
and temporary Python processes for control/ownership behavior. This is not
clinical or real-PHITS validation.
