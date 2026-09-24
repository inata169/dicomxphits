# Synthetic GUI verification

Date: 2026-09-24. Baseline: v1.1.0 at `4ad7a1e`.
Branch: `codex/gui-manual-research`. [日本語](gui-verification.ja.md).

## Outcome and scope

A subsequent [investigation](retry-state-investigation.en.md) reproduced stale state after retry and blocked downstream continuation in existing-case mode. The record below describes the initial verification; consult the investigation for resolution of those uncertainties.

An isolated GUI was used to inspect the five basic pages, preparation cancellation, segment stopping, incomplete-segment retry after GUI restart, and downstream continuation of a prepared RTDOSE case. Nineteen screenshots were saved.
The user's GUI running a ten-thread calculation was neither operated nor captured. Its settings, calculation directories, and running processes were not changed.

The product GUI, validation functions, segment controller, and recovery logic were used with Python fake runners replacing external execution.
This is not real PHITS/phits2dicom validation and does not establish dose accuracy, real stopping time, or real-calculation recovery success.

The test GUI has a distinct title and isolated initial values and settings storage; normal saved tool settings were not read.
A process audit hook rejects external process launches. Synthetic control is delivered in process; these screenshots do not verify stdin communication with real PHITS.

## Verified interactions

| Item | Action and observed result |
| --- | --- |
| Basic pages | Navigated CT2PHITS, Tool settings, Workspace, PHITS, Sumtally, and RTDOSE and inspected labels and control placement. This was not a continuous GUI execution of all five stages for a new case. |
| Prelaunch cancellation | Held a synthetic file read, clicked `Cancel preparation`, observed the sending state, then released the read. The GUI showed `Preparation cancelled; no PHITS launched`; fake runner calls were zero and Sumtally remained disabled. |
| Segment stopping | Started a two-segment synthetic case and clicked `Stop after current segment`. Observed `Stop pending`. Releasing the fake segment produced `User stopped`, 1/2 completed, one remaining; the second runner was not called. |
| Closing while active | Closing the test GUI during pending stop produced `Wait for the active stage to finish before closing the GUI.` The window remained open and the fake invocation remained active. |
| Retry after GUI restart | Closed the test GUI and started another process. Explicitly selected the same synthetic workspace using `Open existing case…`, then used PHITS → `Run incomplete segments…`. The preview retained `seg_001` and scheduled `seg_002`. Only `seg_002` was called after confirmation. |
| Retained result integrity | Compared SHA-256 and modification times for files in `seg_001`: unchanged. Terminal result was success, 2/2 completed, one retained, one newly completed; the previous stop request was not inherited. |
| Recovery rejection | The minimal stop/retry fixture lacked sufficient evidence for downstream recovery and was classified Blocked. PHITS completion alone was not treated as downstream recovery success. Evidence was not rewritten to bypass rejection. |
| Downstream RTDOSE continuation | Prepared a separate happy-path fixture through Sumtally and RTDOSE Prepare. Used `Open existing case…` → RTDOSE → `Create DICOM RT Dose`. The confirmation listed only `RTDOSE Run`; fake conversion produced Completed and the final `.fixed.dcm` path. |

The RTDOSE continuation call record was exactly `["run_rtdose"]`. The GUI action did not rerun Workspace Prepare, PHITS, or Sumtally.
Initial setup of that fixture used existing synthetic DICOM and fake Sumtally test helpers.

## Instructions to incorporate into the manual

1. **STOP is not immediate termination.** Explain `Stop pending` and `User stopped` separately and tell users to wait before closing the GUI.
2. **Preparation cancellation differs from incomplete retry.** After initial prelaunch cancellation, no runner had executed and ordinary `Run PHITS segments` became available again. After a segment stop, review `Run incomplete segments…` instead.
3. **Separate downstream inspection from incomplete retry.** The reopened stopped case showed `Invalid existing case`/`Not reusable`/`Blocked`, yet incomplete retry offered a valid preview. This does not mean every Blocked case is retryable.
4. **Do not infer reuse from a success label alone.** Downstream recovery checks its own evidence after a successful retry. Do not generalize the minimal fixture's rejection cause to real cases.
5. **Read the recovery confirmation's stage list.** A case with valid Prepare evidence required only RTDOSE Run. Other cases may need a different suffix.
6. **Classify folders by purpose.** Related tests verified CT2PHITS's new-output requirement and rejection of a nonempty workspace without overwrite permission. No empty-folder, real-case, or installation deletion was performed. Do not recommend deleting previous results merely to reuse a name.

## Screenshot index

Every image shows a synthetic test session. Windows dialogs use this PC's Japanese language, including Yes/No labels. Visible synthetic local paths are not setup examples.

