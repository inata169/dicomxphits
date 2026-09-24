# GUI説明書の事前調査と構成案

調査日: 2026-09-24。対象: `main` の `4ad7a1e` を基点とする v1.1.0 のGUI。
これは説明書作成前の調査資料であり、操作確認済みの完成マニュアルではありません。
英語版: [manual-research.en.md](manual-research.en.md)。

後続の合成GUI確認と19枚の画面は[検証記録](gui-verification.ja.md)を参照してください。以下は初回調査時点の記録です。

## 調査結果

通常操作だけでなく、停止・再実行・計算完了後の復旧・フォルダ管理を独立した章にする必要があります。
GUIは5画面ですが、「中断して再度行う」は中断した段階によって操作が異なります。
既存の英語ガイドの単純翻訳では、準備キャンセル、STOP、未完了セグメント再実行、相対誤差表示を十分に説明できません。

v1.1.0は教育・研究向けの実験的リリースです。実外部ツールを用いるワークフロー全般の安定動作は未確立です。
対象は許可された非患者ファントムと固定照射3D-CRTであり、臨床用途、患者QA、IMRT、動的MLC、VMATを対象にしません。

## 日英で共通に設ける章

| 優先度 | 章 | 説明すべき内容 |
| --- | --- | --- |
| 必須 | 1. はじめに・対象バージョン | 実験的位置付け、対応範囲、固定6 MV研究モデル、照射野境界、検証の限界 |
| 必須 | 2. インストール・起動・終了 | Windows/Python 3.12、起動用cmd、PHITS等の別途準備、実行中のGUI終了制限、バージョン確認 |
| 必須 | 3. 初回ツール設定 | Standard/Custom layout、Validate and save setup、保存される設定と再入力するケース情報 |
| 必須 | 4. データとフォルダの準備 | RT Plan、CT series、複数series、非患者確認、元データ・CT2PHITS・3D-CRTフォルダの役割 |
| 必須 | 5. 通常の使い方 | CT2PHITS → Workspace → PHITS → Sumtally → RTDOSE。各操作の前提、ボタン、待つ表示、成功判定、出力 |
| 必須 | 6. 計算状況の読み方 | preparation/verificationとPHITS計算の区別、完了数、経過時間/ETA、Activity log、観測値と確定結果の違い |
| 必須 | 7. STOP・キャンセル・終了 | Cancel preparation、Stop after current segment、送信と受理の違い、停止待ち、停止後の状態、最終セグメントとの競合 |
| 必須 | 8. 中断後に再度行う | 起動前キャンセル、正常STOP、異常終了、PHITS完了後、別PCへの移動を分けた案内 |
| 必須 | 9. フォルダの整理・削除 | 手作成空フォルダ、途中/完了ケース、履歴、ロック、インストール先を区別。保持すべき情報と実行中確認 |
| 必須 | 10. 困ったとき | 無効なボタン、既存出力、timeout、busy、入力/出力の変更、geometry/モデル/線量係数の拒否、復旧不可 |
| 追加機能 | 11. 特別な対応 | 既存handoff、計算mesh、Custom layout、Structure r.err、既存ケース復旧、GUI外の専用CLIへの参照 |
| 必須 | 12. 結果・記録・問い合わせ | 最終.fixed.dcm、JSON/logの場所、再現に必要な操作記録、共有前の個人情報/パス確認 |

日本語版でもボタン名は実際の英語表記を併記します。両言語で章番号、注意事項、状態別の分岐を一致させます。
各手順は「使う場面 → 前提 → 操作 → 正常時の表示 → 失敗時の行き先」で統一する構成が適しています。

## STOPと再開で特に説明が必要な区別

