"""Synthetic-only contract checks for the independent report script."""
from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest

from dicomxphits.phits_observation_format import Mesh
from dicomxphits.rtdose_geometry import tally_mesh_geometry_sha256


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "phits_roi_stats.py"
SPEC = importlib.util.spec_from_file_location("phits_roi_stats", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
roi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roi)


def tally(mesh: Mesh, role: str, values: np.ndarray, weight: float = 2.0) -> bytes:
    nx, ny, nz = mesh.counts
    rows = ["[ T-Deposit ]", "title = Synthetic combined dose", "mesh = xyz"]
    for axis, (lo, hi), n in zip("xyz", mesh.bounds, mesh.counts):
        rows += [f"{axis}-type = 2", f"{axis}min = {lo}", f"{axis}max = {hi}", f"n{axis} = {n}"]
    rows += ["unit = 0", "material = all", "output = dose", "axis = xy",
             "file = dose.out", "part = all", "letmat = 0", "dedxfnc = 0",
             "deposit = 0", "2D-type = 3", "mother = all", "sumtally start",
             "isumtally = 2", "nfile = 1", "segment.out", f"{weight:.6g}",
             "sfile = dose.out", f"sumfactor = {weight:.6g}", "sumtally end", "#newpage:"]
    ordered = values.transpose(2, 1, 0)[:, ::-1, :]
    for index, page_values in enumerate(ordered, 1):
        if index > 1:
            rows.append(" newpage:")
        zlo, zhi = mesh.bounds[2]
        dz = (zhi-zlo)/nz
        xl, xh = mesh.bounds[0]
        yl, yh = mesh.bounds[1]
        dx, dy = (xh-xl)/nx, (yh-yl)/ny
        rows += [f"#   no. ={index:3d}   iz  ={index:3d}   part. = all",
                 f"#   z = ( {zlo+(index-1)*dz:.4E} - {zlo+index*dz:.4E} )",
                 f"'no. ={index:3d},  iz ={index:3d}'",
                 "msuc: {Synthetic fixture}", r"msdl: {\it calculated by \PHITS  3.35}",
                 f"#  ny = {ny:3d}   nx = {nx:3d}",
                 "# ( ( data(x,y), x = 1, nx ), y = ny, 1, -1 )", "",
                 f"hc:  y = {yh-dy/2:.7g} to {yl+dy/2:.7g} by {dy:.7g} ; x = {xl+dx/2:.7g} to {xh-dx/2:.7g} by {dx:.7g} ;",
                 " ".join(str(x) for x in page_values.ravel()), "", "#" + "-"*78,
                 "hc: y= 0.005 to 0.995 by 0.01 ; x= 0.5 to 0.5 by 1 ;",
                 " ".join(str(x) for x in range(1, 101)), "z: xorg(0.0)",
                 "y: " + ("Dose [Gy/source]" if role == "dose" else "Relative Error"),
                 "e:", "z: xorg[-1.03/0.05]", "p: ymin(-1) ymax(1)", ""]
    return ("\n".join(rows) + "\n").encode("ascii")


