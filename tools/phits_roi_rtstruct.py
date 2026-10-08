"""Read-only, evidence-bound RT Structure membership for standalone ROI statistics.

This adapter reuses the accepted CT rasterizer and affine cell-mapping rules.
It does not invoke the post-completion evaluator or grant workflow authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

import numpy as np
import pydicom

from dicomxphits.replace_ct_layer_with_water import load_rtstruct_roi_mask_by_number
from dicomxphits.rtdose_geometry import derive_rtdose_placement
from dicomxphits.rtdose_plan_references import validate_full_plan_context
from dicomxphits.structure_relative_error import (
    _frozen_ct_series,
    _structure_membership_on_dose_grid,
)

MAX_JSON = 4 * 1024 * 1024


class StructureBindingError(ValueError):
    """Selected DICOM evidence cannot support a native Structure result."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise StructureBindingError(message)


def _json(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise StructureBindingError("invalid geometry evidence JSON") from exc
    _require(isinstance(value, dict), "invalid geometry evidence JSON")
    return value


def _file(path: Path) -> bytes:
    absolute = Path(os.path.abspath(path))
    for part in (absolute, *absolute.parents):
        mode = part.lstat().st_mode
        _require(not stat.S_ISLNK(mode) and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400),
                 "linked geometry evidence path")
    _require(absolute.is_file() and absolute.stat().st_nlink == 1,
             "missing or linked geometry evidence file")
    before = absolute.stat()
    _require(before.st_size <= MAX_JSON, "geometry evidence exceeds size limit")
    raw = absolute.read_bytes()
    after = absolute.stat()
    _require(len(raw) == before.st_size and
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
             "geometry evidence changed during read")
    return raw


def _ordinary_input(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    for part in (absolute, *absolute.parents):
        mode = part.lstat().st_mode
        _require(not stat.S_ISLNK(mode) and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400),
                 "linked DICOM input path")
    _require(absolute.is_file() and absolute.stat().st_nlink == 1,
             "missing or linked DICOM input")


def _manifest_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def _selected_contours_inside_mesh(
    rtstruct_path: Path, roi_number: int, isocenter_mm: list[float], mesh: object
) -> bool:
    """Reject a contour extending past native PHITS bin edges without tolerance."""
    dataset = pydicom.dcmread(str(rtstruct_path), stop_before_pixels=True)
    items = [item for item in getattr(dataset, "ROIContourSequence", ())
             if int(getattr(item, "ReferencedROINumber", -1)) == roi_number]
    if len(items) != 1:
        return False
    contours = list(getattr(items[0], "ContourSequence", ()))
    if not contours:
        return False
    for contour in contours:
        raw = np.asarray(getattr(contour, "ContourData", ()), dtype=np.float64)
        if not len(raw) or len(raw) % 3 or not np.isfinite(raw).all():
            return False
        xyz = raw.reshape(-1, 3)
        iec = np.column_stack(((isocenter_mm[0] - xyz[:, 0]) / 10,
                               (xyz[:, 2] - isocenter_mm[2]) / 10,
                               (xyz[:, 1] - isocenter_mm[1]) / 10))
        if any(np.any(iec[:, axis] < limits[0]) or np.any(iec[:, axis] > limits[1])
               for axis, limits in enumerate(mesh.bounds)):
            return False
    return True


def rtstruct_membership(mesh, case: dict, source, manifest: dict, generation: dict):
    """Return an exact native xyz mask after binding every selected source."""
    for name in ("workspace", "ct_reference", "rtplan", "rtstruct", "preparation"):
        _require(bool(case.get(name)), f"{name} is required for RT Structure")
    try:
        roi_number = int(case["roi_number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise StructureBindingError("a unique numeric ROINumber is required") from exc
    _require(roi_number > 0 and str(roi_number) == str(case["roi_number"]).strip(),
         "invalid ROINumber")
    workspace = Path(case["workspace"]).absolute()
    ct_reference = Path(case["ct_reference"]).absolute()
    rtplan = Path(case["rtplan"]).absolute()
    rtstruct = Path(case["rtstruct"]).absolute()
    _require(workspace.is_dir() and not workspace.is_symlink(), "frozen workspace is unavailable")
    _ordinary_input(ct_reference)
    _ordinary_input(rtplan)
    _ordinary_input(rtstruct)
    selected_prep = _json(source.read(case["preparation"], MAX_JSON))
    local_prep = _json(_file(
        workspace / "analysis" / "public_preparation_workspace_summary.json"
    ))
    _require(selected_prep == local_prep and selected_prep.get("returncode") == 0,
         "source and frozen preparation evidence differ")
    local_manifest = _json(_file(workspace / "segments" / "segment_manifest.json"))
    _require(_manifest_digest(local_manifest) == _manifest_digest(manifest),
         "source and frozen manifest differ")
    try:
        context = validate_full_plan_context(
            rtplan_path=rtplan, workspace_root=workspace, ct_reference_path=ct_reference
        )
    except Exception as exc:
        raise StructureBindingError("RT Plan, CT reference, or manifest binding is invalid") from exc
    try:
        series, _, _ = _frozen_ct_series(ct_reference, workspace_root=workspace)
    except Exception as exc:
        raise StructureBindingError("frozen CT series or CT2PHITS evidence is invalid") from exc
    _require(series.frame_uid == context["frame_of_reference_uid"],
         "RT Plan and frozen CT frames differ")
    binding = generation["tally_geometry_binding"]["mesh_geometry"]
    iso = context["rtplan_isocenter_dicom_mm"]
    _require(selected_prep.get("phits_generation", {}).get("ct_voxel_assets", {}).get(
        "rtplan_isocenter_dicom_cm") == [float(x) / 10 for x in iso],
         "PHITS generation and RT Plan isocenters differ")
    try:
        ct_mask, roi_name, rtstruct_sha = load_rtstruct_roi_mask_by_number(
            rtstruct, series=series, roi_number=roi_number
        )
    except Exception as exc:
        raise StructureBindingError("RT Structure, ROI, or CT contour binding is invalid") from exc
    try:
        inside = _selected_contours_inside_mesh(rtstruct, roi_number, iso, mesh)
    except Exception as exc:
        raise StructureBindingError("RT Structure contour extent is invalid") from exc
    _require(inside, "RT Structure contour extends outside the PHITS mesh")
    try:
        placement = derive_rtdose_placement(binding, rtplan_isocenter_dicom_mm=iso)
        mapped = _structure_membership_on_dose_grid(
            placement=placement, series=series, ct_mask=ct_mask
        )
    except Exception as exc:
        raise StructureBindingError("RT Structure to PHITS cell mapping is unavailable") from exc
    native = mapped.transpose(2, 0, 1)[::-1, :, :].copy()
    _require(native.shape == mesh.counts, "mapped Structure shape differs from PHITS mesh")
    geometry = {"center_cm": None, "radius_cm": None, "analytic_volume_cm3": None,
                "sample_spacing_cm": None, "sample_points": None,
                "sampling_volume_cm3": None}
    return native, geometry, rtstruct_sha, roi_name
