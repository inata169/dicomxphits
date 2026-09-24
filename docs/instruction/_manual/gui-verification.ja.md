# 合成データによるGUI操作確認

実施日: 2026-09-24。対象: `4ad7a1e`基点、v1.1.0。
ブランチ: `codex/gui-manual-research`。[English](gui-verification.en.md)。

## 結果と対象範囲

後続の[原因調査](retry-state-investigation.ja.md)で、再実行後の古い表示と既存ケースの下流継続不能を再現しました。以下は初回確認時点の記録で、未確定事項は後続調査を参照してください。

独立した検証GUIで、基本5画面、準備キャンセル、STOP、GUI再起動後の未完了再実行、準備済みRTDOSEの下流再開を確認し、19枚の画面を保存しました。
ユーザーが10 threadsで計算中のGUIは操作・撮影していません。その設定、計算フォルダ、実行中のプロセスも変更していません。

製品のGUI・検証関数・セグメント制御・復旧処理を使い、外部ツール実行はPythonの模擬処理に置き換えました。
実PHITSやphits2dicomを起動した検証ではありません。線量精度、実ツールの停止時間、実計算の再開成功を保証するものではありません。

検証用GUIだけに別タイトルを付け、初期設定と保存先を分離しました。通常の保存済みツール設定は読み込んでいません。
検証プロセスでは外部プロセス起動を拒否する監査フックも設定しました。模擬制御はプロセス内で渡しており、実PHITSとのstdin通信をこの画面確認で検証したわけではありません。

## 画面で確認した操作

| 項目 | 実施内容と結果 |
| --- | --- |
| 基本画面 | CT2PHITS、Tool settings、Workspace、PHITS、Sumtally、RTDOSEへ移動し、実際のラベルと操作の配置を確認。新規ケースを5工程すべて連続クリックして完了させた検証ではありません。 |
| 起動前キャンセル | 模擬ファイル読取を待機させて`Cancel preparation`を押下。要求送信の表示を確認後、読取待機を解除すると`Preparation cancelled; no PHITS launched`。模擬runner呼出回数は0、Sumtallyは無効。 |
| セグメントSTOP | 2セグメントの合成ケースを開始。`Stop after current segment`を押し、`Stop pending`を確認。模擬セグメントを終了させると`User stopped`、完了1/2、残り1。2番目のrunnerは未実行。 |
| 実行中に閉じる | STOP待ち中の検証GUIに閉じる操作を行うと`Wait for the active stage to finish before closing the GUI.`と警告。GUIは終了せず、模擬実行を維持。 |
| GUI再起動後の未完了再実行 | 検証GUIを閉じ、別プロセスで起動。`Open existing case…`で同じ合成workspaceを明示選択し、PHITS画面の`Run incomplete segments…`を押下。プレビューは保持`seg_001`、再実行`seg_002`。確認後、呼ばれたrunnerは`seg_002`だけ。 |
| 保持結果の確認 | `seg_001`のファイルSHA-256と更新日時を再実行前後で比較し、変更なし。結果はsuccess、2/2完了、保持1、新規完了1。旧STOP要求は引き継がれていません。 |
| 証拠不足時の復旧拒否 | STOP/再実行用の最小fixtureは、下流復旧検査では不足する証拠がありBlockedになりました。PHITSの完了表示だけで下流復旧成功とは判断しません。証拠を書き換えて通すことはしていません。 |
| RTDOSEの下流再開 | 別の正常系fixtureでSumtallyとRTDOSE Prepareを準備。GUIから`Open existing case…`→RTDOSE→`Create DICOM RT Dose`。確認ダイアログは実行対象`RTDOSE Run`のみ。模擬変換後にCompletedと最終`.fixed.dcm`の表示を確認。 |

RTDOSE再開の呼出記録は`["run_rtdose"]`のみでした。GUI操作からWorkspace Prepare、PHITS、Sumtallyを再実行していません。
この正常系fixtureの準備には、既存テストの合成DICOMと模擬Sumtally処理を使っています。

