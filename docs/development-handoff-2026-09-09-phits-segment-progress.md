# Development handoff - 2026-09-09 PHITS segment progress

This handoff records the repository state at the end of the 2026-09-09
development session. `dicomxphits` remains education and research software for
the documented fixed-field 3D-CRT workflow. Nothing in this work establishes
clinical validity, commissioning, patient QA, vendor certification, or general
dose accuracy.

No real path, UID, DICOM object, PHITS or Sumtally output, RTDOSE, GPR result,
or external-workspace artifact is recorded here or committed with this work.

## Repository and pull-request state

Pull request #59 was reviewed and normally merged into `main` on 2026-09-09 as
merge commit `80200d8`. Its documentation branch was deleted. That pull
request changed only the earlier phantom-CT handoff and did not change runtime
code, physics, DICOM semantics, or an OpenSpec contract.

Development then moved to branch `feature/add-segment-progress-reporting` and
pull request #60, "Add PHITS segment progress reporting". The implementation
revision currently under review is `793cd83`. Before this handoff document was
added, the local branch was clean and matched
`origin/feature/add-segment-progress-reporting`.

PR #60 remains open and unmerged. GitHub public CI run #532 for `793cd83`
completed successfully. The Codex review for that revision also completed,
but opened one new unresolved P2 merge-blocking thread against
`src/dicomxphits/prepare_sumtally.py`:

> Normalize relative roots in legacy v2 evidence.

The feature branch must not be merged or deleted until that confirmed defect
is corrected, the required checks pass, a fresh Codex review reports no
merge-blocking defect, and GitHub CI succeeds. Do not force-push or modify a
tag.

## Work completed today

The primary user selected future-feature item 1, calculation progress and
estimated completion time, as the first implementation stage. An OpenSpec
proposal was created and approved before implementation. Its accepted deltas
are now promoted into:

- `openspec/specs/phits-segment-runtime/spec.md`; and
- `openspec/specs/guided-gui-workflow/spec.md`.

The completed change is archived at
`openspec/changes/archive/2026-09-09-add-segment-progress-reporting/`, with all
tasks checked. Strict validation of the resulting OpenSpec tree passes.

The implementation adds an atomic version-3
`analysis/segment_execution_summary.json` record. Direct PHITS segment
execution records one invocation identifier, current and completed segment
states, UTC timestamps, monotonic elapsed durations, per-segment durations,
manifest binding, output SHA-256 bindings, PHITS return codes, and clean
geometry-diagnostic evidence at the required segment boundaries. A required
progress-write failure stops execution before another segment starts.

The GUI displays validated completed/total active segments, the current active
and manifest ordinals, a bounded segment identifier, elapsed time, approximate
remaining time, approximate finish time, and explicit completed, interrupted,
or failed states. Remaining-time estimates start only after one active segment
has completed successfully and use the arithmetic mean of validated completed
segment durations. The display identifies the estimate as approximate.

The GUI accepts a live progress snapshot only when it belongs to the current
GUI invocation and exact selected workspace. It verifies the current manifest,
ordered segment identities, contained paths, completed output hashes, PHITS
companion-output hashes, and clean geometry evidence. Validation of an
unchanged snapshot is cached so the 250 ms Tk polling loop does not repeatedly
hash completed tallies. Terminal success receives a fresh full validation.

Existing-case terminal success uses the repository's relocation-aware
downstream validation. A safely moved workspace may therefore display
`Completed` when its rebound paths, current hashes, and geometry evidence are
still valid. Live GUI-owned progress and non-success existing records retain
the stricter exact-root rule.

Sumtally remains disabled for running, interrupted, failed, gate-failed,
malformed, stale-invocation, unknown-version, or artifact-mismatched evidence.
Generation rechecks accepted PHITS evidence after capturing its final segment
output digests, closing the previously reviewed file-replacement interval.

The new writer resolves a supplied workspace root before recording version-3
root and artifact paths. This fixes relative-root handling for new version-3
records. Successful version-3 segment evidence additionally requires a zero
PHITS return code.

The implementation and review commits are:

- `1b86bea` - propose segment progress reporting;
- `e6cf011` - implement and archive the approved progress change;
- `f49c4d3` - validate GUI evidence bindings and show manifest ordinals;
- `bb62a96` - fail closed for stale existing progress;
- `5c1bee5` - bind terminal progress and legacy evidence;
- `c4bd6d0` - recheck PHITS evidence after Sumtally digest capture;
- `10e60a1` - bind progress to current workspace evidence and require zero
  return codes;
