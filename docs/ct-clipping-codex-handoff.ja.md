# CT 3断面クリッピング機能：Codex実装引き継ぎ

## 1. この引き継ぎの位置づけ

利用者は、dicomxphits GUIでCTのAxial・Coronal・Sagittal画像を表示し、
数値入力または画像上のクリックでクリッピング範囲を指定したい。
計画書は作成済みであり、今回は実装担当へ渡す文書とプロンプトを用意した。
この文書を作成した時点では、実装コードと確定済み公開仕様は変更していない。

OpenSpec提案は承認待ちのdraftとして保持している。
添付の[実装依頼プロンプト](ct-clipping-codex-prompt.ja.md)を利用者が実装指示として
送信した場合、その送信を記載範囲の提案承認として記録し、実装へ進む。
ファイルを発見した、参照資料として読んだ、という理由だけでは承認と扱わない。
現在の引き継ぎ作成依頼を、実装済み・承認済みと記録してはならない。

## 2. 作業状態と引き継ぎ方法

- リポジトリ：`dicomxphits`。
- 現在のブランチ：`codex/plan-ct-pixel-clipping`。
- HEAD：`ec4fbec`（`Add ROI GUI launcher and clarify analysis steps (#91)`）。
- origin：`https://github.com/inata169/dicomxphits.git`。
- 確認済みタグ：`v1.0.0`から`v1.1.1`。
- OpenSpec計画7ファイルはステージ済みだが未コミット・未push。
- この引き継ぎ書とプロンプトもローカル文書。PR、merge、タグ変更は行っていない。

**同じローカル作業フォルダーを開いたCodexへ引き継ぐこと。**
main、GitHub、またはHEADだけから作った別worktreeには未コミットの計画がない。
別環境へ移す必要がある場合は、承認された方法で計画と引き継ぎ文書を渡し、
実装前に存在と内容を確認する。欠落した計画を想像で再作成しない。
開始時にはroot、branch、status、履歴、remote、tagsを再確認する。

既存の未追跡ファイルがある。これらは本タスクの対象ではなく、開く・取り込む・
削除する・上書きする操作を行わない。

- `config/dicomxphits.calculation.arccheck.json`
- `docs/instruction/_manual/screenshots/`の07から19で始まる既存JPEG群

clean状態を作るためにreset/cleanを実行しない。変更をステージする際は対象を
明示し、`git add -A`で無関係なファイルを巻き込まない。

## 3. 最初に読むファイル

1. [AI_AGENT_RULES.md](../AI_AGENT_RULES.md)を全文読み、
   [AGENTS.md](../AGENTS.md)と併せて守る。
2. [OpenSpec運用規則](../openspec/AGENTS.md)と
   [プロジェクト定義](../openspec/project.md)。
3. 本変更の[proposal.md](../openspec/changes/add-ct-pixel-clipping/proposal.md)、
   [design.md](../openspec/changes/add-ct-pixel-clipping/design.md)、
   [tasks.md](../openspec/changes/add-ct-pixel-clipping/tasks.md)、
   [validation.md](../openspec/changes/add-ct-pixel-clipping/validation.md)。
4. 本変更の仕様差分：
   [ct-pixel-clipping](../openspec/changes/add-ct-pixel-clipping/specs/ct-pixel-clipping/spec.md)、
   [ct2phits-frontend](../openspec/changes/add-ct-pixel-clipping/specs/ct2phits-frontend/spec.md)、
   [guided-gui-workflow](../openspec/changes/add-ct-pixel-clipping/specs/guided-gui-workflow/spec.md)。
5. 対応する現行仕様と
   [ct-accelerator-geometry-safety](../openspec/specs/ct-accelerator-geometry-safety/spec.md)。

本書は再開用の案内であり、矛盾があれば利用者の承認済み依頼と現行仕様・規則を
優先し、矛盾の内容を報告する。別のOpenSpec変更を重複作成しない。

## 4. 実装する操作

既存CT2PHITSページから「CT画像・クリッピング範囲」を開く。
3画像と6つの数値欄で、1つの軸に平行な直方体を共有する。

| 表示 | 2点クリックで変更する軸 | 保持する範囲 |
| --- | --- | --- |
| Axial（横断面） | X・Y | 開始・終了スライス |
| Coronal（冠状断面） | X・Z | Ny最小・最大 |
| Sagittal（矢状断面） | Y・Z | Nx最小・最大 |

