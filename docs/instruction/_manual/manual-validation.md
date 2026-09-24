# 操作説明書の検証記録 / Operating manual validation

公開前の最新チェックは[公開検証記録](publication-validation.md)を参照。以下は各作業段階の履歴で、初期のStructureテスト失敗はPR #84で修正済み。
See the [publication validation](publication-validation.md) for current checks. The following entries preserve earlier checkpoints; PR #84 repaired the initial Structure-test defect.

後続の[原因調査 / subsequent investigation](structure-rerr-investigation.md)で、metadataが変わらない同サイズ書換えを再確認処理が見逃す条件を確認した。下記は説明書作成時の検証結果を保持する記録。

2026-09-24。作業ブランチ / Working branch: `codex/gui-manual-research`。

## 成果物 / Deliverables

- [日本語本文](gui-manual.ja.md)
- [English manual](gui-manual.en.md)
- [README](README.md): 本文への案内を追加 / now points to the operating manuals.
- [修正記録（日本語）](retry-fix.ja.md)・[Repair record](retry-fix.en.md): PRブランチ削除完了を追記 / records completed remote branch deletion.
- 本検証記録 / This validation record.

日英は同じ12章構成。通常操作、進捗、準備キャンセル、STOP、再実行、下流復旧、フォルダ管理、トラブル、特別な操作、記録保管を含む。既存19枚の合成画面のうち、本文は各言語7枚を埋め込み、修正前の表示1枚を履歴としてリンクする。新しいGUI操作・撮影は行っていない。

Both languages have matching twelve-chapter structures covering normal operation, progress, preparation cancellation, STOP, retry, downstream recovery, folders, troubleshooting, special procedures and records. Each manual embeds seven existing synthetic screenshots and links one pre-fix screenshot as historical evidence. No new GUI interaction or capture was performed.

対象コードはローカル`566ca04`で、PR #83のリモート`f8a1f33`と完全なtreeが同一であることを公開時に確認済み。PR #83のmergeは`f3750ed`。本作業ではソース・物理・DICOM処理・公開仕様を変更していない。今回の説明書はローカル成果物で、commit・push・新規PR作成は未実施。

The local baseline is `566ca04`, whose complete tree was verified identical to PR #83's `f8a1f33` at publication; the merge is `f3750ed`. This documentation task changed no runtime, physics, DICOM behavior or public specification. The manuals remain local artifacts; no documentation commit, push or new PR was made.

## 確認 / Checks

| コマンド・確認 / Command or check | 結果 / Result |
| --- | --- |
| Pythonによる本文の章番号・主要ボタン名検査 / chapter and essential-control checks | 両言語12章、主要5操作あり / both languages passed |
| Markdown UTF-8・末尾空白・ローカルリンク / encoding, whitespace, local links | 成功 / passed |
| `.venv/Scripts/python.exe -m compileall src` | 成功 / passed |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | 成功、追跡済み367ファイル。未追跡資料は対象外 / passed, 367 tracked files; untracked manuals excluded |
| `git diff --check`, `git diff --stat`, `git status --short` | 追跡済み差分なし、`docs/instruction/`のみ未追跡 / no tracked diff; only `docs/instruction/` untracked |
| `git diff --exit-code -- src openspec` | 差分なし / unchanged |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | **1 failed, 1455 passed, 15 skipped**, 199.73秒 / seconds |

失敗は`tests/test_structure_relative_error.py::test_retained_large_sources_use_metadata_without_rehashing`。ファイル内容の変更後に期待された`StructureRelativeErrorUnavailable`が発生しなかった。初回調査でも同じ失敗があり、その後のバグ修正時には成功していた。今回の文書差分との因果関係や原因は未確定。再実行で結果を置き換えたり、テストを弱めたり、製品コードを変更したりしていない。

The failing test is `tests/test_structure_relative_error.py::test_retained_large_sources_use_metadata_without_rehashing`: changing file content did not raise the expected `StructureRelativeErrorUnavailable`. The same failure occurred during initial research and later passed during bug-fix validation. Its cause and any relationship to these documentation changes remain unestablished. No rerun was used to replace the result, and no test or runtime guard was weakened.

停止結果：日英本文の作成と文書検証は完了。全公開テストは全件成功ではないことを報告し、既存コードの調査・修正へは範囲を広げず終了する。

Stopping outcome: both manuals and document checks are complete. The full public suite is not all green; report that limitation and stop without expanding into investigation or repair of existing code.

実行中の10 threads GUI・設定・計算フォルダは操作していない。実PHITS、実データ、電源断、実フォルダ削除は未検証。本文は合成テストとコード・仕様に基づく操作説明であり、実外部ツールの検証証明ではない。既知の旧資料と現行仕様のハッシュ範囲の差異は本文末尾で明示した。

The running ten-thread GUI, settings and calculation directories were untouched. Real PHITS/data, power loss and real-folder deletion remain unverified. The manuals describe operation from synthetic tests and code/specifications; they do not certify real external-tool behavior. The known historical documentation discrepancy about hashing scope is disclosed in the manuals.

## 2026-09-24: 修正版GUI確認手順の追加 / Verification-plan addition

承認範囲は実計算を行わない手順・記録表作成。追加した資料は[日本語](live-verification.ja.md)と[English](live-verification.en.md)、更新した資料はREADMEのリンクと本記録。各言語6節、同じ列構成の表43行を確認した。現行の実行中GUI、設定、実計算フォルダは読み書きとも行っていない。

Authorization covered procedure and record-sheet preparation without real execution. Added the Japanese and English verification plans; updated the README links and this validation record. Both versions have six sections and 43 table rows with matching column structure. The running GUI, settings and real calculation directories were neither read nor written during this documentation task.

初回の文書検査スクリプトに表の行数を38と誤記し、43行を検出して停止した。文書の欠落ではなく検査側の固定値の誤りだったため、日英の行数・列数を直接比較する検査に修正し、成功した。製品テスト・安全条件は変更していない。

The first document check incorrectly expected 38 table rows and stopped when it found 43. The fixed-count assumption in the check was corrected to compare the two languages' row and column structure directly, which passed. No product test or safety condition was changed.

| Command / check | Result |
| --- | --- |
| Markdown UTF-8, trailing whitespace and relative links | 16 documents passed |
| Bilingual procedure and record-sheet comparison | Six sections and matching 43-row table structure passed |
| `.venv/Scripts/python.exe -m compileall src` | passed |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 1474 passed, 15 skipped; 160.90 seconds |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | passed, 367 tracked files; local untracked documents excluded |
| `git diff --check`, `git diff --stat`, `git status --short` | no tracked diff; `docs/instruction/` remains untracked |
| `git diff --exit-code -- src tests openspec` | unchanged from local `b45e623` |

停止点: 文書追加と検証完了。runtime・テスト・公開仕様・物理・DICOM意味は今回未変更。commit・push・PR・実PHITS実行・GUI起動・障害注入は行っていない。実動作確認結果は空欄/未確認のままであり、実行条件の別途承認後に記録する。

Stopping outcome: documentation and checks complete. Runtime, tests, public specifications, physics and DICOM meaning were unchanged. No commit, push, PR, real PHITS execution, GUI launch or fault injection occurred. Actual verification results remain blank/unverified, to be recorded only after separate authorization of execution conditions.
