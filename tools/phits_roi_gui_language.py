"""Presentation-only translations for the standalone ROI GUI."""
from __future__ import annotations

import tkinter as tk


# Stable source-text keys; values are Japanese and English, respectively.
PAIRS = [
    ("計算済みの線量と相対誤差を、球またはRTSTRUCTの領域で確認します。", "Inspect completed dose and relative error in a sphere or RTSTRUCT region."),
    ("解析元 ZIP / フォルダ（読み取り専用）", "Source ZIP / folder (read only)"),
    ("解析元 ZIP / フォルダ", "Source ZIP / folder"),
    ("ZIPを選択", "Choose ZIP"), ("フォルダを選択", "Choose folder"),
    ("入力した場所を読み込む", "Load entered location"),
    ("解析元の中のファイル（相対パス。候補から選ぶか、選択ボタンで変更）", "Files inside source (relative paths; select a candidate or browse)"),
    ("合算線量 (.out)", "Combined dose (.out)"),
    ("対応する r.err (_err.out)", "Matching r.err (_err.out)"),
    ("保存実行内の同一線量 (必要時)", "Identical dose in saved run (if needed)"),
    ("Sumtally 生成サマリー (JSON)", "Sumtally generation summary (JSON)"),
    ("Sumtally 実行サマリー (JSON)", "Sumtally execution summary (JSON)"),
    ("セグメントマニフェスト (JSON)", "Segment manifest (JSON)"),
    ("PHITS 準備サマリー (RTSTRUCT時のJSON)", "PHITS preparation summary (JSON for RTSTRUCT)"),
    ("選択…", "Browse…"),
    ("準備サマリーは解析元のJSONです。RTSTRUCT本体は下の『RTSTRUCT DICOM』から選択します。", "The preparation summary is a JSON file inside the source. Choose the RTSTRUCT itself under 'RTSTRUCT DICOM' below."),
    ("領域（球またはRTSTRUCT）", "Region (sphere or RTSTRUCT)"),
    ("ケース名", "Case name"), ("球", "Sphere"),
    ("中心 X (cm)", "center x"), ("中心 Y (cm)", "center y"),
    ("中心 Z (cm)", "center z"), ("半径 (cm)", "radius cm"),
    ("標本間隔 (cm)", "sample spacing cm"),
    ("凍結された計算ワークスペース", "Frozen calculation workspace"),
    ("凍結CTの参照DICOM", "Frozen CT reference DICOM"),
    ("RTSTRUCT DICOM（領域輪郭）", "RTSTRUCT DICOM (contours)"),
    ("ファイルを選択", "Choose file"),
    ("ROI番号 / 名前（明示選択）", "ROI number / name (explicit selection)"),
    ("ROI番号", "ROI number"), ("ROIを一覧", "List ROIs"),
    ("ケースを追加", "Add case"), ("選択行を削除", "Remove selected"),
    ("集計する", "Analyse"),
    ("解析元を選び、合算線量と証拠ファイルを指定してください。", "Choose a source, combined dose, and evidence files."),
    ("ケース", "Case"), ("領域", "Region"), ("表示名", "Label"),
    ("状態", "Status"), ("格子点数", "Grid Points"),
    ("平均 cGy", "Mean cGy"), ("セル合計 cGy", "Cell sum cGy"),
    ("最小 cGy", "Min cGy"), ("最大 cGy", "Max cGy"),
    ("空間標準偏差 cGy", "Spatial SD cGy"),
    ("平均 r.err %", "Mean r.err %"), ("P95 r.err %", "P95 r.err %"),
    ("最大 r.err %", "Max r.err %"), ("理由（原文）", "Reason"),
    ("セル合計 = 選択されたPHITSセル線量の単純合計。平均線量は領域平均です。空間標準偏差とセルごとのr.errは異なるばらつきを表します。", "Cell sum = sum of selected native cell dose values; mean dose is the region average. Spatial SD and voxel r.err describe different variations."),
    ("初期球：1 mm標本間隔で81点、換算体積0.081 cm³、幾何体積約0.06545 cm³。PHITS格子点数とは異なります。", "Sphere default: 1 mm sampling gives 81 Points, 0.081 cm³ sample volume; analytic volume ≈0.06545 cm³. Native Grid Points differ."),
    ("保存ファイル名（拡張子なし）", "Report stem"),
    ("CSV + JSON を新規保存", "Save new CSV + JSON"),
    ("自動候補・変更可", "Suggested; editable"),
    ("{count}件を確認。{suggested}欄に標準配置の候補を設定しました。空欄は手で選択してください。", "Found {count} files; suggested {suggested} standard paths. Choose remaining fields manually."),
    ("解析元", "Source"), ("ファイル選択", "File selection"),
    ("先にZIPまたはフォルダを読み込んでください。", "Load a ZIP or folder first."),
    ("すべてのファイル", "All files"),
    ("解析元の中の通常ファイルを選択してください", "Select a regular file inside the source"),
    ("ZIP内のファイルを選択: {label}", "Choose ZIP member: {label}"),
    ("ZIP内の相対パス。検索してから選択できます。重複名は集計できません。", "Relative paths inside ZIP. Search, then select. Duplicate member names cannot be analysed."),
    ("{count}件一致（最大5000件表示）。目的の名前がなければ検索してください。", "{count} matches (up to 5000 shown). Refine the search to find the desired name."),
    ("選択", "Select"), ("キャンセル", "Cancel"),
    ("{label}を選択してください", "Select {label}"),
    ("球またはRTSTRUCTを選択してください", "Select sphere or RTSTRUCT"),
    ("球の中心・半径・間隔を数値で入力してください", "Enter numeric sphere centre, radius, and spacing"),
    ("解析元の一覧を読み込んでください", "Load the source file list"),
    ("解析元から{label}を選択してください", "Select {label} from the source"),
    ("入力を確認してください（詳細原文）：{reason}", "Check the inputs (original diagnostic): {reason}"),
    ("解析元のファイル指定を確認してください", "Check the source file selections"),
    ("入力済み。まず「ケースを追加」を押してください。追加後に「集計する」が有効になります。",
     "Inputs ready. Select Add case first; Analyse becomes available after the case is added."),
    ("ケースを追加済みです。「集計する」を押してください。",
     "Case added. Select Analyse."),
    ("{count}件のROIを表示しました。使用するROIを選択してください。", "{count} ROI choices listed; select one explicitly."),
    ("ケース一覧が変わりました。集計後に結果行を選ぶと詳細を表示します。", "Cases changed. After analysis, select a result row for details."),
    ("{count}件のケースが待機中", "{count} case selections queued"),
    ("解析", "Analysis"), ("ケースを1件以上追加してください", "Add at least one explicit case"),
    ("選択されたケースを集計中…", "Analysing selected cases..."),
    ("{count}件の結果。不正なStructure入力を球で代用することはありません。", "{count} results; invalid Structure inputs never fall back to a sphere"),
    ("標本点数 {points}；換算体積 {sample} cm³；球の幾何体積 {analytic} cm³；PHITS格子点数 {grid}；格子体積 {volume} cm³。", "Sampling Points {points}; sample volume {sample} cm³; analytic sphere volume {analytic} cm³; native Grid Points {grid}; grid volume {volume} cm³."),
    ("PHITS格子点数 {grid}；格子体積 {volume} cm³。ROINameは表示名です。CT・計画・格子の証拠から対象セルを決定します。", "Native Grid Points {grid}; grid volume {volume} cm³. ROIName is a label; CT/plan/mesh evidence determines cell membership."),
    ("レポート", "Report"), ("保存前に集計してください", "Analyse cases before export"),
    ("解析元とリポジトリ以外の既存フォルダを選択", "Choose an existing folder outside case sources and repository"),
    ("新しいレポートを保存しました: {names}", "Published new reports: {names}"),
    ("選択内容", "Selection"), ("ケース数の上限です", "case limit"),
]
MESSAGES = {key: {"ja": ja, "en": en} for ja, en in PAIRS for key in (ja, en)}


def translate(key: str, language: str = "ja", **values) -> str:
    return MESSAGES.get(key, {}).get(language, key).format(**values)


class DisplayText(tk.StringVar):
    """Retain the message template, never translated input or result data."""

    def __init__(self, master, language, value=""):
        self.language = language
        self.message = value
        self.values = {}
        super().__init__(master, value=translate(value, language.get()))

    def set(self, value, **values):
        self.message, self.values = value, values
        self.refresh()

    def refresh(self):
        super().set(translate(self.message, self.language.get(), **self.values))