| Image | Contents |
| --- | --- |
| [01](screenshots/01-case-setup.jpg) | Case setup |
| [02](screenshots/02-tool-settings.jpg) | Tool settings |
| [03](screenshots/03-workspace.jpg) | Workspace and calculation settings |
| [04](screenshots/04-phits-controls.jpg) | PHITS controls |
| [05](screenshots/05-sumtally.jpg) | Sumtally |
| [06](screenshots/06-rtdose.jpg) | RTDOSE |
| [07 — local-only / 公開対象外](screenshots/README.md) | Synthetic segment running |
| [08 — local-only / 公開対象外](screenshots/README.md) | Accepted stop pending |
| [09 — local-only / 公開対象外](screenshots/README.md) | Active-stage closure warning |
| [10 — local-only / 公開対象外](screenshots/README.md) | Stopped after 1/2 segments |
| [11 — local-only / 公開対象外](screenshots/README.md) | Stopped case reopened after GUI restart |
| [12 — local-only / 公開対象外](screenshots/README.md) | Retained/scheduled preview |
| [13 — local-only / 公開対象外](screenshots/README.md) | Incomplete retry completed |
| [14 — local-only / 公開対象外](screenshots/README.md) | Minimal fixture rejected for downstream recovery |
| [15 — local-only / 公開対象外](screenshots/README.md) | Preparation before launch |
| [16 — local-only / 公開対象外](screenshots/README.md) | Preparation cancellation completed |
| [17 — local-only / 公開対象外](screenshots/README.md) | RTDOSE recovery ready |
| [18 — local-only / 公開対象外](screenshots/README.md) | Run-only recovery confirmation |
| [19 — local-only / 公開対象外](screenshots/README.md) | Synthetic RTDOSE completed |

[Accepted STOP waiting for the current fake segment — local-only / 公開対象外](screenshots/README.md)

## Reproduction and issues encountered

Run the [session script](support/synthetic_gui_session.py) with the repository development Python environment, including pytest.
Explicitly supply a new synthetic-only directory outside the repository as `--session-root`. Only `resume` uses an existing session created by this script.

```text
python docs/instruction/_manual/support/synthetic_gui_session.py --mode layout --session-root <new-synthetic-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode stop --session-root <new-stop-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode resume --session-root <same-stop-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode cancel --session-root <new-cancel-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode recovery --session-root <new-recovery-session>
```

Create an empty `finish-synthetic-segment` file in the session root to release the `stop` mode's fake runner, or `finish-synthetic-read` to release the `cancel` mode's fake read. These are harness controls, not product STOP-file features. Waiting longer than ten minutes fails the synthetic operation.
Session-local `ui-<mode>.jsonl` records UI states; `runner-calls.json` records fake calls. These local records and synthetic outputs were not copied into the documentation directory.

- The first restart check encountered a TypeError because the test adapter's `_default_values` did not accept a path argument. Only the harness was corrected; repeating the same synthetic case succeeded.
- Because the recovery function binds its default runner at definition time, an explicit fake-runner wrapper was added and the happy path verified in a newly launched GUI. The external-process audit hook remained enabled.
- The first Computer Use capture returned another screen; it was not saved and the test window was reselected. Indexed folder-dialog actions also failed, so fresh dialog screenshots were used for coordinate actions. The real-calculation window was never selected.
- Format validation identified the capture payloads as JPEG rather than PNG. File extensions and document links were corrected to `.jpg` without changing image contents. Pillow was unavailable in the development Python environment, so all 19 files were loaded with the image-reading tool and their JPEG start/end markers checked separately.

## Checks and limitations

Focused validation returned **11 passed**:

```text
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_preflight_loop.py tests/test_manual_smoke_workflow.py tests/test_segment_retry.py::test_retry_preserves_completed_artifacts_and_creates_unique_terminal_evidence tests/test_workspace_recovery.py::test_gui_recovery_runs_only_inspected_downstream_suffix tests/test_gui.py::test_ct2phits_gui_stage_keeps_explicit_confirmation_and_new_workspace_gate tests/test_gui.py::test_existing_workspace_overwrite_detection_does_not_start_subprocess
```

Full public checks and artifact checks:

| Command/check | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 1447 passed / 15 skipped in 168.18 seconds; no parallel execution. |
| `.venv/Scripts/python.exe -m compileall src docs/instruction/_manual/support` | Passed for product source and the verification script. |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | Passed for 366 tracked files. New untracked documents were outside this audit. |
| `git diff --check`, `git diff --stat`, `git status --short` | Performed; only `docs/instruction/` is untracked, with no tracked-file diff. |
| Document/image checks | Separately checked relative links, UTF-8, trailing whitespace, and integrity of all 19 JPEGs. |
| Test-window shutdown | No `SYNTHETIC MANUAL CHECK` windows remain. |

The relative-error test that failed during initial research passed this time. Its cause was neither established nor fixed, so this does not prove the previous failure was resolved.
No commit or PR was created. Added/updated material is confined to this folder: README, Japanese/English research documents, Japanese/English verification records, the session script, and 19 screenshots.

Unverified: real PHITS stop/retry, real external-tool end-to-end execution, power loss/forced termination, real-folder deletion, dialogs on English Windows, and Structure r.err screenshots.
The pre-existing documentation discrepancy remains recorded in the [research document](manual-research.en.md); existing documentation and public specifications were not changed to resolve it.

Deliverables are verification records, screenshots, and the reproduction script. Product runtime and public specifications are unchanged. The Japanese/English operating manuals remain the next authoring phase.