def fixture(tmp_path: Path, mesh: Mesh, values: np.ndarray, errors: np.ndarray,
            *, zip_mode: bool = False, retained: bool = False) -> dict:
    manifest = {"schema_version": "segment_manifest_v2", "workflow_mode": "full_plan",
                "segments": [{"segment_mu": 2.0, "mu_weight": 2.0,
                              "beam_number": 1, "delivery_type": "3dcrt",
                              "beam_meterset_mu": 2.0}],
                "plan_total_mu": 2.0, "included_total_mu": 2.0,
                "dose_normalization_mu": 2.0}
    evidence = roi.plan_mu_normalization_evidence(manifest)
    geometry = {"coordinate_system": roi.FRAME, "bounds_semantics": "bin_edges",
                "axes": {axis: {"minimum_cm": lo, "maximum_cm": hi, "bin_count": count,
                                "spacing_cm": (hi-lo)/count}
                         for axis, (lo, hi), count in zip("xyz", mesh.bounds, mesh.counts)}}
    hint = {"input_dose_state": "sumtally_active_treatment_mu_sum",
            "input_dose_unit": "GY", "phits2dicom_factor": 1.0}
    common = {"stage_status": "success", "returncode": 0,
              "manifest_sha256": roi.canonical_manifest_digest(manifest),
              "sumtally_mode": "totalfield", "weight_field": "segment_mu",
              "sumtally_scope": "all_active_segments",
              "sumtally_normalization": "active_treatment_segments_totalfield_segment_mu_sum",
              "sumtally_normalization_evidence": evidence,
              "tally_geometry_binding": {"mesh_geometry": geometry},
              "rt_dose_conversion_hint": hint, "sum_input_sha256": "a"*64,
              "sumtally_input_sha256": "b"*64}
    dose = tally(mesh, "dose", values)
    error = tally(mesh, "error", errors)
    generation = {**common, "schema_version": "dicomxphits_public_sumtally_generation_v1"}
    execution = {**common, "schema_version": "dicomxphits_public_sumtally_execution_v1",
                 "expected_sumtally_output_sha256": roi.digest(dose),
                 "expected_sumtally_output_after_run": {"sha256": roi.digest(dose)},
                 "expected_sumtally_output_updated_by_run": True}
    files = {"official/dose.out": dose, "saved/dose_err.out": error,
             "generation.json": json.dumps(generation).encode(),
             "execution.json": json.dumps(execution).encode(),
             "manifest.json": json.dumps(manifest).encode()}
    if retained:
        files["saved/dose.out"] = dose
    else:
        files["official/dose_err.out"] = files.pop("saved/dose_err.out")
    if zip_mode:
        source = tmp_path / "case.zip"
        with ZipFile(source, "w") as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
    else:
        source = tmp_path / "case"
        for name, raw in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    case = {"source": str(source), "dose": "official/dose.out",
            "error": "saved/dose_err.out" if retained else "official/dose_err.out",
            "generation": "generation.json", "execution": "execution.json",
            "manifest": "manifest.json", "radius_cm": .25,
            "case_label": "synthetic", "region_label": "sphere"}
    if retained:
        case["retained_dose"] = "saved/dose.out"
    return case


def test_approved_geometry_examples():
    aligned = Mesh("synthetic", "dose.out", (11, 11, 11),
                   ((-1.1, 1.1), (-1.1, 1.1), (-1.1, 1.1)))
    mask, geometry = roi.sphere(aligned, {"radius_cm": .25})
    assert mask.sum() == 7
    assert geometry["sample_points"] == 81
    assert geometry["sampling_volume_cm3"] == pytest.approx(.081)
    assert geometry["analytic_volume_cm3"] == pytest.approx(.06544984695)
    offset = Mesh("synthetic", "dose.out", (11, 11, 10),
                  ((-1.65, 1.65), (-1.65, 1.65), (-1.75, 1.25)))
    assert roi.sphere(offset, {"radius_cm": .25})[0].sum() == 2
    assert roi.sphere(aligned, {"volume_cm3": .25})[1]["radius_cm"] == pytest.approx(.39079632)
    with pytest.raises(roi.AnalysisError, match="outside mesh"):
        roi.sphere(aligned, {"radius_cm": .25, "center_cm": [.9, 0, 0]})


def test_decimal_radius_shell_includes_boundary_sampling_points():
    mesh = Mesh("synthetic", "dose.out", (11, 11, 11),
                ((-1.1, 1.1), (-1.1, 1.1), (-1.1, 1.1)))
    geometry = roi.sphere(mesh, {"radius_cm": .3, "sample_spacing_cm": .1})[1]
    assert geometry["sample_points"] == 123
    assert geometry["sampling_volume_cm3"] == pytest.approx(.123)


