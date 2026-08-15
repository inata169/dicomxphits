# Development handoff — 2026-08-15

This handoff records the completed fixed-6-MV GUI integration, Windows offline
bundle upgrade and uninstall work, human Windows acceptance, OpenSpec cleanup,
and the stopping boundary at the end of 2026-08-15.

`dicomxphits` remains education and research software for the documented
fixed-field 3D-CRT workflow. This work does not establish clinical dose
accuracy, commissioning, patient QA, or vendor certification. Real DICOM,
PHITS output, case directories, installed runtimes, and GPR artifacts remain
outside the repository.

## Stop state

- Repository: `C:\Repositories\dicomxphits`
- Branch: `codex/integrate-safety-ui`
- Accepted implementation/specification HEAD before this handoff document:
  `915a6773fb82107f843e7bead2057760bddcbfaa`
- The branch has no configured upstream and has not been pushed under this
  branch name.
- Local working tree was clean before this handoff document was added.
- Last observed local remote-tracking refs:
  - `origin/main`: `e534be951629519cec1dfa920c3711fa74a177b8`
  - `origin/fix-offline-bundle-directory-lock`:
    `ecf474a05f3b37850b70c921de4d4c40e1c17a4d`
  - `origin/feat/safety-ui-energy-guard`:
    `af87da3cd199eb2246a6d3a711eebfc59f68e1b7`
  - `origin/fix/safety-ui-minimum-window-scroll`:
    `85a8d780425408dd1900d3e9d9837fc831242d7c`
- Pull request #38 was not merged, readied, closed, or deleted in this work.
  Its current GitHub state must be reconfirmed through the GitHub plugin in the
  next session because today's new integration commits are local only.
- Tags `v1.0.1` and `v1.0.0` remain unchanged.
- No `v1.0.2` version change, tag, GitHub release, or release asset exists.
- The unapproved
  `openspec/changes/add-rtdose-coordinate-output-choice/` proposal was not
  recreated, implemented, staged, or archived.

Do not infer current GitHub state from these local remote-tracking refs without
refreshing and checking through the GitHub plugin. Do not merge, rebase,
cherry-pick, ready, close, or delete PR #38 or the retained GUI branches without
a new explicit human decision.

## Completed integration

The integration branch is based on PR #38 exact HEAD `ecf474a` and preserves
merged PR #37 geometry, course-dose, recovery, evidence, and GUI stage-gating
behavior. The old GUI branches were not merged wholesale and were not
unreviewedly cherry-picked.

The accepted commits after `ecf474a` are:

- `0e59125` — integrate the fixed Elekta Precise nominal 6 MV safety guard,
  shared model identity, Help menu, author/version presentation, vertically
  scrollable workflow viewport, and five-page action reachability;
- `6cf05c1` — move the Windows default GUI local settings file from the
  protected source snapshot to the per-user `LOCALAPPDATA` boundary;
- `267e90b` — bind protected runtime identity to bundle root plus verified
  manifest content and add verified exact-installation uninstallation;
- `becbb3b` — record the first offline bundle validation;
- `77c662d` — prevent the elevated-stage/finalizer descendant-wait deadlock by
  waiting for only the direct elevated process;
- `adccdea` — record the corrected bundle validation;
- `212b7e4` — acquire Windows delete-sharing handles for every exact uninstall
  target before mutation so a directory lock refuses all deletion;
- `d2e000b` — record the corrected uninstall-lock artifact validation; and
- `915a677` — promote and archive the accepted safety-UI and offline-upgrade
  OpenSpec changes.

Public physics, spectrum bytes, aperture limits, gantry direction, coordinate
mapping, DICOM meaning, MU, Sumtally normalization, PLAN fraction scaling,
package version metadata, and tags were not changed by the offline upgrade and
uninstall correction.

## Human Windows acceptance

The primary user performed the Windows operations. The agent did not execute
or read real PHITS, Sumtally, phits2dicom, GPR, real DICOM, or calculation
results.

Human-reported accepted behavior includes:

- offline installation completed successfully;
- the GUI launched from the offline installation;
- fixed Elekta Precise 6 MV model and nominal-energy presentation appeared;
- `Help -> Web site`, version, and `Hiroki Inata (inata169)` appeared;
- minimum-window vertical scrolling worked;
- primary actions on all five workflow pages were reachable;
- the Activity log used the accepted compact presentation;
- CT2PHITS, Workspace, PHITS, Sumtally, and RTDOSE completed in the human
  external-tool workflow; and
- the user separately reported no abnormal dose distribution or absolute dose
  in GPR-comparing.

The external-tool result is human-reported research evidence, not automated
repository validation or clinical acceptance.

## Uninstall acceptance and exact root cause

The first verified uninstall implementation exposed a process-lifetime
deadlock. `Start-Process -Wait` waited for the detached descendant finalizer,
while that finalizer waited for the verified parent to release bundle locks.
Commit `77c662d` replaced that behavior with the direct process object's
`WaitForExit()`.