- 数値欄はNx最小・最大、Ny最小・最大、開始・終了スライス。
- 1始まりで両端を含む元画像のインデックス。mmや画面座標ではない。
- 同じ画像内の対角2点を「ここから、ここまで」とクリックする。
  クリック順序が逆でも同じ範囲にする。別画像へ移ったら未完の2点選択を取り消す。
- 数値変更と3画像の選択枠を双方向に同期する。マウスポインターの元座標も表示する。
- スライス移動、閲覧用クロスヘア、コントラストは範囲選択から独立させる。
- 「適用」「キャンセル」「全範囲に戻す」を用意する。適用前の編集で現在の設定を
  上書きしない。範囲外の断面を閲覧中なら、そのことを明示する。
- 初期値は全体。CTやシリーズの変更で古い範囲を失効させる。
  範囲は症例固有の一時状態であり、全体設定として保存しない。
- 明示的な非患者ファントム確認の後で画素を読む。患者属性を表示しない。

## 5. 実装の入口

| 場所 | 調査済みの役割 |
| --- | --- |
| `src/dicomxphits/gui.py` | Tk GUI、`GuiConfig`、CT2PHITSページ、CLI引数生成、worker、完了後handoff |
| `src/dicomxphits/run_ct2phits.py` | `select_ct_series()`、`render_ct2phits_input()`、CLI、snapshot、manifest |
| `src/dicomxphits/ct2phits_datfiles.py` | 元CTの原点、IEC変換、c91/c92/c93更新、準備済みCT資産 |
| `src/dicomxphits/structure_relative_error.py` | 元CTの寸法・スライス数・原点と下流情報の整合確認 |
| `tests/test_run_ct2phits.py`、`tests/test_ct2phits_datfiles.py`、`tests/test_gui.py` | 既存の入力・handoff・GUIテスト |
| `docs/instruction/_manual/gui-manual.ja.md`、`gui-manual.en.md` | 操作説明の更新先 |

Tk、numpy、pydicomを基本とし、新規画像ライブラリは前提にしない。
小さな範囲モデル・表示座標変換モジュールとビューアを分離する。
ファイル名案は`ct_pixel_clipping.py`と`ct_preview.py`。
既存のシリーズ検証を再利用し、別の緩いDICOM検証を追加しない。

元配列は`volume[z, y, x]`。Zは物理位置の昇順であり、ファイル名やInstanceNumber
の順ではない。Coronal/Sagittalの上下表示を反転した場合は、クリックの逆変換にも
反映する。異方性PixelSpacingと実際のZ間隔を使い、表示縦横比を保つ。

3断面にはスタック読込が必要。メモリー上限、進捗、キャンセル、古いworker結果の
破棄を実装する。表示用のrescale/コントラストで元画素を書き換えない。
単一スライスでは隣接Z間隔を推定せず、Axial・数値操作を残して他断面を利用不可と示す。
復号失敗やメモリー不足を通常のエラーとして表示し、外部codecを自動導入しない。

CLI案は`--pixel-clipping NX_MIN NX_MAX NY_MIN NY_MAX`と
`--slice-range FIRST LAST`。省略時は既存の入力と動作を保つ。

## 6. 変換を有効にする前の必須確認

現状の入力は`1 slice_count`と`1 Columns 1 Rows`に固定されている。
任意範囲を渡すだけで後続計算の位置が正しいとは確認できていない。

特に、既存準備処理は**元の全CTの原点**からc91/c92/c93を再計算する一方、
生成されたCTsurf/CTvoxelをそのまま利用する。CT2PHITSが切り出しによるずれを
どこに表現するかを確認せずに平行移動を追加すると、位置ずれや二重補正になり得る。

次の事項を、対応バージョンの権威ある説明と独立した期待値で確認・記録する。

1. 元画素番号・スライス番号と、両端を含む指定の正確な意味。
2. 粗視化`8 8 2`で、小さな範囲、端数、境界に揃わない開始番号をどう扱うか。
3. X/Yだけ、Zだけ、XYZを切り出した場合の生成格子の寸法・範囲・位置。
4. 元CTの原点を使う現在のhandoffで正しい位置が保たれるか。