- `e9bdd1a` - cache unchanged progress validation and resolve new workspace
  roots; and
- `793cd83` - accept relocation-aware valid progress for existing cases.

The seventh correction round was explicitly approved by the primary user and
was limited to the relocated-existing-workspace display defect. No optional
refactor or unrelated feature was added.

## Current merge blocker

The unresolved review finding concerns a legacy version-2 success record made
by the earlier CLI when the caller supplied a relative `--workspace-root`.
That writer could retain the relative root text while recording absolute
artifact paths. The new all-schema validation uses the recorded root to bound
those paths and consequently rejects this otherwise same-workspace version-2
evidence.

Resolving workspace roots in the new version-3 writer does not repair old
version-2 records. This conflicts with the accepted OpenSpec requirement that
a valid version-2 terminal success remain usable under its established
manifest, output-digest, and clean-geometry checks.

The next correction must be limited to this case. It should normalize or
otherwise safely recognize a version-2 relative root only when the absolute
recorded artifacts can be proven to belong to the currently selected
same workspace. It must continue to reject a different workspace, escaping
paths, missing or changed artifacts, digest mismatches, malformed evidence,
and unclean geometry. It must not rewrite the stored version-2 summary.

No eighth correction round has been performed in this session. Because the
repository's normal correction limit was already exceeded once under explicit
human approval, the next session must obtain or carry explicit approval for
this one additional bounded correction before editing code.

## Validation completed for revision 793cd83

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider \
  tests/test_gui.py tests/test_workspace_recovery.py \
  --basetemp <outside-repository-temp-directory>
149 passed, 1 skipped

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider \
  tests/test_gui.py tests/test_manual_smoke_workflow.py \
  tests/test_prepare_sumtally.py tests/test_run_segments.py \
  tests/test_workspace_recovery.py \
  --basetemp <outside-repository-temp-directory>
285 passed, 2 skipped

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider \
  --basetemp <outside-repository-temp-directory>
1013 passed, 10 skipped

.venv\Scripts\python.exe -m compileall src
passed

.venv\Scripts\python.exe tools/verify_public_tree.py
passed (280 tracked files checked)

openspec.cmd validate --all --strict
13 passed, 0 failed

git diff --check
passed

GitHub public CI run #532
passed
```

The full test base directory was outside the repository because GUI safety
tests intentionally detect unexpected in-repository files.

## Work to do next

The immediate task is to close PR #60 safely:

1. Confirm the repository, branch, clean status, remotes, tags, PR head, CI,
   review summary, and unresolved review threads.
2. Read the current implementation, tests, promoted specification, and this
   handoff before editing.
3. With explicit human approval, correct only the legacy-v2 relative-root
   blocker and add focused synthetic regression coverage for acceptance of a
   provable same-workspace record and rejection of unsafe bindings.
4. Run focused checks, the related five-file suite, all public checks required
   by `AGENTS.md`, and strict OpenSpec validation.
5. Commit and normally push without rewriting history. Reply to and resolve the
   review thread through the GitHub plugin, update the PR description, and run
   `@codex review` again.
6. Merge only when the new head has successful GitHub CI and no confirmed
   merge-blocking defect. Normally merge PR #60, delete its remote and local
   feature branch, switch to `main`, fetch with pruning, and confirm that local
   `main` is clean and matches `origin/main`.
7. Update this handoff's repository-state section if the final closeout differs
   from the state recorded above.

After PR #60 is closed, the primary user wants future-feature items 1 through
4. Item 1 is the active progress work described here. Items 2 through 4 have
not been approved as requirements, have no OpenSpec changes, and have no
implementation work yet. The recommended sequence is:

1. **Safe PHITS stopping (feature item 2).** Define a separate OpenSpec change
   for cooperative stopping at reviewed boundaries, durable
   `stopped_by_user` evidence, pending/running/completed distinctions, and a
   fail-closed Sumtally gate. Exact meanings of batch-end, segment-end, and
   immediate stop require human approval before implementation.
2. **Rerun only incomplete segments (feature item 4).** Build on the durable
   progress and stopping states. Require unchanged inputs and manifest,
   identify only non-successful segments, preserve verified completed results,
   record the rerun transition, and prevent duplicate Sumtally inclusion.
3. **Additional-history restart (feature item 3).** Treat this as the most
   physics-sensitive of the four. It requires a separate design for PHITS
   version and model identity, tally and transport settings, CT/RTPLAN/manifest
   hashes, calibration binding, random-seed history and non-overlap, statistical
   combination, and provenance. Do not assume that ordinary incomplete-segment
   rerun supplies safe statistical accumulation.

Each stage must have its own proposal, delta specifications, human approval,
implementation, focused and full validation, reviewable pull request, and
OpenSpec promotion/archive cleanup. Do not begin items 2, 3, or 4 merely because
item 1 merges.

The earlier GUI retry-usability observations also remain deferred: missing
public PHITS output can disable both inspection and rerun, standard mode does
not expose a retry output path, overwrite wording does not explain the
`phits.inp` fail-closed refusal, validated CT2PHITS handoff reuse is hidden in
advanced controls, and the UI does not clearly separate PHITS-only rerun from
preparing a new workspace after runtime changes. No code, OpenSpec change, or
Issue was created for these observations.

## Protected and unverified state

- No real PHITS, Sumtally, DICOM, RTDOSE, or GPR workflow was run for PR #60.
- The separately approved external 3D-CRT workflow and all of its identifiers,
  inputs, outputs, and comparison artifacts remain outside the repository.
- The original failed external workspace and retained staging remain
  unresolved. Do not copy, move, delete, promote, rerun, or manually edit their
  summaries.
- Runtime physics values, beam and machine geometry, MLC and jaw shapes, dose,
  MU, absolute-dose calibration, DICOM semantics, and external-workspace
  recovery behavior are outside the next correction's scope.
- The progress feature changes the public progress/evidence contract as
  approved in OpenSpec, but it does not change PHITS calculation parameters or
  physical modeling.

## Next-session morning prompt

Paste the following prompt at the start of the next development session:

```text
C:\Repositories\dicomxphits で前回の作業を再開してください。

