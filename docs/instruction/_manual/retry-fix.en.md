# Repair of downstream continuation after retry

2026-09-24. Branch `codex/gui-manual-research`. [日本語](retry-fix.ja.md).

The user explicitly requested repair of the defect documented in the [investigation](retry-state-investigation.en.md).

- Successful PHITS execution in existing-case mode now reinspects recovery evidence and replaces stale missing-output explanations.
- Fully validated v4/v5 segment evidence can authorize recovery before the first Sumtally generation. Input/output hashes, preparation bindings, retained results and parent-attempt validation remain required. Older schemas retain the additional downstream-summary digest requirement.
- Evidence-validation ValueError/OSError failures produce an invalid recovery inspection.

After retry, restore the CT2PHITS workspace handoff if required and review the downstream sequence offered by Create DICOM RT Dose. Ordinary new-case buttons remain disabled in existing-case mode. Execution-time reinspection and preservation of conflicting downstream artifacts remain in place.

## Changed files

- `src/dicomxphits/gui.py`: reinspection after PHITS success.
- `src/dicomxphits/workspace_recovery.py`: recovery using fully validated v4/v5 evidence.
- `tests/test_workspace_recovery.py`: eight cases covering first completion, retry, changed outputs/preparation evidence and damaged history.
- `tests/test_gui_retry_recovery.py`: hidden Tk regression covering STOP, existing-case inspection, selective retry, refreshed labels, required handoff selection and fake downstream dispatch.

The hidden GUI test uses a fake tool profile and external runners. It verifies that the real recovery coordinator dispatches only the four downstream stages, from Sumtally Generate through RTDOSE Run. It does not verify real downstream output creation, dose or DICOM correctness. An audit hook prohibits external process launches.

## Validation

```text
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_retry_recovery.py tests/test_workspace_recovery.py tests/test_segment_retry.py
```

77 passed in 42.51 seconds, with no failures introduced by the patch or new tests.

The full public suite, `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`, also passed: 1456 passed, 15 skipped in 160.44 seconds. The four repair files are saved in local commit `566ca04`. No push or PR creation was performed. Manual preparation materials remain untracked. The approved repair and validation are complete; no further changes are being made.

Using `.venv/Scripts/python.exe`, `-m compileall src tests/test_gui_retry_recovery.py`, `tools/verify_public_tree.py` and `git diff --check` also passed. The public-tree audit covered 366 tracked files; new untracked documentation and the new test were inspected separately.

The user's running ten-thread GUI, real data and real tools were neither operated nor tested. Runtime changes are limited to this repair; physics, DICOM semantics and public specifications are unchanged. This restores documented behavior, so no new OpenSpec proposal was created.

The earlier investigation and `support/investigate_retry_state.py` preserve evidence from baseline `4ad7a1e`. That script asserts the old defect; use the new regression test above to verify repaired behavior.

The post-commit public-tree audit also passed for 367 tracked files. Final `git diff --check` and `git diff --stat` were clean; `git status --short` showed only untracked `docs/instruction/`.

## PR review and merge

Update: after GitHub sign-in, the remote `codex/gui-manual-research` branch was deleted through the PR's Delete branch action on 2026-09-24; Restore branch confirmed completion. The pending-deletion statement below records the earlier post-merge state.

After user authorization, the GitHub plugin published commit `f8a1f3389ff8472dc0eb068ea4085d21162adbd6` with the identical tree and created [PR #83](https://github.com/inata169/dicomxphits/pull/83). Codex reviewed that commit and reported no major issues, with no actionable findings. Public CI passed. The PR merged without further corrections on 2026-09-24 as `f3750ed64266618f5f53d81539ecbd6cac23d755`. Remote branch deletion remains pending because the plugin lacks that operation and the browser is signed out. The local checkout and running GUI were not changed.
