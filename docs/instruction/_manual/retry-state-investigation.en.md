# Investigation of GUI state after STOP and retry

This is the pre-fix investigation record. See the subsequent [repair record](retry-fix.en.md).

2026-09-24 / baseline `4ad7a1e` / `codex/gui-manual-research`.
[日本語](retry-state-investigation.ja.md)

## Findings

The two previously uncertain observations have been separated. A stopped case can legitimately be blocked for downstream recovery while remaining eligible for incomplete-segment retry. However, the hidden synthetic GUI reproduction confirmed both stale recovery text after successful retry and a blocked downstream path in existing-case mode. This is more than a labeling issue. Product fixes were outside the approved investigation scope and were not made.

The user's GUI running ten threads, its settings, workspaces and processes were untouched. This investigation used a separate hidden Tk instance; no existing windows were enumerated, operated or captured.

## Reproduction

Actual GUI callbacks, segment execution and evidence validation were used with a fake external runner. A two-segment case stopped after its first segment, was inspected as an existing case, retried its remaining segment, and was inspected again.

| Point | Observed state |
| --- | --- |
| Inspect stopped case | Workspace: Invalid existing case; PHITS: Not reusable; downstream: Blocked. Retry enabled. Recovery cites the missing unfinished segment output. |
| Retry succeeds | PHITS: Completed. Old Workspace/downstream labels and missing-output explanation remain. Both ordinary Sumtally Generate and Create DICOM RT Dose are disabled. |
| Independent result validation | `segment_execution_authorizes_sumtally(workspace)` returns True. Retained and newly completed results meet the PHITS evidence gate for ordinary Sumtally generation. |
| Inspect again | PHITS returns to Not reusable; rejection changes to missing matching SHA-256 evidence. Reinspection alone does not enable downstream continuation. |

The initial fake call list was only `seg_001`; retry called only `seg_002`. No callback errors occurred. An audit hook prohibited external process execution. Tool-profile availability was mocked as ready, so real tool discovery was not tested.

## Causes

1. `gui.py`, `inspect_selected_existing_workspace` (around line 3033), maps downstream recovery rejection to Invalid/Not reusable/Blocked labels. The retry button uses separate evidence conditions in `refresh_action_button_states` (around line 2545). Blocking downstream processing while permitting validated retry is consistent, although the wording can imply that the entire case is unusable.
2. `finish_stage_success` (around line 4076) updates PHITS completion but does not reinspect or update `recovery_inspection` and `recovery_status`. Button refresh through `set_busy(None)` continues to use that cached inspection. The obsolete missing-output explanation therefore remains after those outputs exist.
3. Existing-case mode disables ordinary Sumtally and RTDOSE actions (around line 2633). Meanwhile, `workspace_recovery.py::_digest_evidence_sources` (line 224) collects hash evidence from Sumtally generation/execution, RTDOSE preparation and their recovery history, not the segment execution summary itself. `inspect_existing_workspace` requires this additional evidence even after validating successful PHITS execution. A case that has never generated Sumtally can pass the ordinary PHITS-to-Sumtally evidence gate yet fail this recovery gate, leaving no enabled downstream GUI route in existing-case mode.

Line numbers refer approximately to the baseline; function names are the stable references. The fixture is minimal, but source inspection identifies evidence-source selection, rather than merely dummy dose text, as the cause of this SHA-256 rejection. This does not establish reproduction with real PHITS or every existing case. Cases with valid prior Sumtally evidence follow a different path.

## Manual and repair implications

The manual can distinguish downstream blocking from incomplete-segment retry. It must not currently promise that Completed after retry enables existing-case downstream continuation. Restarting or reinspecting alone is not a demonstrated solution.

A repair would need to address both refreshing recovery state after completion and safely continuing from current validated PHITS evidence when Sumtally has never been generated. Bypassing evidence checks, editing summaries or deleting results is not a proposed workaround. Relevant contracts are guided-gui-workflow's Guided Existing-Workspace Recovery and phits-segment-retry's Complete Unique Downstream Evidence After Retry. Implementation and historical-evidence compatibility require separate review.

## Reproduction and validation

The [diagnostic script](support/investigate_retry_state.py) creates no visible window. It asserts the observed defect and is diagnostic code, not a regression test specifying desired product behavior.

```text
.venv/Scripts/python.exe docs/instruction/_manual/support/investigate_retry_state.py --session-root <new-isolated-directory-outside-repository>
```

The diagnostic passed and saved `result.json` in its isolated directory. Always supply a new directory. Synthetic outputs and the JSON containing local absolute paths are not included here.

The initial focused pytest run produced 70 setup errors because its default temporary directory was inaccessible. A short `-x --tb=short` run confirmed the same PermissionError; the suite was rerun in the approved execution environment. Final results are recorded below.

Product runtime and public specifications are unchanged. No commit or PR was created. The investigation stops before product repair.

### Final validation results

| Command/check | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_preflight_loop.py tests/test_segment_retry.py tests/test_workspace_recovery.py` | 70 passed in 31.06 seconds. |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 1447 passed, 15 skipped in 148.19 seconds; no parallel execution. |
| `.venv/Scripts/python.exe -m compileall src docs/instruction/_manual/support` | Passed. |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | Passed, 366 tracked files; untracked documentation excluded. |
| `git diff --check` / `git diff --stat` / `git status --short` | No tracked diff; only `docs/instruction/` untracked. |
| `git diff --exit-code -- src openspec` | No changes. |
| Artifact checks | UTF-8, trailing whitespace and local links checked across seven Markdown files; no DICOM in the manual folder. |

This iteration added the Japanese/English investigation and diagnostic script, and linked the findings from README and both initial verification records. Real tools, real data and repaired behavior remain unverified.
