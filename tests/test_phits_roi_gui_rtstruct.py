"""Only project-authored synthetic inputs exercise the standalone GUI adapter."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tkinter as tk
from types import SimpleNamespace
from zipfile import ZipFile

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset

from dicomxphits.phits_observation_format import Mesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phits_roi_stats as roi  # noqa: E402
import phits_roi_stats_gui as gui  # noqa: E402
import phits_roi_rtstruct as adapter  # noqa: E402
from test_replace_ct_layer_with_water import (  # noqa: E402
    _file_dataset, _save_dataset, _sha256, _write_ct_series, _write_rtstruct,
)
from test_phits_roi_stats import fixture as tally_fixture  # noqa: E402
from dicomxphits.ct2phits_datfiles import RAW_CT2PHITS_NAMES  # noqa: E402


def _rtstruct(path: Path, *, outside: bool = False) -> None:
    sop = pydicom.uid.generate_uid(prefix=None)
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = pydicom.uid.RTStructureSetStorage
    meta.MediaStorageSOPInstanceUID = sop
    meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = pydicom.uid.RTStructureSetStorage
    dataset.SOPInstanceUID = sop
    dataset.Modality = "RTSTRUCT"
    roi_item = Dataset()
    roi_item.ROINumber = 7
    roi_item.ROIName = "Chamber"
    dataset.StructureSetROISequence = [roi_item]
    contour_item = Dataset()
    contour_item.ReferencedROINumber = 7
    contour = Dataset()
    value = 50.0 if outside else 0.0
    contour.ContourData = [value, 0, 0, value, 1, 0, value, 1, 1]
    contour_item.ContourSequence = [contour]
    dataset.ROIContourSequence = [contour_item]
    dataset.save_as(path, enforce_file_format=True)


def _fields(tmp_path: Path) -> dict[str, str]:
    return {"source": str(tmp_path), "dose": "official/dose.out",
            "error": "official/dose_err.out", "generation": "analysis/generation.json",
            "execution": "analysis/execution.json", "manifest": "segments/manifest.json",
            "case_label": "synthetic", "region_type": "sphere", "center_x": "0",
            "center_y": "0", "center_z": "0", "radius_cm": "0.25",
            "sample_spacing_cm": "0.1"}


def test_explicit_member_selectors_and_sphere_defaults(tmp_path: Path) -> None:
    source = tmp_path / "case.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("one/dose.out", "synthetic")
        archive.writestr("two/dose.out", "synthetic")
        archive.writestr("one/dose_err.out", "synthetic")
        archive.writestr("analysis/sumtally_generation_summary.json", "{}")
    candidates = gui.candidate_members(str(source))
    assert candidates["dose"] == ["one/dose.out", "two/dose.out"]
    assert candidates["error"] == ["one/dose_err.out"]
    values = _fields(tmp_path)
    with pytest.raises(roi.AnalysisError, match="合算線量"):
        gui.case_from_fields({**values, "dose": ""})
    case = gui.case_from_fields(values)
    assert case["center_cm"] == [0, 0, 0]
    assert case["radius_cm"] == .25
    assert case["sample_spacing_cm"] == .1
    assert "rtstruct" not in case


def test_canonical_suggestions_and_ambiguous_saved_runs() -> None:
    root = "case"
    dose = f"{root}/sumtally/{gui.COMBINED_NAME}"
    error = dose.removesuffix(".out") + "_err.out"
    basics = [dose, f"{root}/analysis/sumtally_generation_summary.json",
              f"{root}/analysis/sumtally_execution_summary.json",
              f"{root}/analysis/public_preparation_workspace_summary.json",
              f"{root}/segments/segment_manifest.json"]
    result = gui.canonical_suggestions(basics + [error])
    assert result["dose"] == dose and result["error"] == error
    assert "retained_dose" not in result
    assert set(result) == {"dose", "error", "generation", "execution", "manifest", "preparation"}
    saved_one = f"{root}/.sumtally-run-one/{gui.COMBINED_NAME}"
    saved_one_err = saved_one.removesuffix(".out") + "_err.out"
    saved_two = f"{root}/.sumtally-run-two/{gui.COMBINED_NAME}"
    saved_two_err = saved_two.removesuffix(".out") + "_err.out"
    saved = gui.canonical_suggestions(basics + [saved_one, saved_one_err])
    assert saved["error"] == saved_one_err and saved["retained_dose"] == saved_one
    ambiguous = gui.canonical_suggestions(basics + [saved_one, saved_one_err, saved_two, saved_two_err])
    assert ambiguous["dose"] == dose
    assert "error" not in ambiguous and "retained_dose" not in ambiguous
    assert "dose" not in gui.canonical_suggestions(basics + [dose])
    assert "generation" not in gui.canonical_suggestions(
        basics + [f"other/analysis/sumtally_generation_summary.json"])


def test_gui_suggestions_are_editable_and_source_change_clears_stale_values(
    tmp_path: Path,
) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    with ZipFile(first, "w") as archive:
        for name in (f"case/sumtally/{gui.COMBINED_NAME}",
                     f"case/sumtally/{gui.COMBINED_ERROR_NAME}",
                     "case/analysis/sumtally_generation_summary.json",
                     "case/analysis/sumtally_execution_summary.json",
                     "case/segments/segment_manifest.json", "case/other.out"):
            archive.writestr(name, b"synthetic")
    with ZipFile(second, "w") as archive:
        archive.writestr("other/unrelated.txt", b"synthetic")
    try:
        app = gui.App(root)
        app._load_source(str(first))
        assert app.fields["dose"].get() == f"case/sumtally/{gui.COMBINED_NAME}"
        assert app.hints["dose"].get() == "自動候補・変更可"
        assert str(app.combos["dose"]["state"]) == "normal"
        assert str(app.add_button["state"]) == "normal"
        assert str(app.run_button["state"]) == "disabled"
        assert "まず「ケースを追加」" in app.input_state.get()
        app._add()
        assert str(app.run_button["state"]) == "normal"
        assert "「集計する」を押してください" in app.input_state.get()
        app.fields["dose"].set("case/other.out")
        assert app.fields["dose"].get() == "case/other.out"
        assert app.hints["dose"].get() == ""
        app.fields["dose"].set("")
        app._member("dose")
        dialog = next(item for item in app.winfo_children() if isinstance(item, tk.Toplevel))
        root.update()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        box = next(item for item in descendants(dialog) if isinstance(item, tk.Listbox))
        index = list(box.get(0, "end")).index("case/other.out")
        box.selection_set(index)
        choose = next(item for item in descendants(dialog)
                      if isinstance(item, gui.ttk.Button) and item.cget("text") == "選択")
        choose.invoke()
        assert app.fields["dose"].get() == "case/other.out"
        app._load_source(str(second))
        assert app.fields["dose"].get() == ""
        assert str(app.add_button["state"]) == "disabled"
    finally:
        root.destroy()


def test_directory_member_and_external_rtstruct_pickers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    source = tmp_path / "case"
    source.mkdir()
    selected = source / "custom-output.dat"
    selected.write_bytes(b"synthetic")
    try:
        app = gui.App(root)
        app._load_source(str(source))
        monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **_kwargs: str(selected))
        app._member("dose")
        assert app.fields["dose"].get() == "custom-output.dat"
        external = tmp_path / "RTSTRUCT_without_extension"
        _rtstruct(external)
        app.fields["roi_number"].set("7")
        monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **_kwargs: str(external))
        app._external("rtstruct", False)
        assert app.fields["rtstruct"].get() == str(external)
        assert app.fields["roi_number"].get() == ""
        assert gui.roi_choices(app.fields["rtstruct"].get()) == [(7, "Chamber")]
    finally:
        root.destroy()


def test_structure_selection_requires_explicit_number_and_geometry(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.dcm"
    _rtstruct(path)
    assert gui.roi_choices(str(path)) == [(7, "Chamber")]
    values = {**_fields(tmp_path), "region_type": "rtstruct"}
    with pytest.raises(roi.AnalysisError, match="PHITS 準備サマリー"):
        gui.case_from_fields(values)
    values.update(preparation="analysis/preparation.json", workspace=str(tmp_path),
                  ct_reference=str(path), rtplan=str(path), rtstruct=str(path), roi_number="7")
    case = gui.case_from_fields(values)
    assert case["region_type"] == "rtstruct" and case["roi_number"] == "7"
    assert case["region_label"] != "Chamber"


def test_gui_malformed_zip_and_busy_result_consistency(tmp_path: Path, monkeypatch) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args: errors.append(args))
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a ZIP")
    try:
        app = gui.App(root)
        app._load_source(str(broken))
        assert errors and not app.loaded_source
        case = gui.case_from_fields(_fields(tmp_path))
        app.cases = [case]
        app.results = [{"status": "ok"}]
        item = app.table.insert("", "end", values=("synthetic",))
        app.table.selection_set(item)
        app.busy = True
        app._refresh_state()
        assert str(app.remove_button["state"]) == "disabled"
        assert str(app.export_button["state"]) == "disabled"
        app._remove()
        app._run()
        app._export()
        assert app.cases == [case] and app.results == [{"status": "ok"}]
        app.busy = False
        app.details.set("stale details")
        app._remove()
        assert not app.cases and not app.results
        assert app.details.get() != "stale details"
    finally:
        root.destroy()


def test_report_rejects_dicom_input_folder(tmp_path: Path) -> None:
    dicom = tmp_path / "dicom"
    output = dicom / "reports"
    output.mkdir(parents=True)
    selected = dicom / "RTSTRUCT.dcm"
    selected.write_bytes(b"synthetic input")
    with pytest.raises(roi.AnalysisError, match="overlaps selected DICOM"):
        roi.publish([], str(output), "synthetic", [], (str(selected),))


def test_language_menu_preserves_session_and_completion(tmp_path: Path, monkeypatch) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    try:
        app = gui.App(root)
        values = _fields(tmp_path)
        for key, value in values.items():
            app.fields[key].set(value)
        app.loaded_source = values["source"]
        app.all_members = [values[key] for key in gui.REQUIRED]
        app.roi_combo.configure(values=["7 | Chamber {original}"])
        app.roi_combo.current(0)
        app.fields["roi_number"].set("7")
        app.hints["dose"].set("自動候補・変更可")
        app._add()
        row = {"case_label": "synthetic", "region_type": "sphere",
               "region_label": "Chamber {original}", "status": "ok", "grid_points": 2,
               "mean_dose_cgy": 125.5, "voxel_dose_sum_cgy": 251.0,
               "sample_points": 81, "sampling_volume_cm3": .081,
               "analytic_volume_cm3": .06545, "grid_volume_cm3": .054}
        app.events.put([row])
        app._poll()
        item = app.table.get_children()[0]
        app.table.selection_set(item)
        app._details(None)
        before_fields = {key: var.get() for key, var in app.fields.items()}
        before_cases = json.dumps(app.cases, sort_keys=True)
        before_results = json.dumps(app.results, sort_keys=True)
        before_row = app.table.item(item, "values")
        before_states = [str(w["state"]) for w in (app.add_button, app.run_button,
                                                  app.remove_button, app.export_button)]
        monkeypatch.setattr(gui.roi, "analyse", lambda *_a: pytest.fail("language switch ran analysis"))
        monkeypatch.setattr(gui.roi, "publish", lambda *_a: pytest.fail("language switch published reports"))
        for menu_index, expected_language, button, heading in (
            (1, "en", "Analyse", "Mean cGy"), (0, "ja", "集計する", "平均 cGy"),
        ):
            app.language_menu.invoke(menu_index)
            assert app.language.get() == expected_language
            assert app.run_button.cget("text") == button
            assert app.table.heading("Mean cGy", "text") == heading
            assert {key: var.get() for key, var in app.fields.items()} == before_fields
            assert json.dumps(app.cases, sort_keys=True) == before_cases
            assert json.dumps(app.results, sort_keys=True) == before_results
            assert app.table.selection() == (item,)
            assert app.table.item(item, "values") == before_row
            assert app.roi_combo.get() == "7 | Chamber {original}"
            assert [str(w["state"]) for w in (app.add_button, app.run_button,
                                             app.remove_button, app.export_button)] == before_states
            assert "81" in app.details.get() and "0.081" in app.details.get()
        app.busy = True
        app.status.set("Analysing selected cases...")
        app._refresh_state()
        app.language_menu.invoke(1)
        assert app.busy and app.status.get() == "Analysing selected cases..."
        assert all(str(w["state"]) == "disabled" for w in (
            app.add_button, app.run_button, app.remove_button, app.export_button))
        app.events.put([row])
        app._poll()
        assert not app.busy and app.status.get().startswith("1 results;")
        assert app.hints["dose"].get() == "Suggested; editable"
        app.language_menu.invoke(0)
        assert app.status.get().startswith("1件の結果")
        assert app.hints["dose"].get() == "自動候補・変更可"
    finally:
        root.destroy()


def test_language_validation_and_raw_diagnostics(tmp_path: Path, monkeypatch) -> None:
    from phits_roi_gui_language import PAIRS, translate
    from string import Formatter
    for ja, en in PAIRS:
        fields = lambda text: {name for _, name, _, _ in Formatter().parse(text) if name}
        assert fields(ja) == fields(en)
    assert gui.case_from_fields(_fields(tmp_path), "en") == gui.case_from_fields(_fields(tmp_path))
    with pytest.raises(roi.AnalysisError, match="Select Combined dose"):
        gui.case_from_fields({**_fields(tmp_path), "dose": ""}, "en")
    assert translate("入力を確認してください（詳細原文）：{reason}", "en",
                     reason="source {literal}").endswith("source {literal}")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args: errors.append(args))
    try:
        app = gui.App(root)
        app.language_menu.invoke(1)
        assert "Select Source ZIP / folder" in app.input_state.get()
        broken = tmp_path / "broken.zip"
        broken.write_bytes(b"synthetic invalid archive")
        app._load_source(str(broken))
        assert errors[-1][0] == "Source"
        assert errors[-1][1].startswith("Check the inputs (original diagnostic):")
    finally:
        root.destroy()


def _adapter_inputs(tmp_path: Path, *, outside: bool = False):
    workspace = tmp_path / "frozen"
    (workspace / "analysis").mkdir(parents=True)
    (workspace / "segments").mkdir()
    manifest = {"schema_version": "segment_manifest_v2", "segments": []}
    preparation = {"returncode": 0, "phits_generation": {
        "ct_voxel_assets": {"rtplan_isocenter_dicom_cm": [0.0, 0.0, 0.0]}}}
    (workspace / "analysis" / "public_preparation_workspace_summary.json").write_text(
        json.dumps(preparation), encoding="utf-8")
    (workspace / "segments" / "segment_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    paths = {name: tmp_path / f"{name}.dcm" for name in ("ct_reference", "rtplan", "rtstruct")}
    paths["ct_reference"].write_bytes(b"synthetic CT input")
    paths["rtplan"].write_bytes(b"synthetic RT Plan input")
    _rtstruct(paths["rtstruct"], outside=outside)
    case = {"workspace": str(workspace), "preparation": "analysis/preparation.json",
            "roi_number": "7", **{name: str(path) for name, path in paths.items()}}
    source = SimpleNamespace(read=lambda _name, _limit: json.dumps(preparation).encode())
    mesh = Mesh("synthetic", "dose.out", (2, 2, 2), ((-1, 1), (-1, 1), (-1, 1)))
    generation = {"tally_geometry_binding": {"mesh_geometry": {"synthetic": True}}}
    return mesh, case, source, manifest, generation


def test_structure_native_order_one_and_multiple_cells(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mesh, case, source, manifest, generation = _adapter_inputs(tmp_path)
    monkeypatch.setattr(adapter, "validate_full_plan_context", lambda **_k: {
        "frame_of_reference_uid": "synthetic-frame", "rtplan_isocenter_dicom_mm": [0, 0, 0]})
    monkeypatch.setattr(adapter, "_frozen_ct_series", lambda *_a, **_k: (
        SimpleNamespace(frame_uid="synthetic-frame"), {}, {}))
    monkeypatch.setattr(adapter, "load_rtstruct_roi_mask_by_number", lambda *_a, **_k: (
        np.ones((2, 2, 2), dtype=bool), "Chamber", "synthetic-digest"))
    monkeypatch.setattr(adapter, "derive_rtdose_placement", lambda *_a, **_k: {})
    mapped = np.zeros((2, 2, 2), dtype=bool)
    mapped[0, 1, 0] = True
    monkeypatch.setattr(adapter, "_structure_membership_on_dose_grid", lambda **_k: mapped)
    native, geometry, _sha, label = adapter.rtstruct_membership(
        mesh, case, source, manifest, generation)
    assert label == "Chamber" and geometry["sample_points"] is None
    assert native.sum() == 1 and native[1, 0, 1]
    mapped[1, 0, 1] = True
    native, _, _, _ = adapter.rtstruct_membership(mesh, case, source, manifest, generation)
    assert native.sum() == 2 and native[0, 1, 0]
    summary = roi.summarize(native, np.ones((2, 2, 2)), np.full((2, 2, 2), .01), mesh, geometry)
    assert summary["grid_points"] == 2
    assert summary["voxel_dose_sum_cgy"] == 200
    assert summary["mean_dose_cgy"] == 100


def test_script_rtstruct_branch_uses_selected_native_cells(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mesh = Mesh("synthetic", "dose.out", (2, 2, 2), ((-1, 1), (-1, 1), (-1, 1)))
    values = np.arange(1, 9, dtype=np.float64).reshape(2, 2, 2)
    errors = np.full((2, 2, 2), .01)
    case = tally_fixture(tmp_path, mesh, values, errors)
    case.pop("radius_cm")
    case["region_type"] = "rtstruct"
    selected = np.zeros(mesh.counts, dtype=bool)
    selected[0, 0, 0] = selected[1, 1, 1] = True
    monkeypatch.setattr(adapter, "rtstruct_membership", lambda *_args: (
        selected, {"center_cm": None, "radius_cm": None, "analytic_volume_cm3": None,
                   "sample_spacing_cm": None, "sample_points": None,
                   "sampling_volume_cm3": None}, "synthetic-digest", "Chamber"))
    result = roi.analyse(case)
    assert result["region_type"] == "rtstruct" and result["region_label"] == "Chamber"
    assert result["grid_points"] == 2
    assert result["voxel_dose_sum_cgy"] == 900
    assert result["mean_dose_cgy"] == 450


def test_structure_binding_rejects_conflicts_and_outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mesh, case, source, manifest, generation = _adapter_inputs(tmp_path)
    (Path(case["workspace"]) / "segments" / "segment_manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(adapter.StructureBindingError, match="manifest differ"):
        adapter.rtstruct_membership(mesh, case, source, manifest, generation)
    (Path(case["workspace"]) / "segments" / "segment_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(adapter, "validate_full_plan_context", lambda **_k: {
        "frame_of_reference_uid": "other-frame", "rtplan_isocenter_dicom_mm": [0, 0, 0]})
    monkeypatch.setattr(adapter, "_frozen_ct_series", lambda *_a, **_k: (
        SimpleNamespace(frame_uid="synthetic-frame"), {}, {}))
    with pytest.raises(adapter.StructureBindingError, match="frames differ"):
        adapter.rtstruct_membership(mesh, case, source, manifest, generation)
    _rtstruct(Path(case["rtstruct"]), outside=True)
    monkeypatch.setattr(adapter, "validate_full_plan_context", lambda **_k: {
        "frame_of_reference_uid": "synthetic-frame", "rtplan_isocenter_dicom_mm": [0, 0, 0]})
    monkeypatch.setattr(adapter, "load_rtstruct_roi_mask_by_number", lambda *_a, **_k: (
        np.ones((2, 2, 2), dtype=bool), "Chamber", "synthetic-digest"))
    with pytest.raises(adapter.StructureBindingError, match="outside"):
        adapter.rtstruct_membership(mesh, case, source, manifest, generation)


def test_synthetic_frozen_ct_plan_structure_maps_one_native_cell(tmp_path: Path) -> None:
    snapshot = tmp_path / "ct2phits"
    snapshot.mkdir()
    ct = _write_ct_series(snapshot / "CT")
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm", ct, target_slices=(1,),
        target_bounds=(24.0, 26.0, 24.0, 26.0),
    )
    plan_path = snapshot / "RTPLAN.dcm"
    plan = _file_dataset(plan_path, pydicom.uid.RTPlanStorage, pydicom.uid.generate_uid(prefix=None))
    plan.Modality = "RTPLAN"
    plan.StudyInstanceUID = ct["study_uid"]
    plan.FrameOfReferenceUID = ct["frame_uid"]
    beam = Dataset()
    beam.BeamNumber = 1
    beam.TreatmentDeliveryType = "TREATMENT"
    cp = Dataset()
    cp.IsocenterPosition = [30.0, 30.0, 7.5]
    beam.ControlPointSequence = [cp]
    plan.BeamSequence = [beam]
    group = Dataset()
    group.FractionGroupNumber = 1
    group.NumberOfFractionsPlanned = 1
    reference = Dataset()
    reference.ReferencedBeamNumber = 1
    reference.BeamMeterset = 2.0
    group.ReferencedBeamSequence = [reference]
    plan.FractionGroupSequence = [group]
    _save_dataset(plan, plan_path)
    manifest = {
        "schema_version": "segment_manifest_v2", "workflow_mode": "full_plan",
        "plan_uid": plan.SOPInstanceUID,
        "segments": [{"beam_number": 1, "segment_mu": 2.0, "beam_meterset_mu": 2.0}],
        "plan_total_mu": 2.0, "included_total_mu": 2.0, "dose_normalization_mu": 2.0,
    }
    raw_hashes = {}
    datfiles = snapshot / "DATfiles"
    datfiles.mkdir()
    for name in RAW_CT2PHITS_NAMES:
        path = datfiles / name
        path.write_text("synthetic CT2PHITS asset\n", encoding="utf-8")
        raw_hashes[name] = _sha256(path)
    copied = [f"CT/{path.name}" for path in ct["paths"]]
    ct2phits_manifest = {
        "status": "completed",
        "ct_series": {
            "series_instance_uid": ct["series_uid"], "frame_of_reference_uid": ct["frame_uid"],
            "slice_count": len(ct["paths"]), "rows": 64, "columns": 64,
            "copied_files": copied,
            "sha256": {name: _sha256(path) for name, path in zip(copied, ct["paths"], strict=True)},
            "ct_origin_dicom_cm": [0.0, 0.0, 0.0],
        },
        "rtplan": {"isocenter_dicom_cm": [3.0, 3.0, .75],
                   "snapshot_path": "RTPLAN.dcm", "sha256": _sha256(plan_path)},
    }
    (snapshot / "ct2phits_workspace_manifest.json").write_text(
        json.dumps(ct2phits_manifest), encoding="utf-8")
    (snapshot / "ct2phits_execution_summary.json").write_text(
        json.dumps({"status": "completed", "raw_datfiles_sha256": raw_hashes}), encoding="utf-8")
    workspace = tmp_path / "workspace"
    (workspace / "analysis").mkdir(parents=True)
    (workspace / "segments").mkdir()
    (workspace / "segments" / "segment_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    preparation = {
        "schema_version": "dicomxphits_public_prepare_3dcrt_workspace_v1", "returncode": 0,
        "phits_generation": {"ct_voxel_assets": {
            "status": "validated_and_copied",
            "source_contract": "raw_ct2phits_datfiles_plus_ct_reference",
            "frame_of_reference_match": True, "raw_datfiles_sha256": raw_hashes,
            "ct_slice_count": len(ct["paths"]), "ct_origin_dicom_cm": [0.0, 0.0, 0.0],
            "rtplan_isocenter_dicom_cm": [3.0, 3.0, .75],
        }},
    }
    (workspace / "analysis" / "public_preparation_workspace_summary.json").write_text(
        json.dumps(preparation), encoding="utf-8")
    mesh = Mesh("synthetic", "dose.out", (6, 4, 6), ((-3, 3), (-1, 1), (-3, 3)))
    geometry = {"coordinate_system": roi.FRAME, "bounds_semantics": "bin_edges",
                "axes": {axis: {"minimum_cm": lo, "maximum_cm": hi, "bin_count": n,
                                "spacing_cm": (hi-lo)/n}
                         for axis, (lo, hi), n in zip("xyz", mesh.bounds, mesh.counts)}}
    source = SimpleNamespace(read=lambda _name, _limit: json.dumps(preparation).encode())
    case = {"workspace": str(workspace), "preparation": "analysis/preparation.json",
            "ct_reference": str(ct["paths"][0]), "rtplan": str(plan_path),
            "rtstruct": str(rtstruct), "roi_number": "1"}
    native, _, _, name = adapter.rtstruct_membership(
        mesh, case, source, manifest, {"tally_geometry_binding": {"mesh_geometry": geometry}})
    assert name == "Water_CC13_2cm"
    assert native.sum() == 1
    _write_rtstruct(rtstruct, ct, target_slices=(0, 1, 2, 3),
                    target_bounds=(10.0, 40.0, 10.0, 40.0))
    many, _, _, _ = adapter.rtstruct_membership(
        mesh, case, source, manifest, {"tally_geometry_binding": {"mesh_geometry": geometry}})
    assert many.sum() > 1
    shifted = Mesh("synthetic", "dose.out", (6, 4, 6), ((-2.95, 3.05), (-1, 1), (-3, 3)))
    shifted_geometry = {**geometry, "axes": {**geometry["axes"], "x": {
        "minimum_cm": -2.95, "maximum_cm": 3.05, "bin_count": 6, "spacing_cm": 1.0}}}
    with pytest.raises(adapter.StructureBindingError, match="mapping is unavailable"):
        adapter.rtstruct_membership(shifted, case, source, manifest,
                                    {"tally_geometry_binding": {"mesh_geometry": shifted_geometry}})
    _write_rtstruct(rtstruct, ct, target_slices=(1,),
                    target_bounds=(11.5, 12.5, 11.5, 12.5))
    with pytest.raises(adapter.StructureBindingError, match="mapping is unavailable"):
        adapter.rtstruct_membership(mesh, case, source, manifest,
                                    {"tally_geometry_binding": {"mesh_geometry": geometry}})