## 説明書に反映する具体的な案内

1. **STOPは押した瞬間の終了ではない。** `Stop pending`と`User stopped`を別の画面として説明し、待っている間にGUIを閉じないよう案内します。
2. **準備キャンセルと未完了再実行は別。** 最初の起動前キャンセルではrunner未実行で、通常の`Run PHITS segments`が再び有効になりました。STOP後は`Run incomplete segments…`のプレビューを使います。
3. **既存ケースの下流復旧判定と未完了再実行を区別する。** 今回、開き直した停止ケースには`Invalid existing case`/`Not reusable`/`Blocked`が表示されましたが、未完了再実行のプレビューは利用できました。すべてのBlockedケースが再実行可能という意味ではありません。
4. **成功表示だけで再利用を判断しない。** 未完了再実行の成功後も、下流復旧に必要な記録は別途検査されます。今回の最小fixtureの拒否を、一般の実ケースの原因と同一視しません。
5. **RTDOSE再開では確認ダイアログの実行対象を読む。** Prepareの証拠が有効なケースではRunだけが実行されました。他のケースで同じ工程数になるとは限りません。
6. **フォルダは用途別に説明する。** 関連テストでCT2PHITSの新規出力条件と、非空workspaceの上書き拒否を確認しました。空フォルダ削除、実ケース削除、インストール先の削除は実施していません。名前の再利用のために既存結果を消す案内はしません。

## 画面一覧

すべて合成検証画面です。ダイアログはこのPCのWindows言語に従うため、日本語の「はい」「いいえ」が表示されています。ローカルの合成パスは設定例ではありません。

| 画像 | 内容 |
| --- | --- |
| [01](screenshots/01-case-setup.jpg) | ケース設定 |
| [02](screenshots/02-tool-settings.jpg) | ツール設定 |
| [03](screenshots/03-workspace.jpg) | Workspace・計算条件 |
| [04](screenshots/04-phits-controls.jpg) | PHITSの操作ボタン |
| [05](screenshots/05-sumtally.jpg) | Sumtally |
| [06](screenshots/06-rtdose.jpg) | RTDOSE |
| [07 — local-only / 公開対象外](screenshots/README.md) | 合成セグメント実行中 |
| [08 — local-only / 公開対象外](screenshots/README.md) | STOP受理後の待機 |
| [09 — local-only / 公開対象外](screenshots/README.md) | 実行中の終了警告 |
| [10 — local-only / 公開対象外](screenshots/README.md) | 1/2完了で停止 |
| [11 — local-only / 公開対象外](screenshots/README.md) | GUI再起動後に停止ケースを開いた状態 |
| [12 — local-only / 公開対象外](screenshots/README.md) | 保持分・再実行分の確認 |
| [13 — local-only / 公開対象外](screenshots/README.md) | 未完了分の再実行完了 |
| [14 — local-only / 公開対象外](screenshots/README.md) | 最小fixtureの下流復旧拒否 |
| [15 — local-only / 公開対象外](screenshots/README.md) | 起動前の準備中 |
| [16 — local-only / 公開対象外](screenshots/README.md) | 起動前キャンセル完了 |
| [17 — local-only / 公開対象外](screenshots/README.md) | RTDOSE再開可能 |
| [18 — local-only / 公開対象外](screenshots/README.md) | Runだけ実行する確認 |
| [19 — local-only / 公開対象外](screenshots/README.md) | 合成RTDOSEの完了 |

[STOPが受理され、現在の模擬セグメントを待っている画面 — local-only / 公開対象外](screenshots/README.md)

## 再現方法と検証中の問題

[検証スクリプト](support/synthetic_gui_session.py)を、pytest等を含むリポジトリの開発用Python環境で実行します。
`--session-root`はリポジトリ外の新しい合成専用ディレクトリを明示します。`resume`のみ、このスクリプトで作成した既存sessionを使います。

