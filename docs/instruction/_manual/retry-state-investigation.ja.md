# STOP後の再開と状態表示の原因調査

この文書は修正前の調査記録です。後続の[修正記録](retry-fix.ja.md)を参照してください。

2026-09-24 / 基点 `4ad7a1e` / `codex/gui-manual-research`。
[English](retry-state-investigation.en.md)

## 結論

先のGUI確認で未確定だった2点を切り分けた。中断ケースで下流復旧がBlockedでも未完了PHITSの再実行が可能なのは、判定対象が異なるためである。一方、再実行完了後の古い説明の残留と、既存ケースモードで下流へ進めない経路を合成データで再現した。後者は表示だけの問題ではない。製品コードの修正は今回の承認範囲外であり実施していない。

10 threadsで計算中のユーザーGUI・設定・フォルダ・プロセスには触れていない。テスト専用の非表示Tkを使用し、既存ウィンドウの検索・操作・撮影も行っていない。

## 再現結果

実際のGUIコールバックとセグメント実行・検証処理を使い、外部実行のみ模擬runnerに置き換えた。2セグメントのうち1つ完了後にSTOPし、既存ケース検査、残り1つの再実行、再検査を順に行った。

| 時点 | 表示・操作可否 |
| --- | --- |
| STOP済みケースの検査 | Workspace: Invalid existing case、PHITS: Not reusable、下流: Blocked。未完了再実行は有効。理由は未実行セグメントの出力不足。 |
| 再実行成功 | PHITS: Completed。Workspaceと下流の古い表示、および「出力不足」の説明が残る。通常のSumtally GenerateとCreate DICOM RT Doseはいずれも無効。 |
| 同じ結果の独立検証 | `segment_execution_authorizes_sumtally(workspace)`はTrue。保持結果と新規結果が揃い、通常のSumtally開始に必要なPHITS証拠は有効。 |
| 既存ケースを再検査 | PHITS: Not reusableに戻る。理由は「Matching SHA-256 evidence ... unavailable」に変わる。再検査だけでは下流へ進めない。 |

初回runner呼出しは`seg_001`のみ、再実行は`seg_002`のみ。テストの例外記録は空。外部プロセス起動は監査フックで禁止した。ツール存在確認は準備済みの模擬profileに置き換えたため、実ツール検出は検証していない。

## 原因

1. `gui.py:3033`の`inspect_selected_existing_workspace`は下流復旧検査の失敗を共通のInvalid/Not reusable/Blocked表示へ変換する。`gui.py:2545`の未完了再実行ボタンは別の証拠条件で評価する。中断時の下流禁止と再実行許可は両立するが、ケース全体を無効と読める文言は分かりにくい。
2. `gui.py:4076`付近の`finish_stage_success`はPHITS完了時にPHITSラベルを更新するが、`recovery_inspection`と`recovery_status`を再検査・更新しない。`set_busy(None)`経由のボタン更新も、この古い復旧判定を参照する。その結果、完了済み出力をまだ不足と表示する。
3. `gui.py:2633`付近では`existing_case_mode`中の通常のSumtally/RTDOSE操作を無効にする。一方、`workspace_recovery.py:224`の`_digest_evidence_sources`はSumtally生成・実行、RTDOSE準備とその履歴からハッシュ証拠を取得し、PHITSセグメント実行summary自体は候補に含めない。`inspect_existing_workspace`は有効なPHITS実行証拠を検証した後にも、この追加証拠を必須とする。Sumtallyをまだ一度も生成していないケースでは、通常のSumtally開始条件を満たしても復旧判定が拒否され、GUIの操作経路が閉じる。

行番号は上記基点の目安。関数名で照合すること。

合成fixtureは最小構成だが、今回のSHA-256拒否は単に出力本文が模擬文字列だからではなく、証拠の検索元に起因するとコードから確認した。実PHITSの結果やすべての既存ケースで再現したとの主張ではない。既に有効なSumtally等の証拠がある場合は別の経路になる。

## 説明書・修正への影響

説明書には中断中の下流禁止と未完了再実行を区別して記載できる。ただし「再実行がCompletedになれば、そのまま既存ケースの下流処理へ進める」とは現状では記載できない。再起動や再検査だけで直るという案内も、この再現結果では成立しない。

修正を行う場合は、成功後の復旧状態更新と、現在の有効なPHITS証拠からSumtally未生成ケースを安全に継続する経路を併せて扱う必要がある。検証を省略する、summaryを手修正する、結果を削除する回避策は提案しない。公開仕様のguided-gui-workflow「Guided Existing-Workspace Recovery」とphits-segment-retry「Complete Unique Downstream Evidence After Retry」が関連する。修正内容と既存証拠互換性は別途レビュー対象とする。

## 再現・検証

[診断スクリプト](support/investigate_retry_state.py)は画面を表示しない開発用の再現コード。製品の期待動作を定義する回帰テストではなく、現状の問題が起きることをassertする。

```text
.venv/Scripts/python.exe docs/instruction/_manual/support/investigate_retry_state.py --session-root <new-isolated-directory-outside-repository>
```

実行は成功し、隔離ディレクトリに`result.json`を保存した。実行のたびに新規ディレクトリを指定する。データ・個人PCの絶対パスを含む結果JSONは本資料にコピーしていない。

関連テストの最初の実行はpytest既定一時フォルダへのアクセス拒否で70件がsetup error。`-x --tb=short`で同じPermissionErrorを確認し、許可された実行環境で再実行した。結果と最終チェックは下記の検証結果に記載する。

製品runtime・公開仕様は未変更。commit・PR作成は行っていない。調査を完了し、修正には進まず停止する。

### 最終検証結果

| コマンド・確認 | 結果 |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_preflight_loop.py tests/test_segment_retry.py tests/test_workspace_recovery.py` | 70 passed、31.06秒。 |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 1447 passed、15 skipped、148.19秒。並列実行なし。 |
| `.venv/Scripts/python.exe -m compileall src docs/instruction/_manual/support` | 成功。 |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | 成功、追跡済み366ファイル。未追跡の本資料は監査対象外。 |
| `git diff --check` / `git diff --stat` / `git status --short` | 追跡済み差分なし。`docs/instruction/`のみ未追跡。 |
| `git diff --exit-code -- src openspec` | 差分なし。 |
| 資料の個別確認 | 7 MarkdownのUTF-8・末尾空白・ローカルリンクを確認。説明書フォルダにDICOMなし。 |

今回の追加は本資料・英語版・診断スクリプト。READMEと日英の初回検証記録に後続調査へのリンクを追加した。実ツール動作、実データ、修正後の動作は未検証。
