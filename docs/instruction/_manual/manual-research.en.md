# GUI manual research and proposed contents

Research date: 2026-09-24. Baseline: v1.1.0 GUI at `main` commit `4ad7a1e`.
This is a preparatory research document, not a completed or operationally verified user manual.
Japanese version: [manual-research.ja.md](manual-research.ja.md).

See the subsequent [verification record](gui-verification.en.md) for synthetic GUI checks and 19 screenshots. The material below records the initial research state.

## Findings

The manual needs separate chapters for normal operation, stopping, retry, downstream recovery, and folder management.
Although the GUI has five pages, continuation depends on where the workflow stopped.
Simply translating the existing guide would leave preparation cancellation, segment stopping, incomplete-segment retry, and relative-error presentation insufficiently explained.

Version 1.1.0 is an experimental education-and-research release. Stable operation across real external-tool workflows has not been established.
Its scope is authorized non-patient phantoms and fixed-field 3D-CRT, excluding clinical use, patient QA, IMRT, dynamic MLC, and VMAT.

## Shared Japanese/English chapter structure

| Priority | Chapter | Required explanation |
| --- | --- | --- |
| Essential | 1. Introduction and version | Experimental status, supported scope, fixed 6 MV research model, aperture boundary, validation limits |
| Essential | 2. Installation, launch, and exit | Windows/Python 3.12, cmd launcher, separately obtained tools, exit restrictions while running, version check |
| Essential | 3. Initial tool setup | Standard/Custom layout, Validate and save setup, saved settings versus case information requiring reselection |
| Essential | 4. Inputs and folders | RT Plan, CT series selection, non-patient confirmation, source versus CT2PHITS versus 3D-CRT folders |
| Essential | 5. Normal operation | CT2PHITS → Workspace → PHITS → Sumtally → RTDOSE; prerequisites, buttons, waiting states, success checks, outputs |
| Essential | 6. Reading progress | Preparation/verification versus transport, completed counts, elapsed time/ETA, Activity log, provisional versus verified results |
| Essential | 7. Stop, cancel, and exit | Cancel preparation, Stop after current segment, sending versus acceptance, pending stop, terminal state, final-segment races |
| Essential | 8. Continue after interruption | Prelaunch cancellation, verified stop, abnormal termination, post-PHITS recovery, relocation |
| Essential | 9. Folder cleanup and deletion | Manually created empty folders, incomplete/completed cases, history, locks, installation folders; preservation and process checks |
| Essential | 10. Troubleshooting | Disabled buttons, existing outputs, timeout, busy ownership, changed inputs/results, geometry/model/dose-factor rejection, blocked recovery |
| Additional features | 11. Special procedures | Existing handoff, calculation mesh, Custom layout, Structure r.err, case recovery, references to separate CLI tools |
| Essential | 12. Results, records, and support | Final .fixed.dcm, JSON/log locations, reproducible action records, sensitive information/path review before sharing |

Retain exact English button labels in the Japanese manual. Match chapter numbering, warnings, and state-dependent branches across languages.
Use a consistent pattern: situation → prerequisites → actions → expected display → failure route.

## Essential stop and continuation distinctions

| Situation | Observed behavior and required explanation |
| --- | --- |
| Before the first PHITS launch | Use `Cancel preparation`. Accepted cancellation prevents child launch. If child commitment wins, cancellation is rejected and segment stopping requires a separate request. |
| PHITS running | `Stop after current segment` is not immediate termination. Wait for `Stop pending`, then segment completion and result verification. Requests cannot be withdrawn. |
| After stop acceptance | The segment committed at acceptance may finish; it need not be the one displayed when clicked. A verified partial stop is `User stopped`; all-segment success is normal completion. |
| After a verified partial stop | Review a fresh `Run incomplete segments…` preview. Verified successes are retained; incomplete segments restart from the beginning. Partial statistical histories are not resumed. |
| GUI loss, power loss, or abnormal exit | GUI disappearance does not prove PHITS stopped. Check surviving processes, ownership, and evidence. Do not delete the lock to bypass a busy workspace. |
| PHITS completed; downstream work remains | Inspect with `Open existing case…`, then use `Create DICOM RT Dose` when eligible. Only required downstream stages run; conflicting historical outputs are preserved in `recovery_history/` after confirmation. |
| Inputs, settings, or executable changed | Do not promise selective retry. Explain new-workspace preparation and recalculation when evidence rejects reuse. |
| Moved to another PC/path | Downstream recovery from verified PHITS results and selective retry of incomplete PHITS have distinct eligibility conditions. Relocation does not guarantee both. |

Sumtally requires verified completion of all active segments. Partial-stop results are not authorized for partial aggregation.
The GUI rejects normal window closure while a stage is active. Forced termination must not be presented as ordinary STOP.

## Folder management requires separate categories

No dedicated GUI action for deleting arbitrary user folders was found.
`Start new case` changes GUI state without deleting existing files.