def test_decimal_radius_shell_includes_native_cell_centres():
    mesh = Mesh("synthetic", "dose.out", (13, 1, 1),
                ((-.65, .65), (-.65, .65), (-.65, .65)))
    mask, geometry = roi.sphere(mesh, {"radius_cm": .6})
    assert mask[:, 0, 0].all()
    values = np.arange(13, dtype=float).reshape(mesh.counts)
    result = roi.summarize(mask, values, np.full(mesh.counts, .1), mesh, geometry)
    assert result["grid_points"] == 13
    assert result["voxel_dose_sum_cgy"] == pytest.approx(7800)


@pytest.mark.parametrize("zip_mode,retained", [(False, False), (True, True)])
def test_pair_statistics_and_immutable_inputs(tmp_path, zip_mode, retained):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.2, .2)))
    dose = np.array([[[1], [2]], [[3], [0]]], dtype=float)
    error = np.array([[[.1], [.2]], [[0], [.5]]], dtype=float)
    case = fixture(tmp_path, mesh, dose, error, zip_mode=zip_mode, retained=retained)
    case["radius_cm"] = .19
    source = Path(case["source"])
    before = source.read_bytes() if source.is_file() else {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    row = roi.analyse(case)
    assert row["status"] == "ok"
    assert row["region_type"] == "sphere"
    assert row["grid_points"] == 4
    assert row["voxel_dose_sum_cgy"] == pytest.approx(600)
    assert row["mean_dose_cgy"] == pytest.approx(150)
    assert row["spatial_stddev_cgy"] == pytest.approx(np.std([100, 200, 300, 0]))
    assert row["error_eligible_count"] == 2
    assert row["zero_dose_count"] == 1
    assert row["positive_dose_zero_error_count"] == 1
    assert row["median_voxel_rerr_percent"] == pytest.approx(15)
    assert row["p95_voxel_rerr_percent"] == pytest.approx(19.5)
    assert row["mean_voxel_standard_error_cgy"] == pytest.approx(25)
    after = source.read_bytes() if source.is_file() else {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    assert before == after


def test_failure_partial_and_mask(tmp_path):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.2, .2)))
    dose = np.ones(mesh.counts)
    error = np.zeros(mesh.counts)
    case = fixture(tmp_path, mesh, dose, error)
    case["radius_cm"] = .19
    row = roi.analyse(case)
    assert row["status"] == "partial" and row["mean_voxel_rerr_percent"] is None
    assert row["error_excluded_count"] == 4
    mask_path = tmp_path / "mask.npz"
    np.savez(mask_path, mask=np.array([[[True], [False]], [[False], [True]]]),
             x_edges_cm=np.linspace(-.2, .2, 3), y_edges_cm=np.linspace(-.2, .2, 3),
             z_edges_cm=np.linspace(-.2, .2, 2), coordinate_system=roi.FRAME, axis_order="xyz")
    case.update(region_type="structure", region_label="SyntheticStructure", mask=str(mask_path))
    row = roi.analyse(case)
    assert row["grid_points"] == 2 and row["sample_points"] is None
    assert row["region_type"] == "structure"
    np.savez(mask_path, mask=np.ones(mesh.counts, dtype=bool),
             x_edges_cm=np.linspace(-.2, .2, 3)+.01, y_edges_cm=np.linspace(-.2, .2, 3),
             z_edges_cm=np.linspace(-.2, .2, 2), coordinate_system=roi.FRAME, axis_order="xyz")
    with pytest.raises(roi.AnalysisError, match="edges mismatch"):
        roi.analyse(case)


