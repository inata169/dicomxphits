# Development handoff — 2026-09-09: PHITS observation preparation

## Current checkpoint

This document supersedes the morning prompt in
[the earlier segment-progress handoff](development-handoff-2026-09-09-phits-segment-progress.md).
Do not repeat its old PR #60 correction or merge instructions.

- Branch: `feature/add-phits-live-observation-proposal`.
- Implementation checkpoint: `6fa851c15021aba3bce9d9f2243528d2f92acc91`.
- At handoff preparation, the branch was clean and synchronized with origin.
  This handoff is a subsequent documentation-only change; recheck status before work.
- [PR #63](https://github.com/inata169/dicomxphits/pull/63) is OPEN and Draft.
- Main checkpoint: `d8ea0d3bd9608913f6acbafc033399a986974619`.
- Tags remain `v1.0.0`, `v1.0.1`, `v1.0.2`, and `v1.0.3`.
- Do not merge PR #63, delete its branch, or describe stage 4 as complete.

## Completed stages and today's sequence

| Stage | Outcome |
| --- | --- |
| 1: segment progress and completion evidence | PR #60 merged as `f7dfbac`; the old relative-root blocker was fixed in `adfbb0d`. |
| 2: execute incomplete segments | PR #61 merged as `9a4e0367af2717eccafa5b8eb402a8a87603d8b9`; feature branch deleted. |
| 3: stop after the current segment | PR #62 merged as `d8ea0d3bd9608913f6acbafc033399a986974619`; feature branch deleted. |
| 4a: read-only batch/error observation | Proposal approved; production implementation paused at evidence prerequisite 2.1. Synthetic verification kit prepared in PR #63. |
| 4b: batch-boundary and immediate stopping | Not implemented or authorized by stage 4a. |
| 5: additional history | Not started; requires a separate proposal and evidence about PHITS continuation/statistics. |

Stage 2 retains only revalidated completion evidence, rejects changed inputs or
outputs, restarts incomplete segments from scratch, and excludes duplicate
execution through ownership evidence. Legacy workspaces without the required
history are not automatically rescued. Partial completion never unlocks Sumtally.

Stage 3 adds an explicit request to stop after the current segment finishes and
is validated. Sending, acknowledged stop-pending, user-stopped, failure, and
complete success are distinct. It does not kill PHITS or stop within a batch.
Remaining work uses stage 2. The last segment completing takes precedence as
success; a failing current segment is not reported as a successful user stop.

PR #62 had two verified review-driven corrections:

1. `104bc38`: bind stop acknowledgement to a non-retained segment produced by
   the current invocation, within its execution interval.
2. `33caa55`: reject current-invocation execution after acknowledgement and
   incompatible active segments, including a null acknowledged boundary.

Its specification was promoted and archived in `4f82a22`, with the final
correction updating the archived tasks. Final local validation was 1078 passed,
10 skipped; public audit 302 files; OpenSpec strict 15 items. CI runs #553 and
#554 passed. Do not claim an independent approval of the final correction;
closeout used verified regression tests and explicit human merge authority.

## The old CI failure email

[Run 34313510965 (#538)](https://github.com/inata169/dicomxphits/actions/runs/34313510965)
and its Attempt #2 tested the old PR #61 commit `1fb8a1f`, not the current head.
The linked-log regression resolved a path outside the workspace too early,
raising `ValueError` instead of reaching the existing unsafe-path rejection.
It was corrected in `86f7f71`; `582343b` subsequently corrected canonical
`libpath.inp` handling. Final PR #61 CI #544/#545 and main CI #546 passed.
Re-running an old run keeps its original commit; its red history is not proof
that a later fix failed. Preserve that history rather than deleting it.

## Active stage 4a: what exists and what does not

Authoritative working documents:

- [Proposal](../openspec/changes/archive/2026-09-10-add-phits-live-observation/proposal.md)
- [Design](../openspec/changes/archive/2026-09-10-add-phits-live-observation/design.md)
- [Tasks and validation history](../openspec/changes/archive/2026-09-10-add-phits-live-observation/tasks.md)
- [Verification plan](../openspec/changes/archive/2026-09-10-add-phits-live-observation/verification-plan.md)
- [Probe instructions](../tools/phits_observation_probe/README.md)

Commits: `326a8cd` proposal; `1bd46e9` approval/evidence prerequisite;
`621d625` verification plan; `6fa851c` synthetic input and bounded collector.

The human approved the proposal and implementation subject to the evidence
prerequisite, then separately approved the verification plan and preparation of
the input/collector **without a real PHITS launch**. No production observer,
parser, sidecar writer, or GUI observation display has been implemented.
`src/` and accepted `openspec/specs/` are unchanged by PR #63 at this checkpoint.
The change must remain active, not promoted or archived.

The proposed supported target is positively identified PHITS 3.35 Windows
OpenMP. Observation is provisional, read-only, current-generation-bound, and
separate from authoritative run/completion evidence. Remaining batches and
prepared total are separate values, not a fabricated progress percentage.
Error display is for the matching generated 3D dose/error pair only, with
coverage and per-cell median/maximum; it does not provide convergence decisions.
Malformed, mismatched, unsafe, stale, or unsupported data must not be guessed.
No observation result can authorize retry, stop, success, or downstream use.

### Blocking prerequisite: exact output evidence

Task 2.1 is incomplete. The official 3.35 manual's section 4.9 uses a T-Track
example captioned PHITS 3.28, not a complete 3.35 OpenMP 3D T-Deposit dose/error
pair. The remaining-batch description does not establish the entire record
grammar or paired history/restart markers. This is missing evidence, not proof
of incompatibility. The newer 3.37 HTML manual is not a substitute. Never turn
an older example into a claimed 3.35 fixture by replacing its version string.
See the active tasks for the recorded official source and assessment.

### Prepared diagnostic kit (not real-tool verification)

- `tools/phits_observation_probe/observation-probe.inp`: authored synthetic
  1 MeV photon/water case, 27 dose cells, two OpenMP threads, 10,000 histories
  per batch and 10 batches. Real PHITS input acceptance is unverified.
- `tools/phits_observation_probe/collect.py`: check-only by default; execution
  requires an explicit private plan digest. Checks exact paths and artifact
  digests, rejects existing destinations, and preserves ownership while
  collecting bounded output. No automatic kill, restart, or retry.
- `tools/phits_observation_probe/README.md`: private-plan schema, commands,
  limitations, and approval gates.
- `tests/test_phits_observation_probe.py`: fake files and temporary Python
  children test limits, stream draining, ownership, and execution guards.

The diagnostic sampling interval is 100 ms, not the proposed production polling
interval. The shared evidence budget is 100 MiB with a reserved final report;
the ten-minute warning does not kill the child. Fast completion without enough
live observations is inconclusive, not permission to increase the run. Natural
exit or collector exit code zero alone does not establish the required format.
Use the verification plan's acceptance matrix to assess the evidence.

No installed PHITS distribution, private workspace, or real output has been
inspected. No installation/scratch paths or private plan have been finalized.
No real PHITS run or interactive desktop GUI validation has occurred.

## Verified checkpoint before this handoff

At `6fa851c`, using the repository virtual environment and synthetic data:

| Check | Result |
| --- | --- |
| Focused probe pytest | 16 passed, 1 skipped (symlink privilege) |
| Related probe/stop pytest before final two test additions | 47 passed, 1 skipped |
| `python -m compileall src tools/phits_observation_probe` | Passed |
| `python -m pytest -q -p no:cacheprovider --basetemp <outside-repository-temp-directory>` | 1094 passed, 11 skipped |
| `python tools/verify_public_tree.py` | 312 tracked files passed |
| `openspec.cmd validate --all --strict` | 16 items passed |
| Git diff checks and collector CLI help | Passed |

Both operating-system jobs passed in each of the current-head CI runs:
[34327637626](https://github.com/inata169/dicomxphits/actions/runs/34327637626)
and [34327678575](https://github.com/inata169/dicomxphits/actions/runs/34327678575).
These green results validate the preparation kit and existing application, not
real PHITS format compatibility or completion of stage 4a. No independent
automated review approval is claimed for PR #63.

Handoff-only validation was repeated on 2026-09-09: focused probe tests
16 passed / 1 skipped; full pytest 1094 passed / 11 skipped (162.07 seconds);
compilation passed; public-tree audit 313 tracked files passed; OpenSpec strict
16 items passed; Git diff checks passed. The commands are the same as above,
with a fresh outside-repository temporary directory. Only this document and
the older handoff's latest-checkpoint link changed. The handoff is saved in a
local documentation commit; no push, new CI run, PR transition, merge, or
branch deletion is performed as part of this end-of-day documentation task.
The remote CI links above therefore refer to the preceding code checkpoint.

## Next-session order and approval boundaries

1. Read `AI_AGENT_RULES.md`, `AGENTS.md`, this handoff, the active change, and
   probe instructions. Reconfirm root, branch, status, history, remote, tags,
   PR #63 and its head-specific CI. Preserve unrelated edits.
2. Report the missing evidence. Do not discover installations or enumerate
   old workspaces. Resolve an exact installation path through a single concrete
   human yes/no proposal before any scoped external inspection.
3. With separate authorization, select fresh external scratch destinations and
   prepare a private frozen plan with actual artifact digests. Check-only is
   not permission to inspect guessed paths; do not store the populated plan in Git.
4. Obtain fresh approval for the exact single real-PHITS execution, identifying
   executable, destinations, input, hashes, resource limits and evidence policy.
   Today's preparation approval does not authorize that launch.
5. Assess the verification-plan matrix. Preserve private raw evidence outside
   Git. If evidence is incomplete, stop and report; no automatic rerun, larger
   history count, stop experiment, or format guess.
6. Only after task 2.1 is satisfied, continue the approved production observer
   work. Run focused and full checks; promote/archive only when all required
   acceptance criteria are met. Ready/merge requires human direction.

Always preserve fixed 6 MV/3D-CRT physics, geometry, DICOM semantics, MU and dose
conversion. Do not touch failed legacy workspaces or residual staging; do not
run Sumtally on partial, stopped, running, or unverified results. Additional
stopping modes and additional history remain separate future decisions.

## 次回の朝一プロンプト

> 前回の続きです。まず AI_AGENT_RULES.md と AGENTS.md を読み、
> docs/development-handoff-2026-09-09-phits-observation-preparation.md と、
> openspec/changes/add-phits-live-observation/ の提案・設計・tasks・検証計画、
> tools/phits_observation_probe/README.md を確認してください。
> Git の branch/status/history/remote/tags と PR #63 の現在の head・CI を確認し、
> 現状を報告してください。段階1〜3はマージ済み、段階4aは提案承認済みですが、
> task 2.1 の実形式の証拠不足で本番実装を停止しています。入力とcollectorは準備済みです。
> 実PHITSの起動、インストール探索、外部workspaceの閲覧・変更はまだ承認していません。
> 最初は現状確認と、次に必要な最小の承認を一つだけ yes/no で提案するところまでにしてください。
> 実行計画の準備承認と実PHITSの一回起動承認を分け、承認を推測しないでください。
> PR #63を勝手にmerge・branch削除・archiveせず、旧引き継ぎ書の朝一指示も再実行しないでください。