| 状況 | 確認できた動作・記載すべき点 |
| --- | --- |
| 最初のPHITS起動前 | `Cancel preparation`。受理されれば子プロセスを起動しません。起動が先に確定した場合はキャンセルが拒否され、別途セグメントSTOPが必要です。 |
| PHITS計算中 | `Stop after current segment`は即時停止ではありません。`Stop pending`で受理を確認し、対象セグメントの終了と結果検証を待ちます。要求は撤回できません。 |
| STOPが受理された後 | 受理時点で確定済みのセグメントまで進みます。画面に見えていたセグメントと必ず一致するとは限りません。部分停止は`User stopped`、全完了なら通常完了です。 |
| 正常に部分停止した後 | `Run incomplete segments…`の新しいプレビューを確認します。検証済み成功分を保持し、未完了セグメントを最初から計算します。途中の統計を継続する機能ではありません。 |
| GUI終了・停電・異常終了後 | GUIが消えたことはPHITS停止の証明になりません。残存プロセスと所有権、記録を確認します。再実行可否は検証結果に従い、ロック削除で回避しません。 |
| PHITSは完了し、その後を再開 | `Open existing case…`で検証後、可能な場合に`Create DICOM RT Dose`。必要な下流工程だけ実行し、競合する過去出力は確認を経て`recovery_history/`へ保存します。 |
| 入力・設定・実行ファイルが変わった | 選択的再実行を無条件に案内しません。再利用を拒否された場合の新規workspace作成・再計算の説明が必要です。 |
| 別PC/別パスに移した | 検証済みPHITS結果からの下流復旧と、未完了PHITSの選択的再実行は別の条件です。移動しただけでどちらも再開できるとは説明しません。 |

Sumtallyには全active segmentの検証済み完了が必要です。部分停止後に途中結果を合算する手順はありません。
GUIの閉じる操作は工程実行中に警告して拒否されます。強制終了を通常STOPの代替として案内しません。

## フォルダ削除の章に必要な分類

GUIにはユーザーの任意フォルダを削除する専用操作が見当たりません。
`Start new case`は画面状態を切り替える操作で、既存ファイルを削除しません。

| 対象 | 説明方針 |
| --- | --- |
| 手で先に作った空のCT2PHITS出力フォルダ | 空でも「存在しない新規フォルダ」という条件に反します。まず未使用の新しい出力名を選ぶ方法を案内します。削除を扱う場合は対象と空であることの確認を別手順にします。 |
| 手で作った3D-CRT用フォルダ | CT2PHITSと混同しません。GUIのPrepare判定は「中にファイル等があるか」です。Browseが提案する新規の子フォルダ名も説明します。 |
| CT2PHITSケース | Frozen RT Plan、CT参照、DATfilesが下流で必要になります。3D-CRTが存在するだけで削除可とは判断できません。 |
| 途中/完了した3D-CRTケース | segments、analysis、sumtallyとその紐付けが再開・復旧に必要です。容量整理目的の部分削除が検証を壊すことを説明します。 |
| `.dicomxphits-execution.lock` | 正常終了後も残るファイルです。存在/古さだけで実行中とは判断できず、削除によるbusy解除を案内しません。 |
| staging、`recovery_history/`、`analysis/segment_attempt_history/` | 保持された途中結果や履歴を正式結果として手動コピーしません。安全な一括削除対象とは扱いません。 |
| インストール先・旧オフライン環境 | ケースフォルダの削除とアンインストールは別です。v1.1.0に公開オフラインZIPはなく、旧環境は専用資料の適用条件を確認する必要があります。 |

本調査では削除も外部フォルダの調査も行っていません。削除手順の画面検証には空の合成ケースを使用する想定です。

## 「特別な対応」として扱う項目

- 計算mesh: Calculation configは新規workspaceの準備時に適用。既存計算を書き換える操作として説明しません。
- 進行中のIsocenter r.err: 単一voxelの暫定的な統計相対誤差です。残りbatchが0、誤差が小さいことだけでは完了や合格になりません。Unavailableの理由も必要です。
- 完了後のStructure r.err: Sumtally画面の独立機能です。RTSTRUCTと一意なROINumberを選び、明示的に評価します。固定の線量閾値、対象voxel数、平均/中央値/P95、ゼロ誤差除外を説明します。臨床線量誤差や収束判定ではありません。
- retained Sumtally相対誤差復旧: 特別な証拠を必要とする専用処理として参照し、stagingからの手動コピーを案内しません。
- ファントムCT水置換、GPR比較: GUIの5画面には含まれない専用CLIです。通常手順から分離し、既存資料を参照します。
- `batch.out`の手編集: GUIのSTOPと同じ保証にはなりません。可変の制御/観測ファイルであり、内容だけで安全停止や完了を証明できません。標準操作には含めません。
- RTDOSEの意味: 最終座標補正済み出力、GY/PLAN、分割数の扱いと研究モデルの限界を既存仕様に沿って説明します。

