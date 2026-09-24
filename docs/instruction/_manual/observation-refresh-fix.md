# GUI観測更新・Structure変更検出の修正 / GUI observation and Structure freshness repair

2026-09-24。PR #84はレビュー・CIを通過してmainへマージ済み。リモートブランチ削除済み。以下の未公開・未マージ記述は各作業段階の履歴で、最終結果は末尾に記載。v1.1.0タグと起動済みGUIには未反映。
PR #84 passed review and CI and is merged into main; its remote branch was deleted. Unpublished/unmerged statements below are historical checkpoints, superseded by the closing record. The v1.1.0 tag and already running GUI do not include the repair.

## 残バッチ数 / Remaining batches

読み取りを許可された実行の観測JSONは、batchの理由が `unsupported-format` だった。現在のbatch記録には分・秒形式のCPU時間があり、従来のパーサーは秒だけを受け付けていた。準備時の総数が表示に残る原因を特定した。

The authorized read-only inspection found `unsupported-format` for the batch channel. The current complete batch record used a minutes-and-seconds CPU duration, while the parser accepted seconds only. This explains the retained initial count.

完全な記録の検証を維持し、分・秒形式を受け付けるよう修正した。負値、非数、欠損、余分な文字、分付きで60秒以上の値は拒否する。読み取り確認で残数の解析を確認したが、実計算の値は公開資料に転記しない。観測値は完了証拠ではない。

The parser now accepts minutes-and-seconds durations while retaining complete-record validation. Negative, nonnumeric, incomplete, extra-text and invalid seconds fields remain rejected. A read-only check confirmed parsing; real-run values are omitted from this public record. Observations do not establish completion.

## Isocenter相対誤差 / Isocenter relative error

表示に使う観測JSONの更新が停止していた一方、その後の読み取り専用確認では現行の線量・誤差ペアを解析できた。表示更新の停止と元出力の停止は区別する必要がある。実計算の相対誤差、時刻、解析時間は公開資料に転記しない。

The observation sidecar had stopped updating, while a subsequent read-only inspection could parse the current dose/error pair. A frozen display must be distinguished from frozen source output. Real-run relative-error values, timestamps and parsing timings are omitted from this public record.

観測JSONの書き込み例外で観測処理を永久停止する実装を確認した。Windowsの一時的なアクセス・共有競合（5/32/33）では、そのサンプルを採用せず、次の新しいサンプルで通常の安全な出力処理を再試行する。50msの所有者ポーリングごとの再試行は行わない。危険なパス、その他の例外、終了済み観測の拒否は維持する。合成ファイルを通常のWindows読み取りハンドルで開いて置換を阻害するテストで、停止と復帰を検証した。

Previously, any publication exception permanently disabled observation. For Windows access/sharing conflicts (5/32/33), the failed sample remains unpublished and the next new sample can attempt the same guarded writer again. There is no retry at the owner's 50-ms polling cadence. Unsafe destinations, other failures and retired observers still remain disabled. An authored-file test uses an ordinary Windows reader to block replacement and verifies recovery after it closes.

**限界:** 昨日の例外は記録されておらず、実際の停止原因が共有競合だったとは断定できない。修正後の実PHITS再実行や長時間GUI試験は実施していない。元の計算は起動・停止・再開・変更していない。

**Limit:** The original exception was not logged, so a sharing conflict cannot be established as the historical cause. No real PHITS rerun or long-duration GUI test of the repair was performed. The original calculation was not launched, stopped, resumed or modified.

## Structure結果の変更検出 / Structure result freshness

従来の[調査](structure-rerr-investigation.md)で確認した、内容が変わってもmetadataが同じなら見逃す問題を修正した。全保持ソースについてSHA-256を再確認する。metadataが既に変わっていればハッシュ前に拒否し、ハッシュ後もmetadataを再確認する。

The [earlier investigation](structure-rerr-investigation.md) found that changed bytes could retain identical metadata. Every retained source now receives a fresh SHA-256 check. Changed metadata rejects before hashing, and metadata is checked again after hashing.

既存の単一バックグラウンド検証を利用し、終了後5秒で次の検証を予約する。線量配列・CT画素・Structure所属の再解析はしない。ストリーミング読み取りだが、以前よりファイルI/Oは増える。合成64 MiBファイル1個の温キャッシュ確認は0.0501秒だった。全実データや低速・ネットワークドライブの性能保証ではない。

The existing single background verifier schedules the next check five seconds after completion. It does not reparse dose arrays, CT pixels or Structure membership. Hashing streams data but increases file I/O. One warm-cache check of an authored 64-MiB file took 0.0501 seconds; this is not a performance guarantee for complete real datasets or slow/network storage.

## 検証 / Validation

- Focused Structure/live/generated/numeric tests: 196 passed before the final two publication guard tests were added.
- Final focused `tests/test_phits_live_observation.py`: 46 passed, including actual Windows sharing-conflict recovery on authored files.