def test_pair_and_evidence_rejections(tmp_path):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.1, .1)))
    case = fixture(tmp_path, mesh, np.ones(mesh.counts), np.ones(mesh.counts)*.1, retained=True)
    source = Path(case["source"])
    (source / case["retained_dose"]).write_bytes(b"changed")
    with pytest.raises(roi.AnalysisError, match="retained/official"):
        roi.analyse(case)
    (source / case["retained_dose"]).write_bytes((source / case["dose"]).read_bytes())
    execution = source / case["execution"]
    data = json.loads(execution.read_text())
    data["expected_sumtally_output_sha256"] = "0"*64
    execution.write_text(json.dumps(data))
    with pytest.raises(roi.AnalysisError, match="terminal dose digest"):
        roi.analyse(case)
    with pytest.raises(roi.AnalysisError, match="unsafe"):
        roi.relative_name("../dose.out")


def test_new_only_reports_and_csv_neutralization(tmp_path):
    output = tmp_path / "reports"
    output.mkdir()
    row = {"case_label": "=formula", "region_label": "@label", "region_type": "sphere",
           "status": "partial", "reason": "no eligible r.err", "source_members": {},
           "source_sha256": {}}
    assert roi.publish([row], str(output), "report", []) == ["report.json", "report.csv"]
    csv_text = (output / "report.csv").read_text()
    assert "'=formula" in csv_text and "'@label" in csv_text
    with pytest.raises(roi.AnalysisError, match="already published"):
        roi.publish([row], str(output), "report", [])


def test_invalid_case_cannot_publish_inside_its_source(tmp_path, capsys):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.1, .1)))
    case = fixture(tmp_path, mesh, np.ones(mesh.counts), np.ones(mesh.counts) * .1)
    source = Path(case["source"])
    output = source / "reports"
    output.mkdir()
    (source / case["error"]).write_bytes(b"invalid synthetic error")
    args = [item for key in ("source", "dose", "error", "generation", "execution", "manifest")
            for item in ("--" + key.replace("_", "-"), str(case[key]))]
    args += ["--radius-cm", str(case["radius_cm"]),
             "--output-dir", str(output), "--report-stem", "guard-test"]
    assert roi.main(args) == 1
    captured = capsys.readouterr()
    assert '"status": "invalid"' in captured.out
    assert "output directory overlaps source" in captured.err
    assert list(output.iterdir()) == []


def test_direct_pair_evidence_rejects_replaced_error(tmp_path):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.2, .2)))
    case = fixture(tmp_path, mesh, np.ones(mesh.counts), np.ones(mesh.counts) * .1)
    case["radius_cm"] = .19
    source = Path(case["source"])
    dose_raw = (source / case["dose"]).read_bytes()
    error_path = source / case["error"]
    error_raw = error_path.read_bytes()
    _mesh, _values, _errors, metadata = roi.parse_pair(dose_raw, error_raw)
    generation = json.loads((source / case["generation"]).read_text())
    geometry = generation["tally_geometry_binding"]["mesh_geometry"]
    execution_path = source / case["execution"]
    execution = json.loads(execution_path.read_text())
    execution["combined_relative_error_evidence"] = {
        "schema_version": "dicomxphits_sumtally_relative_error_pair_v1",
        "semantics": "phits_3_35_sumtally_isumtally_2_relative_error_v1",
        "validated": True, "dose_sha256": roi.digest(dose_raw),
        "error_sha256": roi.digest(error_raw),
        "sum_input_sha256": generation["sum_input_sha256"],
        "mesh_geometry_sha256": tally_mesh_geometry_sha256(geometry),
        "cell_count": mesh.cells,
        "pair_metadata_sha256": roi.canonical_manifest_digest(metadata),
    }
    execution_path.write_text(json.dumps(execution))
    assert roi.analyse(case)["status"] == "ok"
    error_path.write_bytes(tally(mesh, "error", np.ones(mesh.counts) * .2))
    with pytest.raises(roi.AnalysisError, match="combined error evidence mismatch"):
        roi.analyse(case)
    error_path.write_bytes(error_raw)
    execution["combined_relative_error_evidence"]["pair_metadata_sha256"] = "0" * 64
    execution_path.write_text(json.dumps(execution))
    with pytest.raises(roi.AnalysisError, match="combined error evidence mismatch"):
        roi.analyse(case)