全CTのsnapshot、番号、UID、hash、元寸法、元スライス数、元原点を保持する。
切り出し対象だけコピーして再採番しない。凍結参照`CT/CT000001.dcm`を維持する。
選択は`ct2phits_input.clipping`と`ct2phits_input.slice_range`に分けて記録する。

粗視化、coordinate mode `1`、照射野ガード、CTと加速器の相互排他、線量/MU、
物理条件を変更しない。切り出しを加速器との重なり回避策に流用しない。

根拠が不足する間も、独立したGUI・範囲モデル・合成テストは進められる。
ただし不明な範囲での変換を有効にせず、機能全体が完成したと報告しない。
座標契約の変更や追加の範囲制限が必要なら、根拠と最小の変更案を示して別途判断を求める。
質問は1件ずつ具体的な提案にし、日本語のyes/no形式にする。

実CT、実患者データ、施設固有設定、公式配布物の探索・コピーは実装依頼に含まれない。
実際のct2phits/PHITS等の実行も、対象を指定した別の明示的な依頼が必要。

## 7. 検証と完了条件

人工的な画素を持つ非対称3D CTを用い、異なるX/Y/Z間隔、原点ずれ、ファイル順の
入れ替えを含めて確認する。既存のヘッダーだけのfixtureでは画像表示を検証できない。

- 3断面の軸、Z上下反転、表示倍率、余白、端の画素、両端を含む範囲。
- クリック順逆転、数値同期、残りの軸の保持、画像外クリック、範囲外断面。
- 閲覧と選択の独立、適用/取消/初期化、入力不正、症例変更、実行中の設定固定。
- 単一スライス、画素復号失敗、sliceごとのrescale、メモリー上限、古いworker結果。
- GUI引数、CLI入力、manifestの一致、全範囲時の互換性、全snapshotの不変性。
- X/Yのみ、Zのみ、XYZの偏った切り出しについて、根拠のある格子と位置の期待値。
- 下流Structureの元CTへの結び付きと既存ガードの維持。切り出しに合わせてROIの意味を
  暗黙に変更しない。fake runnerの成功を実ツール互換性の証拠にしない。

関連するfocused testsと合成データでのGUI操作確認の後、以下を実行する。

```text
python -m compileall src
python -m pytest -q -p no:cacheprovider
python tools/verify_public_tree.py
git diff --check
git diff --stat
git status --short
```

ステージ済みの差分には`git diff --cached --check`と`git diff --cached --stat`も使う。
OpenSpec CLIが利用可能ならstrict validation、なければ構造の手動確認と未実施理由を記録する。
コードを変更した後は改めて検証する。下記の計画時テストを実装後の結果に流用しない。

すべての承認済み受入条件と必要な確認が満たされたら、tasksを正しく更新し、
受け入れ済み仕様を`openspec/specs/`へ昇格し、同一ブランチで日付付きarchiveへ移動、
仕様全体を検証する。未解決の座標確認・承認・必要検証が残ればactiveのまま報告する。
レビュー可能なPRで引き渡し、自動merge、force-push、タグ変更はしない。
完了後は任意の改善や別タスクを自動追加しない。

## 8. 計画段階の検証記録と環境

詳細は[計画検証記録](../openspec/changes/add-ct-pixel-clipping/validation.md)を参照。
以下は実装前の結果であり、新機能が動作したという意味ではない。

- 既存`.venv/Scripts/python.exe`はPython 3.12.10でnumpy/pydicom/pytestを利用できる。
- 通常の`python`ではnumpy/pydicom不足による収集エラーがあった。
- 制限内実行ではpytest一時フォルダーのアクセスエラーもあった。
  必要なら対象を限定した通常の権限承認手順を使い、ガードやテストを弱めない。
- 既存環境での`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`は
  **1505 passed, 15 skipped, 1 warning**。警告は重複ZIPメンバーを作るテストによる。
- `python -m compileall src`、公開ツリー監査、Git差分確認は成功。
- OpenSpec CLIは未導入。7要件の構造を確認済み。
- 実ツールによる範囲指定、粗視化、切り出し後の座標は未検証。

## 9. この引き継ぎで追加したファイル

- `docs/ct-clipping-codex-handoff.ja.md`（本書）
- `docs/ct-clipping-codex-prompt.ja.md`（利用者が送信する実装依頼）

この2文書の作成ではコード、テスト、確定済み公開仕様を変更していない。
計画を承認済みに書き換えず、実装・archive・commit・push・PR作成も行っていない。
