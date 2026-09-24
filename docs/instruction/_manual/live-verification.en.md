# Repaired GUI: live verification procedure and record sheet

Prepared: 2026-09-24. [日本語](live-verification.ja.md) / [Manual index](README.md)

This plan covers the `3 PHITS` observation display in a version containing [PR #84](https://github.com/inata169/dicomxphits/pull/84). It is a procedure with blank records, not a real-run acceptance report. The current authorization is for document preparation only.

## 1. Before starting

1. Leave the current ten-thread calculation running until it ends. Do not STOP, force-close, modify files or restart its GUI to perform this verification.
2. Establish completion from the GUI stage state and Activity log. Zero remaining batches or low relative error alone does not establish completion. Handle failure/interruption using the [operating manual](gui-manual.en.md).
3. After completion, establish that the next GUI will launch the repaired code. Merging main does not update an installed application or a running GUI. The repair commit is `95fc06d4d0d9589fd6c2f4f145c616be74807251`, merged as `fa5f0a32d98b8c843cec9bf42f6610d45e92d866`. Local commit `b45e623` contains the same repair. A v1.1.0 label alone cannot establish this.
4. Record the launch method, build, authorized non-patient phantom, new verification output destination, maxcas/maxbch/threads and observation period beforehand. Do not overwrite an earlier calculation or alter its inputs to test the display.
5. Obtain separate explicit approval for the exact real-PHITS verification run. Preparing this document does not start or authorize a new calculation or rerun. Keep the execution within the education/research fixed-field 3D-CRT scope.

Copy the blank record sheet to a verification-record directory outside the repository before filling it in. Keep only blank templates here; do not add real output files, DICOM, UIDs, personal information, real-data screenshots or local configuration. Use anonymous case/destination aliases in records intended for publication.

## 2. Interpreting the display

| Item | Meaning for verification |
| --- | --- |
| `Observed remaining batches` | Provisional remaining count for the current segment, not whole-case percent progress or completion evidence. |
| `prepared total` | Prepared batch budget; keep it unchanged within the segment. |
| `Isocenter voxel r.err` | Provisional statistical relative error for one voxel in the current segment; separate from Structure evaluation. |
| `provisional` | An accepted observation, not an atomic PHITS result or convergence guarantee. |
| `stale` / `age` | The last accepted sample is old. Five seconds without a new sample also produces this label; it can be normal during a long batch. |
| `Unavailable` | The current detail cannot be safely presented; it does not directly establish PHITS failure. |

Sampling runs no faster than once per second, and a new sample requires two successive matching complete observations. Intermediate batch numbers may be skipped and detail may temporarily become unavailable during writes. Display rounding can hide changes in the underlying value. **Do not require relative error to decrease on every update.**

## 3. Verify normal updates

1. Under the separately approved conditions, launch the repaired GUI and prepare the verification workspace using the normal workflow. Use the supported PHITS 3.35 Windows OpenMP configuration. Start the calculation owned by this GUI through `3 PHITS` → `Run PHITS segments`. Opening a completed case alone does not start live observation.
2. Record the first valid observation's time, current segment, remaining count, prepared total, r.err and each channel's state and age.
3. Record approximately every 30–60 seconds or when the display changes. This is the human recording interval, not a change to application sampling. Where possible, capture three distinct accepted samples within one segment.
4. Start a new section when the segment changes. Do not compare counts or errors across segments as one monotonic series.
5. Assess within the planned observation period. If the required updates do not occur, record “Unverified”; do not automatically extend runtime, histories or rerun count. Ending observation is separate from stopping computation. Follow the approved calculation ending policy.

### Checks and acceptance criteria

| ID | Check | Pass criteria / when to record Unverified |
| --- | --- | --- |
| A | Remaining-count updates | Observe a decrease in newly accepted remaining counts within one segment, bounded by zero and prepared total. Displaying every batch is unnecessary. |
| A1 | Minute/second format regression | Where source reading is authorized, establish that the current complete batch record uses minutes and seconds for CPU duration and that a count from that generation or later is accepted. If only seconds occur, or source records are not inspected, leave this item unverified. Never edit a real file to manufacture the format. |
| B | Isocenter relative-error updates | Observe adoption of a new sample corresponding to a complete new pair. Distinguish samples by value or accepted timestamp/age. Identical rounded values or occasional increases alone are not failures. If no new pair occurs, leave this unverified. |
| C | Recovery after a temporary failure | Use the distinction below. If no failure occurs in the real run, record “Not observed / Unverified”; do not substitute synthetic-test success for real-run acceptance. |
| D | Segment transition and termination | Previous-segment values are not adopted as new observations. Clearing live detail or making it unavailable after termination is normal. Use stage state/logs for completion. |

## 4. Recovery after a temporary failure

If `stale` or temporary unavailability occurs naturally, record its start and the subsequent adoption of a new observation. A `stale → provisional` transition alone does not prove recovery from a Windows sharing conflict: ordinary waiting for a batch update produces the same transition.

Verify the Windows sharing/access-conflict regression with authored development fixtures, without locking, editing or deleting files in the real calculation. These tests already passed for PR #84; listing them here is not an instruction to launch another test now.

- `test_publication_recovers_from_sharing_failure_on_new_sample`: publication of a new sample after Windows errors 5/32/33.
- `test_windows_sidecar_reader_cannot_permanently_stop_observation`: recovery after an actual Windows sharing conflict on an authored file is released.
- `test_unsafe_publication_still_disables_observer`: continued rejection of an unsafe destination.

Recovery covers the specified temporary Windows conflicts, not every exception. Resuming observation is not restarting or resuming PHITS computation.

## 5. When updates appear frozen

1. Record segment ID, values, states, ages and wall-clock time. Do not stop computation or modify files to investigate the display.
2. Only with separate read authorization, briefly read the verification workspace's `analysis/phits_observation.json` and close it immediately. Avoid readers that hold replacement-blocking handles open. Do not edit and save the file.
3. Within the same invocation and segment, compare `sequence`, each channel's `reason`, `sample_utc` and `sample_age_seconds`. GUI age also includes time since the last publication, so it can differ from the stored JSON age.
4. Advancing sequence with old sample timestamps suggests unchanged sources or rejected parsing. A frozen sequence suggests stopped sampling/publication. Neither observation alone establishes the cause. Even `reason=available` can coexist with increasing age when the source sample remains unchanged.
5. Preserve reasons such as `unsupported-format`, `resource-limit` and `pair-mismatch` in the investigation record. Changed output bytes alone do not prove a complete matching pair was available. The observation JSON may be removed at termination.

## 6. Blank record sheet

All entries are initially unperformed. Use “Pass / Fail / Unverified / Not applicable” with a reason.

| Preparation record | Entry |
| --- | --- |
| Date, timezone and operator | — |
| Repaired commit/build and launch method | — |
| Confirmation that the current calculation ended | — |
| Reference to approved run conditions and ending policy | — |
| Non-patient case alias and new output-destination alias | — |
| Windows, PHITS version and OpenMP threads | — |
| maxcas / maxbch / mesh | — |
| Planned observation start/end and other load | — |
| Scope of authorization to read sources/observation JSON | — |

| Time | Segment | Remaining / total | Batch state / age | r.err (%) | Error state / age | Sample distinction / notes |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |
| — | — | — | — | — | — | — |
| — | — | — | — | — | — | — |

| Failure/suspected-failure start | Observed reason and evidence | Recovery time and new sample | Outcome and limitations |
| --- | --- | --- | --- |
| — | — | — | — |

| ID | Result | Evidence alias and time / reason unverified |
| --- | --- | --- |
| A Remaining count | Unverified | — |
| A1 Minute/second format | Unverified | — |
| B r.err | Unverified | — |
| C Temporary-failure recovery, real run | Unverified | Record explicitly if no event occurs |
| C Synthetic sharing-conflict tests | Previously passed; not rerun here | [PR #84 repair record](observation-refresh-fix.md) |
| D Transition/termination | Unverified | — |
| Remaining issue / next decision needed | — | — |

Passing display-update checks does not establish clinical dose correctness, convergence, patient QA, STOP behavior or real-data Structure-statistics validation. No additional Sumtally or RTDOSE execution is needed for observation verification.
