# dicomxphits GUI 操作説明書（日本語）

作成日：2026-09-24。[English](gui-manual.en.md) / [資料一覧](README.md)

対象：v1.1.0の機能と、[PR #83](https://github.com/inata169/dicomxphits/pull/83)の再開処理修正、[PR #84](https://github.com/inata169/dicomxphits/pull/84)の観測更新・Structure変更検出修正を含むコード。両修正はmainへマージ済みですが、公開済みv1.1.0タグには含まれません。以下の修正後の説明は両PRを含む版を前提とします。

このソフトウェアは教育・研究用の実験的な固定照射野3D-CRTワークフローです。許可を得た非患者ファントムデータを使用します。臨床利用、患者QA、IMRT、動的MLC、VMATは対象外です。実外部ツールを通した安定動作や臨床装置との線量一致を保証する説明書ではありません。

## 1. 最初に読む操作早見表

| したいこと | 操作・参照先 |
| --- | --- |
| 新しいケースを計算する | 4章のCT2PHITS → Workspace → PHITS → Sumtally → RTDOSE |
| PHITS開始前の準備を取り消す | 6章の`Cancel preparation` |
| PHITS計算を区切りのよい所で止める | 6章の`Stop after current segment`。即時停止ではありません。 |
| STOPしたケースを再開する | 7章の`Run incomplete segments…` |
| PHITSが完了したケースからRTDOSEを作る | 8章の`Open existing case…` → `Create DICOM RT Dose` |
| 空フォルダを先に作ってしまった | 9章。CT2PHITSは空でも既存フォルダを出力先にできません。 |
| ボタンが押せない・エラーが出た | 10章。フォルダや記録を消す前に状態と理由を確認します。 |

左の5工程と下部の`Activity log`を使います。上部の`Ready`は操作待ちという意味で、ケース全体の成功を意味しません。

![ケース設定の例（合成データ）](screenshots/01-case-setup.jpg)

画像は合成データによる検証用GUIです。タイトルの`SYNTHETIC MANUAL CHECK`は通常の起動例ではありません。個人PCの合成パスを含む操作画像は[公開対象外](screenshots/README.md)とし、手順を本文で説明しています。説明書の作成時に、別途実行中だった10 threadsのGUIは操作・撮影していません。

## 2. 起動前の準備と終了

WindowsとPython 3.12を使用します。PHITS、RT-PHITS、phits2dicomは別途正規に用意してください。インストールの詳細は[既存GUIガイド](../../gui-user-guide.md)を参照します。

初回だけ、リポジトリ直下のPowerShellで次を実行します。既に設定済みの環境を作り直す必要はありません。

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

通常の起動は次です。

```powershell
.\launchers\run_gui_venv.cmd
```

`.cmd`は仮想環境や依存関係を自動作成しません。PowerShell版ランチャーが署名エラーになる場合は、実行ポリシーを緩めず`.cmd`を使います。Linux Dev Container内からWindows GUIを起動する手順ではありません。

終了は工程が終わってからウィンドウを閉じます。実行中は通常の終了操作を拒否します。PHITSを中断したい場合は先に6章のSTOPを行い、終了状態を待ちます。GUIを強制終了する操作はSTOPの代わりになりません。

## 3. ツール設定とフォルダの区別

### ツール設定

1. `1 CT2PHITS` → `Tool settings • Show saved paths`を開きます。
2. 通常は`Standard PHITS 3.35-style layout`を選び、`PHITS installation folder`にPHITSの最上位フォルダを指定します。
3. `RTDOSE template`に公開テンプレート`templates\phits2dicom_rtdose_template.dcm`を指定します。
4. `Validate and save setup`を押し、標準構成では`Ready — phits-3.35-windows`を確認します。
5. `Tool settings • Back to case setup`で戻ります。

標準構成はPHITSルートの`bin\phits335_win_openmp.exe`、`utility\RTphits\RTphits_win.bat`、`utility\RTphits\data\HumanVoxelTable.data`、`utility\RTphits\bin\phits2dicom_win.exe`を想定します。異なる構成は`Custom layout (advanced)`で表示される各パスを明示します。設定検証だけでは外部計算を実行しません。

![ツール設定（合成データ）](screenshots/02-tool-settings.jpg)

ツールパスや一部実行設定・Browse履歴は保存されます。ケースのRT Plan、CTフォルダ、出力先、非患者確認、上書き許可は再起動時に自動復元されません。再開には既存ケースを明示選択します。

### 3種類のケース関連フォルダ

| 種類 | 内容・扱い |
| --- | --- |
| 入力フォルダ | 元のCTとRT Plan。出力先や削除対象にしません。 |
| CT2PHITSケース | 固定したRT Plan、CT参照、DATfiles。下流への引き継ぎに使います。実行前の出力先は未作成である必要があります。 |
| 3D-CRT workspace | セグメント入力・結果、集計、変換、検証記録。再開にはこのフォルダを選びます。 |

計算データはリポジトリ外で管理し、Gitに追加しません。標準設定のCT2PHITS出力はRT-PHITSの`work`配下に自動提案されます。入力と出力の場所を混同しないでください。

## 4. 新規ケースの通常操作

### 4.1 CT2PHITS：CTを変換する

1. `RT Plan (source)`と対応する`CT DICOM folder`を選択します。同じFrame of Referenceの非患者ファントムデータを使用します。
2. CTフォルダに複数シリーズがある場合は、Tool settingsの`Series UID (optional)`に目的のSeriesInstanceUIDを指定します。サブフォルダまで自動探索されるとは考えず、対象シリーズを含むフォルダを選びます。
3. `CT2PHITS case output`が新しい未作成パスであることを確認します。`Timeout (seconds)`の通常値は300です。
4. `I confirm non-patient phantom data`を確認して選択し、`Run CT2PHITS`を押します。
5. 完了後、`Verified frozen handoff`を確認します。Frozen RT Plan、CT reference、CT2PHITS DATfilesが下流へ引き継がれます。

下流が使うのは固定されたFrozen RT Planです。元ファイルを編集しても既存workspaceの計算設定を変更したことにはなりません。失敗した場合は10章に進み、同じ出力先で無条件に繰り返さないでください。

### 4.2 Workspace：入力を準備する

1. `2 Workspace`で`3D-CRT workspace`を選びます。`Browse…`は選択した親フォルダの下に新しいケース名を提案します。
2. `Geometry mode`は`rectangular_3dcrt`とします。通常は`Machine config (optional)`を空欄にして公開研究モデルを使います。
3. `Calculation config (optional)`を空欄にすると従来の101 × 101 × 101、3 mmの3D tallyを使います。変更する場合は11章を参照します。
4. 次の実行設定を確認して`Prepare workspace`を押します。

| 設定 | 初期値 | 意味 |
| --- | ---: | --- |
| `maxcas` | 1,000,000 | 1バッチのヒストリー数 |
| `maxbch` | 10 | バッチ数 |
| OpenMP threads | 8 | セグメント計算の並列スレッド数 |

ここではPHITS輸送計算は始まりません。RT Plan・MU・座標・照射野などを検証して入力を生成します。公開モデルの有効照射野はコリメータ座標のX/Yがそれぞれ−100～+100 mm以内、幅200 mm以下です。最大の中心正方形は20 × 20 cm²で、範囲外の照射野を自動で切り詰めません。

![Workspace設定（合成データ）](screenshots/03-workspace.jpg)

### 4.3 PHITS：全セグメントを計算する

1. `3 PHITS`で対象workspaceとPHITS実行ファイルを確認します。
2. `Run PHITS segments`を押します。
3. 最初の実行前準備・検証を待ちます。その後、各有効セグメントを順に計算します。
4. `Activity log`、PHITSの完了状態、完了数を確認します。全有効セグメントの結果検証が通るまでSumtallyには進みません。

実行中は入力、実行ファイル、結果、summaryを変更しません。生成入力の`$OMP = N`はPHITSの構文なので、コメントと考えて削除しないでください。止める場合は6章を使います。

### 4.4 Sumtally：結果を集計する

1. `4 Sumtally`で`Generate Sumtally`を押します。
2. 成功後に`Run Sumtally`を押します。
3. 両方の成功をActivity logで確認します。

集計は全有効治療セグメントをMUで重み付けした`totalfield`です。SETUPビームは治療線量の重みに含めません。未完了ケースの一部だけを集計する操作ではありません。

### 4.5 RTDOSE：DICOM RT Doseを作成する

1. `5 RTDOSE`でテンプレート、引き継いだCT参照、phits2dicomの設定を確認します。
2. `Prepare RTDOSE`を押します。
3. `Prepared`と`Next: click Run RTDOSE`を確認し、`Run RTDOSE`を押します。
4. `Completed`を確認し、`Final DICOM patient-coordinate output`に表示される`.fixed.dcm`を最終成果物として確認します。

Prepareだけでは変換は完了しません。標準的な出力位置は次です。実際にはGUIとsummaryに記録されたパスを優先します。

```text
<3D-CRT workspace>\sumtally\
  deposit-target-3D_sum_all_active_segments_totalfield.fixed.dcm
```

出力は`DoseUnits = GY`、`DoseSummationType = PLAN`です。現在の公開モデルでは1回分の集計線量に計画分割回数を一度適用したコース線量です。分割回数が不明・不正な場合に1と仮定して進めません。臨床装置の校正を証明する値ではありません。

![RTDOSE画面（合成データ）](screenshots/06-rtdose.jpg)

## 5. 進捗・状態・相対誤差の読み方

| 表示 | 意味と対応 |
| --- | --- |
| 準備中・検証中 | まだ輸送計算前、または結果の検証中の場合があります。ファイル読取も時間を要します。 |
| 完了数・残数 | 検証済みセグメントの状況。再実行では保持分と今回完了分を区別します。 |
| elapsed / ETA | elapsedは今回の試行の時間。ETAは推定で、再実行直後などは表示できません。 |
| `Ready` | GUIが操作待ち。成功・失敗は各工程とログで確認します。 |
| `Prepared` | RTDOSEの準備済み。変換実行済みとは異なります。 |
| `Completed` | 対応工程の成功。最終RTDOSEはその工程の完了と出力パスを確認します。 |
| `Blocked` / `Not reusable` | 下流復旧の証拠が不足・不一致。未完了PHITSの再実行可否とは別です。 |

Live Isocenter `r.err`は、現在のセグメントのアイソセンタを含む単一ボクセルの暫定統計相対誤差です。全体・全構造の線量誤差ではありません。`Unavailable`は値を安全に提示できない状態です。小さい値や残バッチ数0だけで、完了・収束・停止成功を判断しません。計算終了後のStructure評価は11章の別機能です。

`stale`は最後に採用した観測値が古い状態です。新サンプルが5秒ない場合にも表示され、長いバッチの途中では正常に発生します。分・秒形式のCPU時間を拒否する問題と、Windowsの一時的な共有競合後に観測が永久停止する問題はPR #84で修正済みです。[修正記録](observation-refresh-fix.md)を参照してください。実行中GUIには反映されません。観測表示が止まっただけでPHITSが停止したとは判断しません。

## 6. キャンセル・STOP・終了

### PHITSがまだ起動していない準備中

1. 有効になっている`Cancel preparation`を押します。
2. 送信中の表示だけで終了せず、`Preparation cancelled; no PHITS launched`を待ちます。
3. 初回計算を取り消した場合は、設定を確認して改めて`Run PHITS segments`で開始します。未完了再実行の準備を取り消した場合は、元の証拠を再検査して再度プレビューを作ります。

最初のセグメント起動が先に確定すると、準備キャンセルは受理されません。その場合、停止したければ別途`Stop after current segment`を操作します。

### PHITS計算中

1. `Stop after current segment`を1回押します。
2. `Stop pending`を待ちます。送信済みという表示だけでは受理確認になりません。
3. 受理時点で起動が確定していたセグメントの計算と検証を待ちます。停止までの時間は保証されません。
4. 未完了分が残れば`User stopped`と完了数・残数を確認します。この状態になってからGUIを閉じられます。

[STOP受理後の待機（合成データ） — local-only / 公開対象外](screenshots/README.md)

STOPは即時終了、バッチ途中停止、強制終了ではありません。受理した要求は取り消せません。クリック時に画面に出ていたセグメントと、受理時点のセグメントが異なる場合があります。最後のセグメントが正常終了して全数が揃えば、STOPと重なっても通常の完了になります。計算・検証が失敗した場合は`User stopped`ではなく失敗・未完了です。

ボタンが無効なら、そのGUIが所有する停止可能な実行だと確認できていない可能性があります。別GUIやCLIから動いている計算をこのボタンで止める機能ではありません。`batch.out`の手編集をGUIのSTOPの代わりにしないでください。

## 7. 中断・再起動後にPHITSを再開する

### 正常なSTOP後

1. 同じGUIで続ける場合は対象workspaceを維持します。GUIを再起動した場合は`1 CT2PHITS` → `Open existing case…`で元の3D-CRT workspaceを選びます。
2. `3 PHITS` → `Run incomplete segments…`を押します。
3. プレビューの保持セグメント、実行予定セグメント、スキップ対象を確認して承認します。
4. 実行予定分が完了し、全有効セグメントの検証が通るまで待ちます。
5. 新規ケースの通常モードを維持している場合は4.4節へ進みます。`Open existing case…`を使った場合は8章の復旧操作を使います。

[保持分・再実行分のプレビュー（合成データ） — local-only / 公開対象外](screenshots/README.md)

成功済みの検証可能な結果は保持します。未完了セグメントは最初から再計算し、途中の統計を継ぎ足しません。前回のSTOP要求は次の試行に持ち越されません。

PR #83を含む版では、既存ケースの再実行成功後に復旧状態を更新し、証拠が有効なら`Verified — locked`、`Recovery needed`、`Recovery ready`などの表示へ進みます。必要なCT2PHITS引き継ぎが未選択なら、8章の選択が必要です。修正前の[再実行完了画像 — local-only / 公開対象外](screenshots/README.md)には古い拒否表示が残っています。この画像は修正後の表示例には使わないでください。

### GUI消失・電源断・強制終了後

GUIが消えたことはPHITS終了の証拠ではありません。対象ケースの子プロセスが残っていないか、実行所有権が解放されているかを確認します。判断できなければworkspaceを保存し、管理者に確認を依頼します。PC全体のPython/PHITSを一括終了しないでください。

所有権が解放された後、`Open existing case…`から証拠を検査します。再実行プレビューが作れる場合だけ内容を確認して続けます。証拠が不足・改変されていれば再利用を強行せず、新しいworkspaceでの準備・計算が必要です。

再実行は、元のworkspace位置、実行ファイル、入力・準備記録・結果などの整合を必要とします。移動したケースや旧形式の記録は再実行できるとは限りません。結果があるというだけで再開可能とは判断しません。

## 8. PHITS完了後の下流復旧

1. `Open existing case…`で3D-CRT workspaceを開き、検査結果を読みます。
2. 引き継ぎを要求されたら`Select CT2PHITS workspace…`で、対応する完了済みCT2PHITSケースを選びます。DATfilesだけでなくケースフォルダを指定します。
3. `5 RTDOSE` → `Create DICOM RT Dose`を押します。
4. 確認画面の工程一覧と保存対象を確認し、承認します。
5. 最終的な`Completed`と`.fixed.dcm`のパスを確認します。

| 現在検証できる段階 | 復旧で必要になる工程 |
| --- | --- |
| PHITSまで | Sumtally Generate → Run → RTDOSE Prepare → Run |
| Sumtallyまで | RTDOSE Prepare → Run |
| RTDOSE Prepareまで | RTDOSE Run |
| 最終RTDOSEまで | 既存の最終出力を確認。不要な再実行はしません。 |

[下流復旧の確認画面（合成データ・RTDOSE Runのみの例） — local-only / 公開対象外](screenshots/README.md)

この操作はWorkspace PrepareやPHITSを再実行しません。競合する下流結果は承認後に`recovery_history/`へ保存されます。途中で失敗したらその工程で停止します。原因を直した後に再検査し、改めて必要工程を確認します。

PR #83を含む版は、現在のv4/v5 PHITS証拠が完全に検証できれば、Sumtally未生成でも復旧へ進めます。旧形式には従来の下流ハッシュ証拠が必要です。別PC・別パスへの移動は下流復旧と未完了PHITS再実行で条件が違うため、両方が可能とは限りません。

## 9. 手動作成フォルダ・不要なケースの扱い

GUIには任意フォルダを削除する機能はありません。`Start new case`は画面のケース状態を初期化する操作で、既存ファイルは削除しません。

### 出力用の空フォルダを先に作った場合

最も簡単なのは、まだ存在しない別の出力名を指定することです。削除する必要がある場合だけ次を行います。

1. そのフォルダを使う工程が動作していないことを確認します。別の計算中ケースは対象にしません。
2. エクスプローラーで対象の完全なパスを確認し、入力・インストール・既存ケースの親フォルダではないことを確認します。
3. 隠し項目を含め中身を確認します。ロックファイル、summary、結果、子フォルダがあれば「自分で作った空フォルダ」として扱いません。
4. 自分で作った不要な空フォルダだけを、利用環境でごみ箱に入る通常の削除方法で削除します。完全削除の警告が出る場合は中止し、別名の出力先を選びます。
5. GUIに戻り、削除したパスが未作成になったことと出力先の指定を確認します。

CT2PHITSは空でも既存フォルダを拒否します。3D-CRT Prepareの非空フォルダ制限とは異なります。削除コマンドや再帰削除を一括実行する必要はありません。

### 計算済み・未完了ケースを整理する場合

再開や監査に必要なケースは一式を保持します。`segments/`、`analysis/`、`sumtally/`を部分削除すると、成功結果があっても再利用できなくなることがあります。CT2PHITSケースも固定入力の引き継ぎに必要です。3D-CRT結果があるだけで削除可能とは判断しません。

不要と判断したケースを廃棄する場合は、実行終了、所有権解放、必要な成果物・記録のバックアップ、今後再開しないことを確認し、対象ケースだけを扱います。場所を変えたバックアップからの選択再実行は保証されません。

`.dicomxphits-execution.lock`は正常終了後も残ります。存在・古さだけで使用中とは判断できません。Busyを解除する目的で削除しないでください。`recovery_history/`、`analysis/segment_attempt_history/`、一時stagingも一律に安全な削除対象ではありません。インストールフォルダの削除はケース整理とは別の作業です。

## 10. 困ったとき

| 症状 | 確認・対応 |
| --- | --- |
| `Needs attention` | Tool settingsで標準ルートまたはCustomの各パスを確認し、再検証します。 |
| 非患者確認を求められる | 実際に許可された非患者データか確認します。患者データなら進めません。 |
| CT2PHITS出力が既存と表示される | 未作成の別名を選びます。9章参照。 |
| workspaceにファイルがある | 既存計算は`Open existing case…`で開きます。Prepareで作り直しません。 |
| ボタンが無効 | 他工程の実行中、ツール未設定、証拠不一致、既存ケースモード、引き継ぎ未選択を確認します。 |
| STOPが無効・送信失敗 | そのGUIが所有する停止可能な実行か確認します。受理を確認できなければ停止済みとは扱いません。 |
| Busy / 所有権エラー | 同じworkspaceのGUI・CLI・子プロセスの終了を待ちます。ロック削除で回避しません。 |
| 再実行プレビューが拒否される | 入力・準備記録・実行ファイル・成功結果・履歴の変更を確認します。summaryの手修正では直しません。 |
| RTDOSEが`Prepared` | 同じ新規ケースなら`Run RTDOSE`。再起動後は8章の復旧操作を使います。 |
| 復旧が`Blocked` | メッセージとActivity logを確認。PHITS未完了なら7章、証拠不一致ならケースを保存して原因確認。 |
| CT2PHITS timeout | summaryを確認。`process_tree_termination_error`があれば、残存子プロセスの確認前に同じ場所を再利用しません。 |
| geometry・モデル・dose factorの拒否 | 許容範囲外や古い証拠の可能性があります。ガード値を変えて通さず、適合する入力・設定で新規準備します。 |

`Allow overwrite of downstream stage summaries`は万能な復旧スイッチではありません。過去結果の保護条件を確認し、既存ケースの継続は8章を優先します。相対誤差だけが利用不能な場合にPHITS全体の失敗と即断せず、表示理由を確認します。

## 11. 特別な操作

| 操作 | 手順・範囲 |
| --- | --- |
| 検証済みCT2PHITSを新規準備に使う | Workspaceの`Use an existing validated CT2PHITS handoff (advanced)`。完了summaryに対応した不変のFrozen RT Plan、CT reference、DATfilesを使用します。パスの存在だけでは不十分です。 |
| 計算メッシュの変更 | 新規Prepare前にCalculation configを選択します。既存結果の後付け変更ではありません。[設定仕様](../../calculation-configuration.md)を参照。 |
| Structure r.err | 検証済みSumtally完了後、Sumtallyの`Post-completion Structure r.err`でRT Structure Setと一意の`ROINumber`を選び、`Evaluate selected Structure`を押します。ROI名による推測選択はしません。 |
| 相対誤差の補足復旧 | 専用の証拠に基づく復旧契約に従います。一時フォルダから手動コピーしません。[仕様](../../../openspec/specs/post-completion-structure-relative-error/spec.md)を参照。 |
| ファントムCTの水置換 | 5工程のGUIとは別のCLI作業です。[専用手順](../../phantom-ct-water-replacement.md)を参照。 |
| GPR比較 | GUIは最終RTDOSEまでです。[READMEのGPR手順](../../../README.md)を参照し、比較条件を明示して別途実行します。 |

Structure r.errは、全体の検証済み3D線量の最大値Dmaxに対して、構造内で`D > 0.5 × Dmax`を満たすボクセルを対象とします。閾値は固定です。r.errが0のボクセルは除外・計数し、0%不確かさとは扱いません。有効ボクセルが2未満なら利用不能です。平均・中央値・P95などと個数を読み合わせます。臨床的な線量誤差や収束判定ではなく、STOPやRTDOSEの実行可否も決めません。

変更検出の修正：同サイズの素早い書換えで古いStructure結果が残る問題は、PR #84で元ファイルの内容ハッシュも再確認するよう修正しました。v1.1.0タグには未反映です。評価後の関連ファイルを変更した場合は過去の表示を使用せず、改めて証拠検証・評価を行います。[原因調査](structure-rerr-investigation.md)と[修正・検証記録](observation-refresh-fix.md)を参照してください。

## 12. 結果の保管と問い合わせ

| 工程 | 主な記録（workspaceからの相対パス） |
| --- | --- |
| Workspace | `analysis/public_preparation_workspace_summary.json` |
| PHITS | `analysis/segment_execution_summary.json` |
| Sumtally生成 | `analysis/sumtally_generation_summary.json` |
| Sumtally実行 | `analysis/sumtally_execution_summary.json` |
| RTDOSE準備 | `analysis/rtdose_conversion_prepare_summary.json` |
| RTDOSE実行 | `analysis/rtdose_conversion_execution_summary.json` |

最終出力はRTDOSE実行summaryの`coordinate_corrected_rtdose_output`でも確認できます。未補正の`.dcm`と取り違えないでください。失敗時は`failure_reason`、`return_code`、記録されたstdout/stderrパスを確認します。項目名は工程で異なります。

問い合わせには版・commit、操作した工程と順序、状態表示、エラー本文、関係するsummaryを準備します。外部共有前に個人パス・識別情報を確認し、患者データ、ライセンス付きツール、資格情報を添付しません。

完了確認：全PHITS検証成功、Sumtally生成・実行成功、RTDOSEのPreparedとRun成功、最終`.fixed.dcm`の所在を確認して記録を保管します。

確認範囲：ソース・公開仕様、合成GUI画面、STOP/再実行/下流復旧の模擬テストに基づきます。実PHITSの停止時間・再開成功、電源断、実フォルダ削除、英語Windowsでのダイアログは未検証です。[GUI検証記録](gui-verification.ja.md)と[修正記録](retry-fix.ja.md)に証拠と制約を記載しています。旧資料のインストール全体ハッシュに関する記述には既知の差異があり、本書の再実行説明は現行コードと[現行仕様](../../../openspec/specs/phits-preflight-control/spec.md)を基準とします。