```text
python docs/instruction/_manual/support/synthetic_gui_session.py --mode layout --session-root <new-synthetic-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode stop --session-root <new-stop-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode resume --session-root <same-stop-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode cancel --session-root <new-cancel-session>
python docs/instruction/_manual/support/synthetic_gui_session.py --mode recovery --session-root <new-recovery-session>
```

`stop`の模擬runnerはsession直下の`finish-synthetic-segment`、`cancel`の模擬読取は`finish-synthetic-read`という空ファイルの作成で待機を終えます。これは検証専用であり、製品のSTOPファイル機能ではありません。上限10分を超えると検証処理は失敗します。
操作中の状態はsession内の`ui-<mode>.jsonl`、模擬呼出は`runner-calls.json`に記録します。これらのローカル記録や合成結果はこの資料フォルダへコピーしていません。

- 初回の再開確認で検証アダプタの`_default_values`がパス引数を受け取れず、TkコールバックにTypeErrorが発生しました。検証スクリプトだけを修正し、同じ合成ケースで再確認して成功しました。
- 下流復旧関数の既定runnerが定義時に束縛されるため、模擬runnerを明示的に渡す検証ラッパーを追加し、修正後の別GUIで正常系を確認しました。監査フックは維持しました。
- Computer Useの初回撮影は別画面を返したため保存せず、検証ウィンドウを再選択しました。フォルダ選択ダイアログの要素番号操作も失敗したため、再取得したダイアログ画像に基づく操作へ切り替えました。実計算のウィンドウは選択していません。
- 画像形式チェックで、撮影ツールの出力はPNGではなくJPEGと判明しました。画像の内容は変更せず、拡張子と文書リンクを`.jpg`に修正しました。開発用PythonにPillowがなかったため、19枚すべてを画像読取ツールで読み込み、JPEGの開始/終了マーカーも別途確認しました。

## チェックと未確認事項

関連テストは次のコマンドで**11 passed**でした。

```text
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_preflight_loop.py tests/test_manual_smoke_workflow.py tests/test_segment_retry.py::test_retry_preserves_completed_artifacts_and_creates_unique_terminal_evidence tests/test_workspace_recovery.py::test_gui_recovery_runs_only_inspected_downstream_suffix tests/test_gui.py::test_ct2phits_gui_stage_keeps_explicit_confirmation_and_new_workspace_gate tests/test_gui.py::test_existing_workspace_overwrite_detection_does_not_start_subprocess
```

全公開チェックと成果物チェック:

| コマンド・確認 | 結果 |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 1447 passed / 15 skipped、168.18秒。並列実行なし。 |
| `.venv/Scripts/python.exe -m compileall src docs/instruction/_manual/support` | 成功。製品ソースと検証スクリプトの構文を確認。 |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | 追跡済み366ファイルで成功。新規の未追跡資料はこの監査の対象外。 |
| `git diff --check`、`git diff --stat`、`git status --short` | 実施。`docs/instruction/`のみ未追跡で、追跡済みファイルのdiffなし。 |
| 文書と画像の確認 | 相対リンク、UTF-8、末尾空白、19枚のJPEGの整合性を別途検査。 |
| 検証GUI終了確認 | `SYNTHETIC MANUAL CHECK`のウィンドウは残っていません。 |

初回調査で失敗した相対誤差テストも今回は成功しました。ただし原因特定や修正はしていないため、以前の失敗が解消されたとは断定しません。
commit/PRは未作成です。追加・更新対象はこのフォルダ内のREADME、日英調査資料、日英検証記録、検証スクリプト、画面19枚のみです。

未確認: 実PHITSの停止/再開、実外部ツールによる一連の計算、電源断・強制終了、実フォルダの削除、英語Windowsでのダイアログ表示、Structure r.errの画面撮影。
既存英語資料の検証範囲に関する不一致は前回の[調査資料](manual-research.ja.md)に記録済みで、今回その既存資料・公開仕様は変更していません。

成果物は検証記録・画面・再現用スクリプトです。製品ランタイムおよび公開仕様は未変更です。日英の操作マニュアル本体は次の執筆段階に残っています。