最初に以下を全文読んでください。

- AGENTS.md
- AI_AGENT_RULES.md
- openspec/AGENTS.md
- docs/development-handoff-2026-09-09-phits-segment-progress.md

その後、repository root、現在のbranch、status、recent history、remote、
tagsを確認してください。既存branch・変更・実データ・外部workspaceを
削除またはresetしないでください。force-pushとtag変更は禁止です。
GitHub上の確認・コメント・review・mergeにはGitHubプラグインを使って
ください。

前回の終了状態では、mainはPR #59のmerge commit 80200d8、作業branchは
feature/add-segment-progress-reporting、PR #60はopenでした。実装revision
793cd83ではlocal full checksが1013 passed、10 skipped、関連checksが
285 passed、2 skipped、GitHub CI run #532がsuccessでした。

最新Codex reviewには、legacy v2のrelative workspace rootとabsolute
artifact pathの組み合わせを新しいdownstream検証が拒否するP2 blockerが
1件残っています。まずPR #60の現在のhead、CI、review summary、未解決
threadを再確認してください。

この確認済みP2だけを対象に、第8修正ラウンドを行うことを承認します。
same-workspaceであることを現在のmanifest、artifact path、hash、clean
geometry evidenceから証明できるlegacy v2記録だけを安全に正規化して
受け入れ、異なるworkspace、path escape、missing/changed artifact、hash
mismatch、malformed evidence、unclean geometryは引き続き拒否してください。
保存済みv2 summaryを書き換えないでください。他のrefactorや機能追加を
含めないでください。

focused tests、関連5テスト群、AGENTS.mdの全公開checks、OpenSpec strict
validationを実行してください。通常commit・通常push後、GitHubプラグイン
で指摘へ返信してthreadをresolveし、PR本文を更新し、@codex reviewを
実行してください。

新headの全checksが成功し、確認済みmerge-blocking defectがなければ、
PR #60を通常mergeし、remoteとlocalのfeature branchを削除してください。
その後mainへ戻り、fetch --pruneして、mainがorigin/mainと一致するclean
状態を確認してください。新しいblockerが出た場合は追加修正せず、人間へ
報告してください。

実PHITS、Sumtally、DICOM、RTDOSE、GPR、外部toolを実行しないでください。
元のfailed workspaceや残存stagingをコピー、移動、削除、手動昇格、
summary編集しないでください。外部workspaceの実パス、UID、DICOM、出力を
repositoryへ追加・記録・commitしないでください。

最後に、PR #60の状態、merge commit、branch削除、main/status、実施checks、
未検証事項、変更範囲を報告してください。
```
