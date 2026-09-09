# Run incomplete PHITS segments

This stage-2 feature is for the fixed 6 MV public 3D-CRT education/research
workflow. It retains verified successful segments and restarts incomplete
segments from the beginning. It does not resume PHITS statistics or add history.

## GUI workflow

1. Select the existing workspace with its current tool configuration.
2. On PHITS, choose **Run incomplete segments...**. Evidence inspection runs in
   a background worker. The preview lists retained successes, scheduled segments,
   and skipped entries.
3. Confirm that preview. Execution revalidates the source record and all bound
   conditions before launching only the scheduled segments.
4. Progress distinguishes retained and newly completed segments. The elapsed
   time belongs to this attempt; ETA waits for a success in this attempt.
5. After every active segment validates, use the normal downstream workflow.
   Existing downstream artifact conflicts still require the established recovery
   action and its preservation permission.

The workspace selection controls remain locked while PHITS is active. Unexpected
programmatic changes to selection invalidate old progress/terminal callbacks.
One workspace cannot be executed concurrently from multiple GUIs or CLIs.

## CLI workflow

For newly prepared work, supply the explicitly configured PHITS installation
and executable on the original run so runtime identity can be captured:

```text
dicomxphits-run-segments --workspace-root <workspace> --phits-root-folder <installation> --phits-executable-path <executable>
```

Read-only inspection prints JSON containing `retained`, `scheduled`, `skipped`,
and `source_sha256`. Inspection launches no external process:

```text
dicomxphits-run-segments --workspace-root <workspace> --phits-root-folder <installation> --phits-executable-path <executable> --plan-incomplete
```

After reviewing that plan, execute with its source digest:

```text
dicomxphits-run-segments --workspace-root <workspace> --phits-root-folder <installation> --phits-executable-path <executable> --run-incomplete --expected-summary-sha256 <preview-digest>
```

An already-complete valid retry is a no-op. A rejected retry leaves the existing
execution summary intact. Failed attempts preserve verified earlier results but
never authorize partial Sumtally aggregation.

## Evidence and eligibility

New execution records are v5; eligible v4 records remain retryable. Retry binds the manifest, actual input bytes,
recursive includes, preparation summaries, child environment digest, configured
executable, and the file membership and bytes of the explicitly selected PHITS
installation. The workspace itself is excluded from the installation tree when
nested there because its inputs and results are bound separately.

Installation hashing is conservative and may take time. Changes elsewhere in
that selected installation tree, including other work stored there, can reject a
retry. Do not select a broad filesystem root as an installation. Linked runtime
dependencies and unsupported external input forms do not establish retry
eligibility. No machine-wide executable/data discovery is performed.

Ordinary runs can record that retry identity is unavailable (for example, no
installation path or preparation evidence was supplied). Such a record does not
permit selective execution. A missing or changed required result, input,
dependency, runtime, or model/calibration binding requires a new prepared
workspace; a damaged success is not silently scheduled for replacement.

Legacy v2/v3 records retain their prior downstream behavior, but cannot establish
selective retry eligibility. They are not upgraded from current file hashes.
Selective execution initially requires the original resolved workspace and tool
identity. Bounded relocation remains available for ordinary downstream inspection
without discovering or loading the former computer's tools.

The [Stop after current segment](segment-boundary-stop.md) control can now end
an owned retry-capable v5 invocation at a verified boundary. Use this same
incomplete-segment preview after a user stop; old stop requests never carry over.

Successful segment files are kept byte-for-byte without changing modification
times. Prior summaries are preserved under
`analysis/segment_attempt_history/<unique-attempt>/summary.json`, with source
digest and producer identities carried forward. Do not manually edit these
records or promote preserved staging directories.

## Interruption and ownership

The persistent `.dicomxphits-execution.lock` file represents OS-held ownership,
not a lock inferred from its text or age. It remains present after clean exit.
Do not delete it to bypass a busy workspace. Direct PHITS children inherit the
ownership handle, so a surviving child prevents another execution even if its
controller has exited. Once OS ownership is released, a valid orphaned v4 record
may be inspected and retried from its incomplete segment boundaries.

No immediate/batch stop controls, batch/error parser, checkpoint rescue, automatic external
workspace migration, or additional-history accumulation is included. The
original failed external workspace and its retained staging remain excluded.
Automated tests use synthetic files, fake PHITS runners, and temporary Python
children for ownership tests. These tests do not establish real PHITS behavior,
clinical suitability, or dose validity.