| Folder or artifact | Documentation approach |
| --- | --- |
| Manually created empty CT2PHITS output folder | Even an empty existing folder violates the new, nonexistent output requirement. Prefer a fresh output name. Any deletion procedure needs separate target and emptiness checks. |
| Manually created 3D-CRT folder | Distinguish it from CT2PHITS: GUI Prepare checks whether the folder contains entries. Explain the new child name proposed by Browse. |
| CT2PHITS case | Frozen RT Plan, CT reference, and DATfiles support downstream work. Existence of a 3D-CRT case alone does not establish that this folder can be removed. |
| Incomplete/completed 3D-CRT case | segments, analysis, sumtally, and their bindings support retry/recovery. Partial cleanup can invalidate that evidence. |
| `.dicomxphits-execution.lock` | The file remains after clean exit. Presence or age does not establish active ownership. Deletion is not a supported busy-workspace workaround. |
| staging, `recovery_history/`, `analysis/segment_attempt_history/` | Do not manually promote retained files to official results or describe these directories as universally safe cleanup targets. |
| Installation or historical offline environment | Case deletion and uninstallation are separate. v1.1.0 has no public offline ZIP; legacy environments require the applicable dedicated instructions. |

No folder deletion or external-folder investigation was performed. Future deletion-screen verification should use empty synthetic cases.

## Special procedures

- Calculation mesh: Calculation config applies during new workspace preparation, not as an edit to an existing calculation.
- Live Isocenter r.err: a provisional single-voxel statistical relative error. Zero remaining batches or a small error does not prove completion or acceptance. Explain Unavailable states.
- Post-completion Structure r.err: a separate Sumtally-page feature with explicit RTSTRUCT and unique ROINumber selection. Explain the fixed dose threshold, voxel counts, mean/median/P95, and zero-error exclusion. It is not clinical dose error or convergence evidence.
- Retained Sumtally relative-error recovery: reference the evidence-bound dedicated procedure; do not recommend copying staging files manually.
- Phantom CT water replacement and GPR comparison: separate CLI workflows outside the five GUI pages; link to their documentation.
- Manual `batch.out` edits: not equivalent to the GUI STOP guarantee. Mutable control/observation content does not prove safe stopping or completion. Keep this outside the standard procedure.
- RTDOSE meaning: explain the final coordinate-corrected output, GY/PLAN, fraction-count handling, and research-model limits using existing specifications.

## Items to resolve or disclose before authoring

1. **Guide version and coverage:** `docs/gui-user-guide.md` still says v1.0.x and lacks newer operations. Identify v1.1.0 and the research baseline in the new manual.
2. **Conflicting retry-binding descriptions:** Evidence and eligibility in `docs/incomplete-segment-execution.md` describes hashing the entire PHITS installation tree. The current `phits-preflight-control` specification and `_selected_executable_evidence` in `segment_retry.py` describe `selected_executable` scope. This investigation records the discrepancy without changing existing documentation, specifications, or implementation.
3. **Exact post-restart click sequences:** downstream recovery and incomplete retry have separate GUI conditions. Verify buttons and return paths with synthetic workspaces for each state before finalizing illustrated procedures.
4. **Meaning of manually created folders:** empty folders, calculation cases, and manually installed software are classified separately. No actual deletion target has been specified.
5. **Screenshots and operational verification:** this was static source/specification/document review. Current GUI screenshots, real PHITS/DICOM execution, forced termination, deletion, and real continuation were not tested. Illustrations should use synthetic examples.

Do not present the future manual as operationally verified while these items remain unresolved.

## Principal sources

- [Existing GUI guide](../../gui-user-guide.md), [v1.1.0 release notes](../../release-notes-v1.1.0.md)
- [Segment stop](../../segment-boundary-stop.md), [Incomplete retry (discrepancy above)](../../incomplete-segment-execution.md)
- [GUI implementation](../../../src/dicomxphits/gui.py), [Retry bindings](../../../src/dicomxphits/segment_retry.py), [Output protection](../../../src/dicomxphits/safe_output.py)
- [Preflight/cancellation specification](../../../openspec/specs/phits-preflight-control/spec.md), [Downstream recovery specification](../../../openspec/specs/portable-workspace-recovery/spec.md)
- [Live observation specification](../../../openspec/specs/phits-live-observation/spec.md), [Structure evaluation specification](../../../openspec/specs/post-completion-structure-relative-error/spec.md)
- [Calculation configuration](../../calculation-configuration.md), [CT water replacement](../../phantom-ct-water-replacement.md), [Offline environment documentation](../../windows-offline-installation.ja.md)

## Validation record for these research documents

- Only this document and its Japanese counterpart were added. Branch: `codex/gui-manual-research`. Runtime and public specifications are unchanged; no commit or PR was created.
- Python checks of 15 links per language, UTF-8, and trailing whitespace: passed.
- `python -m compileall src`: passed.
- `python tools/verify_public_tree.py`: passed for 366 existing tracked files; the new untracked documents were outside that audit.
- `git diff --check`, `git diff --stat`, and `git status --short`: performed. Ordinary diff was empty because the additions are untracked. Each addition also passed `git diff --no-index --check -- NUL <file>` without whitespace errors. Two files were added.
- `python -m pytest -q -p no:cacheprovider`: unavailable because system Python lacks pytest.
- The equivalent `.venv` invocation was interrupted after repeated temporary-directory permission errors. A diagnostic `-x` run returned 14 passed / 1 error (PermissionError).
- After permission was granted, `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` returned **1446 passed / 15 skipped / 1 failed**.
- Failure: `tests/test_structure_relative_error.py::test_retained_large_sources_use_metadata_without_rehashing`. Updating the file did not raise the expected `StructureRelativeErrorUnavailable`. The cause and any causal relationship to these documentation additions were not established. No implementation changes or weakened tests were introduced.
- Stopping outcome: research saved. The operational manual, screen verification, resolution of the documentation discrepancy, and an all-green validation result remain incomplete.