## 執筆前に解消または明示すべき点

1. **既存資料の版と説明範囲**: `docs/gui-user-guide.md`はv1.0.x表記で、新しいGUI操作の説明が不足しています。新説明書はv1.1.0と調査基点を明記する必要があります。
2. **再実行の検証範囲に不一致**: `docs/incomplete-segment-execution.md`のEvidence and eligibilityはPHITSインストールツリー全体をhashすると説明しています。一方、現行`phits-preflight-control`仕様と`segment_retry.py`の`_selected_executable_evidence`は選択実行ファイルの`selected_executable`範囲を示します。本調査では不一致を記録するにとどめ、既存文書・仕様・実装を変更していません。
3. **異常終了・再起動後の正確なクリック順**: 実装には既存ケースの下流復旧と未完了再実行の別条件があります。最終マニュアルでは合成workspaceで各状態のボタンと復帰経路を確認してから画面手順を確定する必要があります。
4. **手作成フォルダの意味**: 空フォルダ、計算フォルダ、手動インストール先をすべて分類しました。実際の削除対象はまだ指定されていません。
5. **画面資料と実機確認**: 今回はソース・仕様・文書の静的調査です。現行GUIの画面撮影、実PHITS、実DICOM、強制終了、削除、再開の実機検証は実施していません。掲載画像は合成例から作成する必要があります。

以上の未確定事項を解消せずに、操作確認済みの説明書として公開しない構成とします。

## 主な調査根拠

- [既存GUIガイド](../../gui-user-guide.md)、[v1.1.0リリース情報](../../release-notes-v1.1.0.md)
- [STOP説明](../../segment-boundary-stop.md)、[未完了再実行説明（上記不一致あり）](../../incomplete-segment-execution.md)
- [GUI実装](../../../src/dicomxphits/gui.py)、[再実行の検証実装](../../../src/dicomxphits/segment_retry.py)、[出力保護実装](../../../src/dicomxphits/safe_output.py)
- [準備とキャンセル仕様](../../../openspec/specs/phits-preflight-control/spec.md)、[下流復旧仕様](../../../openspec/specs/portable-workspace-recovery/spec.md)
- [live観測仕様](../../../openspec/specs/phits-live-observation/spec.md)、[Structure評価仕様](../../../openspec/specs/post-completion-structure-relative-error/spec.md)
- [計算設定](../../calculation-configuration.md)、[CT水置換](../../phantom-ct-water-replacement.md)、[オフライン環境資料](../../windows-offline-installation.ja.md)

## この調査資料の検証記録

- 変更は本資料と英語版の追加のみ。ブランチ: `codex/gui-manual-research`。実装・公開仕様は未変更、commit/PRは未作成です。
- 日英各15リンクの存在、UTF-8、末尾空白をPythonで確認: 成功。
- `python -m compileall src`: 成功。
- `python tools/verify_public_tree.py`: 成功（既存の追跡済み366ファイル。未追跡の新規資料は対象外）。
- `git diff --check`、`git diff --stat`、`git status --short`: 実施。新規資料は未追跡のため通常diffは空。各新規ファイルを`git diff --no-index --check -- NUL <file>`でも検査し、空白エラーなし。追加は計2ファイルです。
- `python -m pytest -q -p no:cacheprovider`: system Pythonにpytestがなく実行不可。
- `.venv`の同コマンド: 一時ディレクトリの権限制限でsetupエラーが続いたため中断。`-x`で再確認し、14 passed / 1 error（PermissionError）。
- 許可後、`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`を再実行: **1446 passed / 15 skipped / 1 failed**。
- 失敗: `tests/test_structure_relative_error.py::test_retained_large_sources_use_metadata_without_rehashing`。ファイル更新後に期待された`StructureRelativeErrorUnavailable`が発生しませんでした。原因は未確定で、今回の文書変更との因果関係は確認していません。実装修正やテストの緩和は行っていません。
- 停止点: 事前調査を保存して終了。操作マニュアル本体、画面検証、資料間の不一致の解消、全チェック成功は未完了です。
