# 再実行後の下流継続の修正

2026-09-24。ブランチ`codex/gui-manual-research`。[English](retry-fix.en.md)。

[原因調査](retry-state-investigation.ja.md)で再現した不具合を、ユーザーの明示的な修正依頼に基づき修正した。

- 既存ケースでPHITS再実行が成功すると、復旧状態を再検査し、古い不足説明を更新する。
- v4/v5のセグメント実行証拠が完全に検証できる場合は、その証拠からSumtally未生成ケースの下流復旧を許可する。入力・出力のハッシュ、準備証拠、保持結果、親試行履歴の検証は維持する。旧形式は従来の下流summaryによる追加証拠を引き続き要求する。
- 証拠検証のValueError/OSErrorは復旧不可として表示する。

期待される操作は、再実行成功後に必要ならCT2PHITS workspaceを選択して引き継ぎ情報を復元し、`Create DICOM RT Dose`で提示される下流工程を確認すること。通常の新規ケース用ボタンを既存ケースで有効にする変更ではない。実行時の再検査と既存下流ファイルの履歴保存は従来どおり行う。

## 変更ファイル

- `src/dicomxphits/gui.py`: PHITS成功後の既存ケース再検査。
- `src/dicomxphits/workspace_recovery.py`: 完全検証済みv4/v5証拠による復旧判定。
- `tests/test_workspace_recovery.py`: 初回完了・再実行完了、出力・準備証拠・履歴破損の8ケース。
- `tests/test_gui_retry_recovery.py`: 非表示TkでSTOP、既存ケース検査、残りのみ再実行、表示更新、引き継ぎ情報の必要性、模擬下流工程の呼出しを検証。

非表示GUIテストは模擬tool profileと外部runnerを使い、下流コーディネータがSumtally GenerateからRTDOSE Runまでの4工程のみを呼ぶことを検証する。実際の下流出力生成・線量・DICOMの正しさをこのテストで確認したという意味ではない。外部プロセス起動は監査フックで禁止する。

## 検証

関連チェック:

```text
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_retry_recovery.py tests/test_workspace_recovery.py tests/test_segment_retry.py
```

77 passed、42.51秒。追加テストと修正に起因する失敗なし。

全公開テスト`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`も1456 passed、15 skipped、160.44秒で成功。修正4ファイルはローカルcommit `566ca04`に保存した。push・PR作成は未実施。説明書の資料は未追跡のまま保持している。承認範囲の修正・検証を完了し、追加変更は行わない。

`python`には開発用`.venv/Scripts/python.exe`を使用。`-m compileall src tests/test_gui_retry_recovery.py`、`tools/verify_public_tree.py`、`git diff --check`も成功。公開ツリー監査は追跡済み366ファイルが対象で、未追跡資料・新規テストは別途内容確認した。

実行中の10 threads GUI、実データ、実ツールは操作・検証していない。製品runtimeは上記バグ修正のみ変更し、物理計算・DICOMの意味・公開仕様は変更していない。既存仕様を回復する修正なので、新しいOpenSpec提案は作成していない。

以前の調査記録と`support/investigate_retry_state.py`は修正前の基点`4ad7a1e`での証拠を保存する資料である。同スクリプトは旧不具合をassertするため、修正後の検証には上記の新規回帰テストを使う。

commit後の公開ツリー監査も367追跡ファイルで成功。最終`git diff --check`・`git diff --stat`は差分なし、`git status --short`は未追跡の`docs/instruction/`のみ。

## PRレビューとマージ

追記：GitHubへのログイン後、2026-09-24にPR画面の`Delete branch`でリモートの`codex/gui-manual-research`を削除し、`Restore branch`表示で完了を確認した。以下の削除待ち記述はマージ直後の記録。

ユーザー承認後、GitHubプラグインで同一treeのcommit `f8a1f3389ff8472dc0eb068ea4085d21162adbd6`を公開し、[PR #83](https://github.com/inata169/dicomxphits/pull/83)を作成した。Codexレビューは同commitに対して重大な問題なしと報告し、修正指摘はなかった。公開CIも成功。追加修正なしで2026-09-24にmerge commit `f3750ed64266618f5f53d81539ecbd6cac23d755`へマージ済み。リモートブランチ削除は、プラグインに削除機能がなくブラウザも未ログインのため未完了。ローカルcheckout・計算中のGUIは変更していない。