| Command (repository `.venv/Scripts/python.exe`) | Result |
| --- | --- |
| `-m pytest -q -p no:cacheprovider` | 1474 passed, 15 skipped; 161.47 seconds |
| `-m compileall src` | passed |
| `tools/verify_public_tree.py` | passed; 367 tracked files, untracked manuals excluded |
| `git diff --check` | passed |
| `git diff --stat`, `git status --short` | reviewed; five tracked source/test modifications and the existing untracked manual folder |
| Markdown UTF-8, trailing whitespace and relative links | 14 documents passed |

変更ファイル / Changed runtime and tests:

- `src/dicomxphits/phits_observation.py`
- `src/dicomxphits/phits_observation_format.py`
- `src/dicomxphits/structure_relative_error.py`
- `tests/test_phits_live_observation.py`
- `tests/test_structure_relative_error.py`

公開仕様・PHITS入力・物理・DICOM意味・STOP/完了/下流処理の許可条件は変更していない。観測の2回確認・2秒制限・所有権・パス検証も維持した。実計算に関するアクセスは承認された読み取りのみで、実出力・DICOM・個別設定はこの資料やテストにコピーしていない。

Public specifications, PHITS inputs, physics, DICOM meaning and STOP/completion/downstream authority are unchanged. Two-observation confirmation, the two-second deadline, ownership and path guards remain intact. Access to the active calculation was read-only as authorized; real output files, DICOM and local configuration were not copied into these documents or tests.

実行中GUIへの反映・再起動・配布版更新は行わない。修正版を使う次回の起動で反映される。
The running GUI is not patched or restarted, and no packaged installation is updated. The repair applies when subsequently launching the repaired version.

停止点: ローカル修正と必須テスト完了。未commit・未push・新規PR未作成。実行中GUIへの反映、実PHITS再実行、長時間の更新確認、全実データでのStructure再確認性能は未検証。新機能・公開仕様変更ではなく既存動作の不具合修正のため、新規OpenSpec変更は作成していない。

Stopping outcome: local repair and required checks complete; no commit, push or new PR. Application to the running GUI, a real PHITS rerun, long-duration update verification and full-real-dataset Structure revalidation performance remain unverified. These repairs restore existing behavior without a new capability or specification change, so no new OpenSpec change was created.

## 承認後のPR作成 / Subsequent authorized publication

2026-09-24、commit・push・PR作成の承認後、GitHubプラグインで[PR #84](https://github.com/inata169/dicomxphits/pull/84)を作成した。上記の未commit・未pushという停止点は修正完了時点の履歴であり、現在は公開済み・未マージ。

After approval to commit, push and open a PR, the GitHub plugin published [PR #84](https://github.com/inata169/dicomxphits/pull/84). The previous uncommitted stopping outcome records the earlier repair phase; the patch is now published and unmerged.

- Branch: `codex/fix-gui-observation-refresh`.
- Local commit: `b45e6233184e5f64f48fc29057e97c122316a6e6`.
- GitHub commit: `95fc06d4d0d9589fd6c2f4f145c616be74807251`.
- Verified identical local/remote Git tree: `af1194c71cc2d84ae91fa40b1265c87a2547f83e`.
- The plugin commit uses current merged main as its parent; local and remote commit IDs consequently differ, while all tracked contents match.
- PR readback confirmed exactly the five runtime/test files listed above. Local manuals and screenshots were not included.
- Required checks above remain applicable to the identical published tree; staged diff and public-tree audit were checked again before publication.
- [GitHub Actions run](https://github.com/inata169/dicomxphits/actions/runs/35971314445) was in progress at publication handoff. No CI success or review approval is claimed.
- No operation on the running GUI or calculation folder was performed during publication. Public specifications and physics remain unchanged.

## レビュー・マージ完了 / Review and merge complete

2026-09-24、PR #84のレビュー対応・合格後マージ・リモートブランチ削除について人間の承認を受け、完了した。

- Codex review completed for `95fc06d` at 07:48:51 UTC. The Codex bot added a thumbs-up reaction; no review findings or inline threads remained. No correction round was needed.
- Public CI run `35971314445` succeeded on both Windows and Ubuntu, including compilation, tests and public-tree audit.
- PR #84 merged as `fa5f0a32d98b8c843cec9bf42f6610d45e92d866`, with the expected reviewed head SHA supplied to the merge operation.
- Remote branch `codex/fix-gui-observation-refresh` was deleted through the Browser plugin UI; the GitHub branch search subsequently returned no match.
- Local branch, manuals and screenshots remain preserved. No checkout, GUI restart, calculation-folder write, deployment or real-tool execution occurred.

停止点: 指摘なし・CI成功・マージ・リモートブランチ削除完了。新たなコード変更はないため、同一内容のローカル全テストは再実行していない。実計算での長時間検証など、上記の未検証事項は引き続き未実施。

Stopping outcome: review clean, CI successful, merged and remote branch deleted. No additional runtime changes were needed, so the identical local full suite was not rerun. Previously documented real-run and long-duration verification limitations remain.