def test_axis_order_single_cell_and_empty_region(tmp_path):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 2),
                ((-.4, .4), (-.4, .4), (-.4, .4)))
    dose = np.arange(8, dtype=float).reshape(mesh.counts)
    errors = np.ones(mesh.counts) * .2
    case = fixture(tmp_path, mesh, dose, errors)
    mask = np.zeros(mesh.counts, dtype=bool)
    mask[1, 0, 1] = True
    mask_path = tmp_path / "mask.npz"

    def save_mask():
        np.savez(mask_path, mask=mask, x_edges_cm=np.linspace(-.4, .4, 3),
                 y_edges_cm=np.linspace(-.4, .4, 3), z_edges_cm=np.linspace(-.4, .4, 3),
                 coordinate_system=roi.FRAME, axis_order="xyz")

    save_mask()
    case.update(region_type="structure", mask=str(mask_path))
    row = roi.analyse(case)
    assert row["grid_points"] == 1
    assert row["mean_dose_cgy"] == 500
    assert row["error_eligible_count"] == 1
    assert row["mean_voxel_rerr_percent"] == 20
    mask[:] = False
    save_mask()
    empty = roi.analyse(case)
    assert empty["status"] == "empty" and empty["mean_dose_cgy"] is None


def test_duplicate_zip_member_and_batch(tmp_path, capsys):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.2, .2)))
    case = fixture(tmp_path, mesh, np.ones(mesh.counts), np.ones(mesh.counts)*.1,
                   zip_mode=True, retained=True)
    archive_path = Path(case["source"])
    raw = archive_path.read_bytes()
    case["radius_cm"] = .19
    batch = tmp_path / "batch.json"
    case["source"] = archive_path.name
    batch.write_text(json.dumps({"cases": [case]}))
    assert roi.main(["--batch", str(batch)]) == 0
    assert '"grid_points": 4' in capsys.readouterr().out
    archive_path.write_bytes(raw)
    with ZipFile(archive_path, "a") as archive:
        archive.writestr("official/dose.out", b"duplicate")
    case["source"] = str(archive_path)
    with pytest.raises(roi.AnalysisError, match="duplicated"):
        roi.analyse(case)


def test_normalization_role_and_numeric_rejections(tmp_path):
    mesh = Mesh("Synthetic combined dose", "dose.out", (2, 2, 1),
                ((-.2, .2), (-.2, .2), (-.2, .2)))
    case = fixture(tmp_path, mesh, np.ones(mesh.counts), np.ones(mesh.counts)*.1)
    case["radius_cm"] = .19
    source = Path(case["source"])
    generation_path = source / case["generation"]
    generation = json.loads(generation_path.read_text())
    generation["sumtally_normalization_evidence"]["sumfactor"] = 3.0
    generation_path.write_text(json.dumps(generation))
    with pytest.raises(roi.AnalysisError, match="normalization evidence"):
        roi.analyse(case)
    generation["sumtally_normalization_evidence"]["sumfactor"] = 2.0
    generation_path.write_text(json.dumps(generation))
    error_path = source / case["error"]
    valid = error_path.read_bytes()
    error_path.write_bytes(valid.replace(b"Relative Error", b"Dose [Gy/source]"))
    with pytest.raises(roi.AnalysisError, match="invalid combined pair"):
        roi.analyse(case)
    error_path.write_bytes(valid.replace(b"0.1 0.1", b"nan 0.1", 1))
    with pytest.raises(roi.AnalysisError, match="invalid combined pair"):
        roi.analyse(case)


def test_hardlinked_input_rejected(tmp_path):
    original = tmp_path / "synthetic.bin"
    alias = tmp_path / "alias.bin"
    original.write_bytes(b"synthetic")
    os.link(original, alias)
    assert alias.stat().st_nlink == 2
    with pytest.raises(roi.AnalysisError, match="linked/reparse-backed"):
        roi.stable_file(alias, 1024)