The corrected uninstall then exposed a separate Windows directory-sharing
case. A Windows Terminal window had originally been opened with the extracted
installation as its startup directory. Changing the child PowerShell prompt to
the parent directory did not necessarily release the parent Windows Terminal's
directory handle. The first recursive implementation could delete the bundle
contents and then fail to remove the held root.

Commit `212b7e4` adds a deletion preflight. Before any mutation, the elevated
finalizer opens every existing exact target with `DELETE` access and
read/write/delete sharing and retains the handles through exact target
removal. If another handle does not permit deletion, the uninstall stops before
deleting anything and reports Windows error 32.

Human acceptance proved both paths:

1. With the original Windows Terminal still retaining the extraction root,
   uninstallation stopped before deletion. The bundle remained complete with
   its manifest and all top-level content.
2. After closing that entire terminal window and starting a new PowerShell
   outside the extraction root, verified uninstallation succeeded.
3. The exact extracted bundle, matching protected runtime, receipt, Windows
   Installer log, successful cleanup staging, and the earlier failed cleanup
   staging were confirmed absent.
4. Case folders, external tools, and per-user GUI settings were outside the
   deletion set and were preserved.

The practical user rule is: close the entire terminal or Explorer process that
was opened in the installation directory. Running `Set-Location` in that same
terminal may not release the parent terminal host's directory handle. Start a
new PowerShell outside the installation directory before running its absolute
`uninstall_offline.cmd` path.

## Final validated offline artifact

The ignored local artifact produced from accepted HEAD `915a677` is:

```text
C:\Repositories\dicomxphits\dist\dicomxphits-offline-win64-1.0.1.zip
SHA-256 24da1da9f7ec383f225618f0f079826efa8c6c33ab5f9d734492029024add720
size 36,905,202 bytes
manifest source HEAD 915a6773fb82107f843e7bead2057760bddcbfaa
ZIP files 231
manifest file records 229
public source files 221
```

Every ZIP file was reopened in memory and checked for duplicate names, exact
size, SHA-256, manifest membership, and exact `SHA256SUMS.txt` binding. Official
CPython 3.12.10, Tcl/Tk, and NuGet signature validation passed; the five pinned
Windows wheels were downloaded with hashes and validated.

The human installed and uninstalled the immediately preceding runtime-identical
artifact at `d2e000b`. Commit `915a677` changes only accepted OpenSpec
promotion/archive content, so the final ZIP was not installed again. Rebuild
the ZIP after any future version or source change; do not treat this ignored
file as a published GitHub release asset.

## Automated validation

Validation for the final runtime diff and accepted specification state:

- focused offline bundle/installer/uninstaller suite:
  `85 passed, 1 skipped`;
- `python -m compileall src`: passed;
- full repository suite using a repository-external Windows base directory:
  `827 passed, 11 skipped`;
- `python tools/verify_public_tree.py`: passed, 221 tracked files;
- current OpenSpec tree: `10 passed, 0 failed` under strict validation;
- the newly archived
  `2026-08-15-integrate-safety-ui` and
  `2026-08-15-support-offline-bundle-upgrades` changes: passed;
- `git diff --check`: passed; and
- final ZIP manifest, inventory, size, and hashes: passed.

`openspec validate --archived --strict` reports `18 passed, 1 failed` because
the pre-existing archive
`2026-08-07-add-windows-offline-installer` contains one historical incomplete
task (24/25). The two 2026-08-15 archives pass. Do not silently edit the older
accepted archive merely to make the aggregate count green; first determine its
historical intent and obtain a separate human decision if it ever becomes
necessary.

Several invalid test invocations were diagnosed and discarded during the day:
the default user temp root had an inaccessible historical pytest directory, a
repository-internal base directory correctly triggered the public-workspace
safety boundary, and `C:\tmp` did not exist (`C:\temp` does). The final focused
and full results above used clean, unique, repository-external base directories,
and every base directory created for the final runs was removed.

## OpenSpec completion

The accepted changes were promoted and archived with the installed OpenSpec
CLI:

- `openspec/changes/archive/2026-08-15-integrate-safety-ui/`; and
- `openspec/changes/archive/2026-08-15-support-offline-bundle-upgrades/`.

The offline upgrade and verified uninstall contract is now in:

- `openspec/specs/windows-offline-installation/spec.md`.

The accepted fixed-6-MV and GUI requirements were already synchronized with:

- `openspec/specs/fixed-6mv-beam-model-safety/spec.md`; and
- `openspec/specs/guided-gui-workflow/spec.md`.

No active 2026-08-15 OpenSpec change remains.

## Remaining work and stopping boundary

Development stops here. Do not deepen runtime work in this session.

Remaining decisions for a future session are external workflow and release
decisions rather than accepted runtime defects:

1. protect the local integration commits by pushing
   `codex/integrate-safety-ui` to `origin`;
2. reconfirm PR #38 and its exact-head CI through the GitHub plugin;
3. decide whether PR #38 should merge first and how the integration work should
   be presented for review;
4. create or update a reviewable draft pull request only after explicit human
   approval;
5. decide whether to change the package version to `1.0.2`; and
6. only after merge and explicit release approval, create the tag, final
   release ZIP, checksums, and GitHub release.

Do not modify tags or publish `v1.0.2` merely because human acceptance passed.
Do not merge, rebase, cherry-pick, force-push, delete branches, or alter PR #38
without a new yes/no decision. Do not rerun real external tools or load real
DICOM/results for repository work.

## Next-development morning prompt

Copy the following prompt into the first task of the next development session:

```text
C:\Repositories\dicomxphits の2026-08-15からの継続です。
このPCはWindows 11です。

最初に次のファイルを全文読んでください。

- AGENTS.md
- AI_AGENT_RULES.md
- openspec/AGENTS.md
- openspec/project.md
- docs/development-handoff-2026-08-15.md

最初にread-onlyで次を確認してください。

git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git log -15 --oneline --decorate --graph
git remote -v
git branch -a -vv
git tag --sort=-creatordate

引き継ぎ書作成前のaccepted implementation/specification HEADは
915a6773fb82107f843e7bead2057760bddcbfaaです。
引き継ぎ書のcommitにより現在HEADが1つ進んでいる可能性があります。
現在branchはcodex/integrate-safety-ui、作業treeはcleanであることを期待します。
このbranchにはまだupstreamがない状態でした。

最終ローカルartifactは次です。

C:\Repositories\dicomxphits\dist\dicomxphits-offline-win64-1.0.1.zip
SHA-256 24da1da9f7ec383f225618f0f079826efa8c6c33ab5f9d734492029024add720
manifest source HEAD 915a6773fb82107f843e7bead2057760bddcbfaa

これはignored local artifactで、GitHub release assetではありません。
v1.0.2へのversion変更、tag、releaseはまだ行っていません。
tags v1.0.1、v1.0.0を変更しないでください。

次の2つのOpenSpec changeは受け入れ、promotion、archive済みです。

- openspec/changes/archive/2026-08-15-integrate-safety-ui/
- openspec/changes/archive/2026-08-15-support-offline-bundle-upgrades/

openspec validate --archived --strictの全体結果には、今回と無関係な既存
2026-08-07-add-windows-offline-installerの未完了task 1件があります。
今回の2 archiveは合格済みです。古いarchiveを無断修正しないでください。

人間によるWindows受け入れは完了しました。

- offline install成功
- GUI起動成功
- 6 MV固定表示、Help、Web site、Hiroki Inata、version表示成功
- 最小window scrollと5ページのprimary action到達性成功
- CT2PHITS、Workspace、PHITS、Sumtally、RTDOSE成功
- 人間がGPR-comparingで線量分布・絶対線量に異常なしと報告
- verified uninstall成功
- bundle、対応runtime、receipt、log、cleanup stagingの残存なし

エージェントは実PHITS、Sumtally、phits2dicom、GPR、実DICOM、実結果を
実行・読み込みしないでください。

GitHub操作にはGitHubプラグインを使用し、ghは使用しないでください。
最初にGitHubをread-only確認し、PR #38の現在状態、exact HEAD CI、
origin/main、関連branch、codex/integrate-safety-uiが未pushかを確認してください。
PR #38のmerge、ready化、close、branch削除は行わないでください。
2つの古いGUI branchもmerge、rebase、cherry-pick、削除しないでください。

最初の作業範囲は、GitHubとlocal stateの再確認、および次の安全な公開順序の
具体案提示までです。推奨案は、まずlocal integration branchをoriginへbackupし、
PR #38とのstacked reviewまたはPR #38 merge後のreview方法を比較して、1案だけを
提示することです。push、PR作成、merge、version 1.0.2変更、tag、releaseは、
それぞれ人間のyes/no承認前に行わないでください。

未承認のopenspec/changes/add-rtdose-coordinate-output-choice/を再作成、実装、
stageしないでください。

並列agent、Codex Security、security scan、脅威モデル、監査成果物生成は
使用しないでください。

調査結果として、現在のlocal/GitHub状態、推奨するPR・merge・release順序、
今日の最初の具体的な1操作を日本語で報告してください。
最後に、その1操作だけをyes/noで承認できる質問として提示して停止してください。
```

## Final statement

The accepted runtime defects found during the integration and Windows
acceptance have been corrected. The final local artifact is reproducible and
verified, human Windows installation/GUI/uninstall acceptance is complete, and
the active OpenSpec work is archived. The remaining work is to protect and
review the local branch, then make an explicit version and release decision in
a future session.
