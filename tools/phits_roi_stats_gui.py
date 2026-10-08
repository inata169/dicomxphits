"""Independent desktop selector for completed PHITS ROI statistics.

Run with ``.venv/Scripts/python.exe tools/phits_roi_stats_gui.py``.
No PHITS, Sumtally, DICOM conversion, or public workflow action is launched.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from zipfile import BadZipFile

import pydicom

import phits_roi_stats as roi
from phits_roi_gui_language import DisplayText, translate


MEMBERS = {
    "dose": ("合算線量 (.out)", lambda n: n.endswith(".out") and not n.endswith("_err.out")),
    "error": ("対応する r.err (_err.out)", lambda n: n.endswith("_err.out")),
    "retained_dose": ("保存実行内の同一線量 (必要時)", lambda n: n.endswith(".out") and not n.endswith("_err.out")),
    "generation": ("Sumtally 生成サマリー (JSON)", lambda n: n.endswith(".json")),
    "execution": ("Sumtally 実行サマリー (JSON)", lambda n: n.endswith(".json")),
    "manifest": ("セグメントマニフェスト (JSON)", lambda n: n.endswith(".json")),
    "preparation": ("PHITS 準備サマリー (RTSTRUCT時のJSON)", lambda n: n.endswith(".json")),
}
REQUIRED = ("dose", "error", "generation", "execution", "manifest")
COMBINED_NAME = "deposit-target-3D_sum_all_active_segments_totalfield.out"
COMBINED_ERROR_NAME = COMBINED_NAME.removesuffix(".out") + "_err.out"


def configure_style(root: tk.Misc) -> None:
    """Use the established dicomxphits navy/cyan palette."""
    navy, deep, surface = "#071A2B", "#061521", "#0B2740"
    text, muted, cyan, line = "#F4F8FC", "#A9BED1", "#2EA8FF", "#264A67"
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=navy)
    root.option_add("*TCombobox*Listbox.background", deep)
    root.option_add("*TCombobox*Listbox.foreground", text)
    root.option_add("*TCombobox*Listbox.selectBackground", "#0C4A8A")
    style.configure(".", background=navy, foreground=text, font=("Segoe UI", 10))
    style.configure("TFrame", background=navy)
    style.configure("TLabel", background=navy, foreground=text)
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground=text)
    style.configure("Muted.TLabel", foreground=muted, font=("Segoe UI", 9))
    style.configure("TLabelframe", background=navy, bordercolor=line, relief="solid")
    style.configure("TLabelframe.Label", foreground=cyan, background=navy,
                    font=("Segoe UI Semibold", 10))
    for name in ("TEntry", "TCombobox"):
        style.configure(name, fieldbackground=deep, background=surface, foreground=text,
                        insertcolor=text, arrowcolor=cyan, bordercolor=line,
                        lightcolor=line, darkcolor=line, padding=5)
        style.map(name, fieldbackground=[("readonly", surface)],
                  foreground=[("readonly", text)], bordercolor=[("focus", cyan)])
    style.configure("TButton", background=surface, foreground=text, bordercolor=line,
                    lightcolor=line, darkcolor=line, padding=(10, 6), font=("Segoe UI Semibold", 10))
    style.map("TButton", background=[("disabled", navy), ("active", "#0C4A8A")],
              foreground=[("disabled", muted)])
    style.configure("Primary.TButton", background="#0C4A8A", bordercolor=cyan)
    style.map("Primary.TButton", background=[("disabled", surface), ("active", "#168FF2")])
    style.configure("TRadiobutton", background=navy, foreground=text)
    style.map("TRadiobutton", background=[("active", surface)])
    style.configure("Treeview", background=deep, fieldbackground=deep, foreground=text,
                    rowheight=30, bordercolor=line)
    style.configure("Treeview.Heading", background=surface, foreground=cyan,
                    font=("Segoe UI Semibold", 10), padding=6)
    style.map("Treeview", background=[("selected", "#0C4A8A")], foreground=[("selected", text)])
    style.map("Treeview.Heading", background=[("active", "#0D3151")])


def source_members(location: str) -> list[str]:
    """List safe names only; selected members are still checked by Source.read."""
    source = roi.Source(location)
    if source.archive:
        with source.open_zip() as archive:
            infos = archive.infolist()
            roi.need(len(infos) <= 50_000, "too many ZIP members")
            names = [item.filename for item in infos if not item.is_dir()]
    else:
        names = []
        for item in source.path.rglob("*"):
            roi.need(len(names) <= 50_000, "too many source files")
            if item.is_file() and not item.is_symlink():
                names.append(item.relative_to(source.path).as_posix())
    safe = []
    for name in names:
        try:
            safe.append(roi.relative_name(name))
        except roi.AnalysisError:
            continue
    return sorted(safe)


def candidates_from_members(names: list[str]) -> dict[str, list[str]]:
    return {key: sorted({name for name in names if predicate(name.lower())})
            for key, (_, predicate) in MEMBERS.items()}


def candidate_members(location: str) -> dict[str, list[str]]:
    return candidates_from_members(source_members(location))


def canonical_suggestions(names: list[str]) -> dict[str, str]:
    """Suggest only unambiguous conventional paths, without trusting their contents."""
    counts = Counter(names)
    def one(parent: str, basename: str) -> str | None:
        found = [name for name in names if PurePosixPath(name).parent.name.lower() == parent
                 and PurePosixPath(name).name.lower() == basename.lower()]
        return found[0] if len(found) == 1 else None

    suggested = {}
    for key, parent, basename in (
        ("generation", "analysis", "sumtally_generation_summary.json"),
        ("execution", "analysis", "sumtally_execution_summary.json"),
        ("manifest", "segments", "segment_manifest.json"),
        ("preparation", "analysis", "public_preparation_workspace_summary.json"),
    ):
        match = one(parent, basename)
        if match:
            suggested[key] = match
    dose = one("sumtally", COMBINED_NAME)
    if not dose:
        return suggested
    suggested["dose"] = dose
    expected_error = str(PurePosixPath(dose).with_name(COMBINED_ERROR_NAME))
    if counts[expected_error] == 1:
        suggested["error"] = expected_error
        return suggested
    if counts[expected_error] > 1:
        return suggested
    run_pairs = []
    for name in names:
        path = PurePosixPath(name)
        if path.name.lower() != COMBINED_ERROR_NAME.lower() or not path.parent.name.lower().startswith(".sumtally-run-"):
            continue
        retained = str(path.with_name(COMBINED_NAME))
        if counts[name] == 1 and counts[retained] == 1:
            run_pairs.append((name, retained))
    if len(run_pairs) == 1:
        suggested["error"], suggested["retained_dose"] = run_pairs[0]
    return suggested


def roi_choices(path: str) -> list[tuple[int, str]]:
    roi.ordinary_path(Path(path))
    dataset = pydicom.dcmread(path, stop_before_pixels=True, force=False)
    roi.need(str(getattr(dataset, "Modality", "")) == "RTSTRUCT", "selected DICOM is not RTSTRUCT")
    choices = []
    seen = set()
    for item in getattr(dataset, "StructureSetROISequence", ()):
        number = int(item.ROINumber)
        roi.need(number > 0 and number not in seen, "RTSTRUCT has duplicate or invalid ROI numbers")
        seen.add(number)
        choices.append((number, str(getattr(item, "ROIName", "") or f"ROI {number}")))
    return choices


def case_from_fields(values: dict[str, str], language: str = "ja") -> dict:
    """Snapshot only explicit selections; blank optional fields stay absent."""
    def tr(key, **args):
        return translate(key, language, **args)

    for key in ("source", *REQUIRED):
        label = "解析元 ZIP / フォルダ" if key == "source" else MEMBERS[key][0]
        roi.need(bool(values.get(key, "").strip()), tr("{label}を選択してください", label=tr(label)))
    kind = values.get("region_type", "sphere")
    roi.need(kind in {"sphere", "rtstruct"}, tr("球またはRTSTRUCTを選択してください"))
    case = {key: values[key].strip() for key in ("source", *REQUIRED)}
    case["case_label"] = values.get("case_label", "").strip() or "case"
    case["region_type"] = kind
    if values.get("retained_dose", "").strip():
        case["retained_dose"] = values["retained_dose"].strip()
    if kind == "sphere":
        try:
            case["center_cm"] = [float(values[f"center_{axis}"]) for axis in "xyz"]
            case["radius_cm"] = float(values["radius_cm"])
            case["sample_spacing_cm"] = float(values["sample_spacing_cm"])
        except (KeyError, ValueError) as exc:
            raise roi.AnalysisError(tr("球の中心・半径・間隔を数値で入力してください")) from exc
        case["region_label"] = "central sphere"
    else:
        for key in ("preparation", "workspace", "ct_reference", "rtplan", "rtstruct", "roi_number"):
            labels = {"preparation": MEMBERS["preparation"][0],
                      "workspace": "凍結された計算ワークスペース", "ct_reference": "凍結CTの参照DICOM",
                      "rtplan": "RTPLAN DICOM", "rtstruct": "RTSTRUCT DICOM", "roi_number": "ROI番号"}
            roi.need(bool(values.get(key, "").strip()), tr("{label}を選択してください", label=tr(labels[key])))
            case[key] = values[key].strip()
        case["region_label"] = "RT Structure ROI"
    return case


def table_row(result: dict) -> tuple[str, ...]:
    def value(key: str) -> str:
        item = result.get(key)
        if item is None:
            return ""
        return f"{item:.5g}" if isinstance(item, float) else str(item)
    return tuple(value(key) for key in (
        "case_label", "region_type", "region_label", "status", "grid_points",
        "mean_dose_cgy", "voxel_dose_sum_cgy", "min_dose_cgy", "max_dose_cgy",
        "spatial_stddev_cgy", "mean_voxel_rerr_percent", "p95_voxel_rerr_percent",
        "max_voxel_rerr_percent", "reason",
    ))


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        configure_style(master.winfo_toplevel())
        super().__init__(master, padding=12)
        self.pack(fill="both", expand=True)
        self.language = tk.StringVar(self, value="ja")
        self.display_texts = []
        self.fields = {key: tk.StringVar() for key in (
            "source", "case_label", *MEMBERS, "region_type", "center_x", "center_y", "center_z",
            "radius_cm", "sample_spacing_cm", "workspace", "ct_reference", "rtplan", "rtstruct",
            "roi_number", "report_stem",
        )}
        self.fields["region_type"].set("sphere")
        for key, value in (("center_x", "0"), ("center_y", "0"), ("center_z", "0"),
                           ("radius_cm", "0.25"), ("sample_spacing_cm", "0.1"),
                           ("case_label", "case"), ("report_stem", "phits-roi-statistics")):
            self.fields[key].set(value)
        self.cases: list[dict] = []
        self.results: list[dict] = []
        self.all_members: list[str] = []
        self.loaded_source = ""
        self.hints = {key: self._text("") for key in MEMBERS}
        self.busy = False
        self.events: queue.Queue = queue.Queue()
        self._build()
        self._build_language_menu()
        self._change_language()
        for variable in self.fields.values():
            variable.trace_add("write", lambda *_args: self._refresh_state())
        for key in MEMBERS:
            self.fields[key].trace_add("write", lambda *_args, k=key: self.hints[k].set(""))
        self.fields["rtstruct"].trace_add("write", lambda *_args: self._clear_roi())
        self._refresh_state()
        self.after(100, self._poll)

    def _tr(self, key: str, **values) -> str:
        return translate(key, self.language.get(), **values)

    def _text(self, key: str) -> DisplayText:
        value = DisplayText(self, self.language, key)
        self.display_texts.append(value)
        return value

    def _build_language_menu(self) -> None:
        self.menu = tk.Menu(self.winfo_toplevel(), tearoff=False)
        self.language_menu = tk.Menu(self.menu, tearoff=False)
        for label, value in (("日本語", "ja"), ("English", "en")):
            self.language_menu.add_radiobutton(label=label, variable=self.language,
                                              value=value, command=self._change_language)
        self.menu.add_cascade(label="表示言語 / Language", menu=self.language_menu)
        self.winfo_toplevel().configure(menu=self.menu)

    def _change_language(self) -> None:
        # Only presentation is updated: never write fields or rebuild the table.
        for value in self.display_texts:
            value.refresh()
        for column in self.table["columns"]:
            self.table.heading(column, text=self._tr(column))
        self._refresh_state()

    def _build(self) -> None:
        ttk.Label(self, textvariable=self._text("dicomxphits  /  ROI Statistics"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, textvariable=self._text("計算済みの線量と相対誤差を、球またはRTSTRUCTの領域で確認します。"),
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 14))
        top = ttk.LabelFrame(self, labelwidget=ttk.Label(self, textvariable=self._text("解析元 ZIP / フォルダ（読み取り専用）"), foreground="#2EA8FF"), padding=8)
        top.pack(fill="x")
        ttk.Entry(top, textvariable=self.fields["source"]).pack(side="left", fill="x", expand=True)
        ttk.Button(top, textvariable=self._text("ZIPを選択"), command=lambda: self._source(False)).pack(side="left", padx=3)
        ttk.Button(top, textvariable=self._text("フォルダを選択"), command=lambda: self._source(True)).pack(side="left")
        ttk.Button(top, textvariable=self._text("入力した場所を読み込む"), command=lambda: self._load_source(
            self.fields["source"].get())).pack(side="left", padx=3)
        selectors = ttk.LabelFrame(self, labelwidget=ttk.Label(self, textvariable=self._text("解析元の中のファイル（相対パス。候補から選ぶか、選択ボタンで変更）"), foreground="#2EA8FF"), padding=8)
        selectors.pack(fill="x", pady=5)
        self.combos = {}
        for index, (key, (title, _)) in enumerate(MEMBERS.items()):
            ttk.Label(selectors, textvariable=self._text(title)).grid(row=index, column=0, sticky="w", pady=2)
            combo = ttk.Combobox(selectors, textvariable=self.fields[key], state="normal", values=[])
            combo.grid(row=index, column=1, sticky="ew", padx=6, pady=2)
            self.combos[key] = combo
            ttk.Button(selectors, textvariable=self._text("選択…"), command=lambda k=key: self._member(k)).grid(
                row=index, column=2, sticky="w", pady=2)
            ttk.Label(selectors, textvariable=self.hints[key]).grid(row=index, column=3, sticky="w", padx=4)
        selectors.columnconfigure(1, weight=1)
        ttk.Label(selectors, textvariable=self._text("準備サマリーは解析元のJSONです。RTSTRUCT本体は下の『RTSTRUCT DICOM』から選択します。"),
                  wraplength=1050).grid(row=len(MEMBERS), column=0, columnspan=4, sticky="w", pady=(6, 0))
        region = ttk.LabelFrame(self, labelwidget=ttk.Label(self, textvariable=self._text("領域（球またはRTSTRUCT）"), foreground="#2EA8FF"), padding=8)
        region.pack(fill="x", pady=5)
        ttk.Label(region, textvariable=self._text("ケース名")).grid(row=0, column=0, sticky="w")
        ttk.Entry(region, textvariable=self.fields["case_label"], width=20).grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(region, textvariable=self._text("球"), variable=self.fields["region_type"], value="sphere").grid(row=0, column=2)
        ttk.Radiobutton(region, textvariable=self._text("RTSTRUCT"), variable=self.fields["region_type"], value="rtstruct").grid(row=0, column=3)
        for index, key in enumerate(("center_x", "center_y", "center_z", "radius_cm", "sample_spacing_cm")):
            ttk.Label(region, textvariable=self._text(key.replace("_", " "))).grid(row=1, column=index*2, sticky="w")
            ttk.Entry(region, textvariable=self.fields[key], width=8).grid(row=1, column=index*2+1, padx=2)
        for index, (key, title, directory) in enumerate((
            ("workspace", "凍結された計算ワークスペース", True), ("ct_reference", "凍結CTの参照DICOM", False),
            ("rtplan", "RTPLAN DICOM", False), ("rtstruct", "RTSTRUCT DICOM（領域輪郭）", False))):
            ttk.Label(region, textvariable=self._text(title)).grid(row=index+2, column=0, columnspan=2, sticky="w")
            ttk.Entry(region, textvariable=self.fields[key]).grid(row=index+2, column=2, columnspan=6, sticky="ew")
            ttk.Button(region, textvariable=self._text("ファイルを選択" if not directory else "フォルダを選択"),
                       command=lambda k=key, d=directory: self._external(k, d)).grid(row=index+2, column=8)
        ttk.Label(region, textvariable=self._text("ROI番号 / 名前（明示選択）")).grid(row=6, column=0, columnspan=2, sticky="w")
        self.roi_combo = ttk.Combobox(region, state="readonly", values=[])
        self.roi_combo.grid(row=6, column=2, columnspan=6, sticky="ew")
        self.roi_combo.bind("<<ComboboxSelected>>", lambda _e: self.fields["roi_number"].set(self.roi_combo.get().split(" | ", 1)[0]))
        ttk.Button(region, textvariable=self._text("ROIを一覧"), command=self._list_rois).grid(row=6, column=8)
        for column in range(2, 8):
            region.columnconfigure(column, weight=1)
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=5)
        self.add_button = ttk.Button(actions, textvariable=self._text("ケースを追加"), command=self._add)
        self.add_button.pack(side="left")
        self.remove_button = ttk.Button(actions, textvariable=self._text("選択行を削除"), command=self._remove)
        self.remove_button.pack(side="left", padx=4)
        self.run_button = ttk.Button(actions, textvariable=self._text("集計する"), command=self._run, style="Primary.TButton")
        self.run_button.pack(side="left", padx=4)
        self.run_button.configure(state="disabled")
        self.status = self._text("解析元を選び、合算線量と証拠ファイルを指定してください。")
        ttk.Label(actions, textvariable=self.status).pack(side="left", padx=10)
        self.input_state = tk.StringVar()
        ttk.Label(self, textvariable=self.input_state, wraplength=1100).pack(fill="x")
        columns = ("Case", "Region", "Label", "Status", "Grid Points", "Mean cGy", "Cell sum cGy",
                   "Min cGy", "Max cGy", "Spatial SD cGy", "Mean r.err %", "P95 r.err %", "Max r.err %", "Reason")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=6, selectmode="browse")
        for title in columns:
            self.table.heading(title, text=self._tr(title))
            self.table.column(title, width=125 if title not in {"Label", "Reason"} else 240,
                              stretch=False)
        self.table.pack(side="top", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.table.xview)
        scrollbar.pack(fill="x")
        self.table.configure(xscrollcommand=scrollbar.set)
        ttk.Label(self, textvariable=self._text("Cell sum = sum of selected native cell dose values; mean dose is the region average. "
                  "Spatial SD and voxel r.err describe different variations."), wraplength=1100).pack(fill="x", pady=4)
        self.details = self._text("Sphere default: 1 mm sampling gives 81 Points, 0.081 cm³ sample volume; analytic volume ≈0.06545 cm³. Native Grid Points differ.")
        ttk.Label(self, textvariable=self.details, wraplength=1100).pack(fill="x")
        export = ttk.Frame(self)
        export.pack(fill="x", pady=5)
        ttk.Label(export, textvariable=self._text("Report stem")).pack(side="left")
        ttk.Entry(export, textvariable=self.fields["report_stem"], width=28).pack(side="left", padx=4)
        self.export_button = ttk.Button(export, textvariable=self._text("CSV + JSON を新規保存"), command=self._export)
        self.export_button.pack(side="left")
        self.table.bind("<<TreeviewSelect>>", self._details)

    def _source(self, folder: bool) -> None:
        path = filedialog.askdirectory() if folder else filedialog.askopenfilename(filetypes=[("ZIP", "*.zip")])
        if path:
            self._load_source(path)

    def _load_source(self, path: str) -> None:
        try:
            names = source_members(path)
            members = candidates_from_members(names)
            suggested = canonical_suggestions(names)
        except (OSError, ValueError, BadZipFile) as exc:
            messagebox.showerror(self._tr("解析元"), self._tr("入力を確認してください（詳細原文）：{reason}", reason=str(exc)))
            return
        self.loaded_source = str(roi.Source(path).path)
        self.all_members = names
        self.fields["source"].set(self.loaded_source)
        for key, combo in self.combos.items():
            self.fields[key].set("")
            combo.configure(values=members[key])
            self.hints[key].set("")
            if key in suggested:
                self.fields[key].set(suggested[key])
                self.hints[key].set("自動候補・変更可")
        self.status.set("{count}件を確認。{suggested}欄に標準配置の候補を設定しました。空欄は手で選択してください。",
                        count=len(names), suggested=len(suggested))
        self._refresh_state()

    def _member(self, key: str) -> None:
        if not self.loaded_source or self.fields["source"].get() != self.loaded_source:
            messagebox.showinfo(self._tr("解析元"), self._tr("先にZIPまたはフォルダを読み込んでください。"))
            return
        source = roi.Source(self.loaded_source)
        if not source.archive:
            selected = filedialog.askopenfilename(initialdir=str(source.path), filetypes=[(self._tr("すべてのファイル"), "*")])
            if not selected:
                return
            try:
                roi.ordinary_path(Path(selected))
                relative = Path(selected).resolve().relative_to(source.path.resolve()).as_posix()
                relative = roi.relative_name(relative)
                roi.need(self.all_members.count(relative) == 1, self._tr("解析元の中の通常ファイルを選択してください"))
            except (OSError, ValueError) as exc:
                messagebox.showerror(self._tr("ファイル選択"), self._tr("入力を確認してください（詳細原文）：{reason}", reason=str(exc)))
                return
            self.fields[key].set(relative)
            return
        dialog = tk.Toplevel(self)
        dialog.configure(background="#071A2B")
        dialog.title(self._tr("ZIP内のファイルを選択: {label}", label=self._tr(MEMBERS[key][0])))
        dialog.geometry("900x500")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ttk.Label(dialog, textvariable=self._text("ZIP内の相対パス。検索してから選択できます。重複名は集計できません。")).pack(
            fill="x", padx=8, pady=4)
        query = tk.StringVar()
        ttk.Entry(dialog, textvariable=query).pack(fill="x", padx=8, pady=4)
        box_frame = ttk.Frame(dialog)
        box_frame.pack(fill="both", expand=True, padx=8)
        box = tk.Listbox(box_frame, selectmode="browse", background="#061521",
                         foreground="#F4F8FC", selectbackground="#0C4A8A", relief="flat")
        box.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(box_frame, orient="vertical", command=box.yview)
        scroll.pack(side="right", fill="y")
        box.configure(yscrollcommand=scroll.set)
        count = tk.StringVar()
        ttk.Label(dialog, textvariable=count).pack(fill="x", padx=8)
        available = sorted(name for name, amount in Counter(self.all_members).items() if amount == 1)
        visible: list[str] = []

        def refresh(*_args) -> None:
            visible.clear()
            needle = query.get().casefold()
            matches = [name for name in available if needle in name.casefold()]
            visible.extend(matches[:5000])
            box.delete(0, "end")
            for name in visible:
                box.insert("end", name)
            count.set(self._tr("{count}件一致（最大5000件表示）。目的の名前がなければ検索してください。", count=len(matches)))

        def accept(*_args) -> None:
            selection = box.curselection()
            if selection:
                self.fields[key].set(visible[selection[0]])
                dialog.destroy()

        query.trace_add("write", refresh)
        refresh()
        box.bind("<Double-Button-1>", accept)
        buttons = ttk.Frame(dialog)
        buttons.pack(pady=6)
        ttk.Button(buttons, textvariable=self._text("選択"), command=accept).pack(side="left", padx=4)
        ttk.Button(buttons, textvariable=self._text("キャンセル"), command=dialog.destroy).pack(side="left", padx=4)

    def _refresh_state(self) -> None:
        try:
            case = case_from_fields({key: var.get() for key, var in self.fields.items()}, self.language.get())
            roi.need(case["source"] == self.loaded_source, self._tr("解析元の一覧を読み込んでください"))
            roi.Source(case["source"])
            for key in REQUIRED:
                roi.need(self.all_members.count(case[key]) == 1, self._tr("解析元から{label}を選択してください", label=self._tr(MEMBERS[key][0])))
            if case.get("retained_dose"):
                roi.need(self.all_members.count(case["retained_dose"]) == 1,
                         self._tr("解析元から{label}を選択してください", label=self._tr(MEMBERS["retained_dose"][0])))
            if case["region_type"] == "rtstruct":
                roi.need(Path(case["workspace"]).is_dir(), self._tr("{label}を選択してください", label=self._tr("凍結された計算ワークスペース")))
                for key in ("ct_reference", "rtplan", "rtstruct"):
                    roi.need(Path(case[key]).is_file(), self._tr("{label}を選択してください", label=self._tr({"ct_reference": "凍結CTの参照DICOM", "rtplan": "RTPLAN DICOM", "rtstruct": "RTSTRUCT DICOM"}[key])))
                roi.need(self.all_members.count(case["preparation"]) == 1,
                         self._tr("解析元から{label}を選択してください", label=self._tr(MEMBERS["preparation"][0])))
        except (OSError, KeyError, ValueError) as exc:
            ready = False
            self.input_state.set(self._tr("入力を確認してください（詳細原文）：{reason}", reason=str(exc))
                                 if isinstance(exc, roi.AnalysisError)
                                 else self._tr("解析元のファイル指定を確認してください"))
        else:
            ready = True
            self.input_state.set(self._tr("入力済み。ケースを追加できます。"))
        self.add_button.configure(state="normal" if ready and not self.busy else "disabled")
        self.run_button.configure(state="normal" if self.cases and not self.busy else "disabled")
        self.remove_button.configure(state="normal" if self.cases and not self.busy else "disabled")
        self.export_button.configure(state="normal" if self.results and not self.busy else "disabled")

    def _external(self, key: str, folder: bool) -> None:
        path = filedialog.askdirectory() if folder else filedialog.askopenfilename()
        if path:
            self.fields[key].set(path)

    def _clear_roi(self) -> None:
        self.fields["roi_number"].set("")
        self.roi_combo.set("")
        self.roi_combo.configure(values=[])

    def _list_rois(self) -> None:
        try:
            choices = roi_choices(self.fields["rtstruct"].get())
        except Exception as exc:
            messagebox.showerror(self._tr("RT Structure"), self._tr("入力を確認してください（詳細原文）：{reason}", reason=str(exc)))
            return
        self.roi_combo.configure(values=[f"{number} | {name}" for number, name in choices])
        self.status.set("{count} ROI choices listed; select one explicitly.", count=len(choices))

    def _add(self) -> None:
        try:
            case = case_from_fields({key: var.get() for key, var in self.fields.items()}, self.language.get())
            roi.Source(case["source"])
            roi.need(len(self.cases) < roi.MAX_CASES, self._tr("case limit"))
        except (OSError, ValueError) as exc:
            messagebox.showerror(self._tr("Selection"), self._tr("入力を確認してください（詳細原文）：{reason}", reason=str(exc)))
            return
        self.cases.append(case)
        self.results = []
        self.details.set("ケース一覧が変わりました。集計後に結果行を選ぶと詳細を表示します。")
        self.table.insert("", "end", values=(case["case_label"], case["region_type"], case["region_label"], "queued"))
        self.status.set("{count} case selections queued", count=len(self.cases))
        self._refresh_state()

    def _remove(self) -> None:
        if self.busy:
            return
        chosen = self.table.selection()
        if not chosen:
            return
        index = self.table.index(chosen[0])
        self.table.delete(chosen[0])
        self.cases.pop(index)
        self.results = []
        self.details.set("ケース一覧が変わりました。集計後に結果行を選ぶと詳細を表示します。")
        self.status.set("{count} case selections queued", count=len(self.cases))
        self._refresh_state()

    def _run(self) -> None:
        if self.busy:
            return
        if not self.cases:
            messagebox.showinfo(self._tr("Analysis"), self._tr("Add at least one explicit case"))
            return
        snapshot = [dict(case) for case in self.cases]
        self.busy = True
        self._refresh_state()
        self.status.set("Analysing selected cases...")
        threading.Thread(target=self._worker, args=(snapshot,), daemon=True).start()

    def _worker(self, cases: list[dict]) -> None:
        rows = []
        for case in cases:
            try:
                row = roi.analyse(case)
            except Exception as exc:
                row = {"case_label": case["case_label"], "region_type": case["region_type"],
                       "region_label": case["region_label"], "status": "invalid",
                       "reason": str(exc) if isinstance(exc, roi.AnalysisError)
                       else "selected inputs are unavailable or invalid"}
            rows.append(row)
        self.events.put(rows)

    def _poll(self) -> None:
        try:
            rows = self.events.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        self.results = rows
        self.table.delete(*self.table.get_children())
        for row in rows:
            self.table.insert("", "end", values=table_row(row))
        self.busy = False
        self._refresh_state()
        self.status.set("{count} results; invalid Structure inputs never fall back to a sphere", count=len(rows))
        self.after(100, self._poll)

    def _details(self, _event) -> None:
        chosen = self.table.selection()
        if not chosen or not self.results:
            return
        row = self.results[self.table.index(chosen[0])]
        def value(key: str) -> str:
            number = row.get(key)
            return f"{number:.6g}" if isinstance(number, (int, float)) else "—"
        if row.get("region_type") == "sphere":
            self.details.set("Sampling Points {points}; sample volume {sample} cm³; analytic sphere volume {analytic} cm³; native Grid Points {grid}; grid volume {volume} cm³.",
                             points=value("sample_points"), sample=value("sampling_volume_cm3"),
                             analytic=value("analytic_volume_cm3"), grid=value("grid_points"),
                             volume=value("grid_volume_cm3"))
        else:
            self.details.set("Native Grid Points {grid}; grid volume {volume} cm³. ROIName is a label; CT/plan/mesh evidence determines cell membership.",
                             grid=value("grid_points"), volume=value("grid_volume_cm3"))

    def _export(self) -> None:
        if self.busy:
            return
        if not self.results:
            messagebox.showinfo(self._tr("Report"), self._tr("Analyse cases before export"))
            return
        folder = filedialog.askdirectory(title=self._tr("Choose an existing folder outside case sources and repository"))
        if not folder:
            return
        try:
            sources = [roi.Source(case["source"]) for case in self.cases]
            extra = tuple(case[key] for case in self.cases for key in
                          ("workspace", "ct_reference", "rtplan", "rtstruct") if case.get(key))
            names = roi.publish(self.results, folder, self.fields["report_stem"].get(), sources, extra)
        except (OSError, ValueError) as exc:
            messagebox.showerror(self._tr("Report"), self._tr("入力を確認してください（詳細原文）：{reason}", reason=str(exc)))
            return
        self.status.set("Published new reports: {names}", names=", ".join(names))


def main() -> None:
    root = tk.Tk()
    root.title("dicomxphits — ROI Statistics")
    root.geometry("1400x980")
    root.minsize(1100, 700)
    try:
        root.state("zoomed")
    except tk.TclError:
        pass
    canvas = tk.Canvas(root, background="#071A2B", highlightthickness=0)
    scroll = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    app = App(canvas)
    item = canvas.create_window(0, 0, window=app, anchor="nw")
    app.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
    root.mainloop()


if __name__ == "__main__":
    main()
