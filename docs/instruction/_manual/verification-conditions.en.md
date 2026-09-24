# Proposed verification conditions for the PR #84 GUI repair

2026-09-24. [日本語](verification-conditions.ja.md) / [Procedure and record sheet](live-verification.en.md) / [Index](README.md)

Status: **proposal prepared; execution not approved or performed**. The request authorizes planning without launching real PHITS. The running ten-thread GUI, settings and calculation directories have not been operated on.

## One proposed verification run

| Item | Proposed condition |
| --- | --- |
| Start prerequisite | After the current calculation ends, its terminal state is confirmed, and exact run conditions and paths are approved. |
| GUI | Launch code containing PR #84: repair `95fc06d`, merge `fa5f0a3`; local `b45e623` has identical repaired contents. Do not replace the running GUI. |
| Candidate case | `<approved-non-patient-case>`; the real case identifier is not published. Confirm permission and non-patient phantom provenance before execution. No source-data inspection was repeated here. |
| Inputs | Propose the case's validated frozen CT2PHITS handoff as input to a fresh workspace. Do not overwrite its existing calculation workspace or results. Confirm the exact frozen inputs and validity before preparation. |
| PHITS | Supported PHITS 3.35 Windows OpenMP; exact executable path and version remain to be confirmed. |
| Threads | 10 |
| maxcas | 4,000,000 histories/batch |
| maxbch | Propose 10 batches/segment. Apply through new-workspace preparation settings, not by editing existing generated inputs. |
| Segments | Assume two active segments for this proposal. Confirm before execution and perform one normal all-active GUI run. Revise the proposal if the count differs; no selective omission, addition or automatic retry. |
| Mesh, geometry and physics | Preserve the original approved case conditions. No observation-driven mesh, coordinate, source, physics, MU or normalization change is proposed. Record the actual mesh before execution. |
| Output | A fresh `gui-pr84-check-001` workspace under an approved verification parent, independent of the repository, PHITS installation, source data and existing calculation destinations. The absolute path is unresolved. If occupied, propose a different fresh name rather than reuse it. |
| Records | Propose a separate fresh sibling `gui-pr84-check-001-evidence`. Keep real data and local configuration outside the repository. Neither directory is created in this task. |
| Launch count | One GUI `Run PHITS segments` action; up to two PHITS child executions if two segments are active. No rerun or automatic extension. |
| Excluded execution | No CT2PHITS rerun, Sumtally, RTDOSE or GPR. An unusable frozen handoff requires a separate decision. |

## Workload and time estimate

The user estimates that “4,000,000 takes about five minutes.” This proposal provisionally interprets that as **one maxcas=4,000,000 batch taking approximately five minutes for the same case at ten threads**. It is not a measured result or runtime guarantee. If the estimate instead refers to a whole segment or another unit, do not use the following timing estimate.

| Unit | Nominal histories | Estimate under that assumption |
| --- | ---: | --- |
| One batch | 4,000,000 | About 5 minutes |
| One segment, ten batches | 40,000,000 | About 50 minutes |
| Two segments | 80,000,000 | About 100 minutes |

Preparation, output, transitions and result validation add time. Segments and computer load may differ. Elapsed time is not guaranteed to scale directly with nominal histories. Do not equate PHITS `cpu time` with elapsed time. Separately establish whether the minute/second format actually occurs.

## Observation and ending policy

1. Use the first 30 minutes after transport starts in segment one for focused observation. Record counts, r.err, state and age approximately every 30–60 seconds or on visible updates. Five minutes per batch suggests about six batches, but does not guarantee six accepted observations. Aim for three distinct accepted samples within one segment.
2. Record the initial assessment at 30 minutes. **This is not a computation timeout.** The proposal waits for natural completion of ten batches in each of two segments. Do not STOP, kill or edit inputs merely because the observation window ends.
3. Also record the transition to segment two and final termination. Approximately 100 minutes is an estimate, not a deadline. If longer, record the situation without automatic reruns, added batches or forced termination. Any necessary change of ending policy is a human decision.
4. Verify decreasing remaining counts and adoption of new r.err samples. Do not require monotonically decreasing r.err. A stale label during a long batch alone is not a failure.
5. Limit source batch/observation JSON inspection to the separately approved verification workspace. Record under A1 whether a complete minute/second record occurred and a subsequent count was accepted. Otherwise mark it unverified.
6. Do not deliberately cause sharing conflicts in a real calculation. Without an established natural event, real-run recovery remains unverified; distinguish it from the existing successful synthetic regression tests.

This roughly 100-minute proposal cannot establish observation continuity beyond 24 hours or recovery from every temporary failure. Real-data validation of Structure freshness, STOP or dose accuracy is outside its acceptance scope.

## Items to finalize before execution

| Unresolved item | Handling |
| --- | --- |
| End of the current calculation | Not checked here; no monitoring in this task. |
| Phantom permission/provenance and exact frozen-input location | Human selection followed by authorized read-only confirmation. |
| Repaired GUI launch route and PHITS executable | Establish build and exact paths in the final run conditions. |
| Absolute workspace and evidence paths | Select the approved parent and finalize both paths. No existence checks or creation occurred here. |
| Active count, original mesh and other case conditions | Confirm and record by authorized reading; revise if assumptions differ. |
| Five-minute batch estimate | Conditional use of the user's estimate; record deviations from the first actual measurement. |
| Execution approval | Obtain it for the finalized exact conditions. Document-preparation approval is not a substitute. |

Use the [procedure and record sheet](live-verification.en.md) for records and acceptance. Deliverables here are the two language proposals and index update only. Runtime, tests and public specifications are unchanged; no real tool was launched.
