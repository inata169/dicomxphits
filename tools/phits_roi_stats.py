"""Read-only, independent PHITS 3.35 combined-dose ROI summaries.

The only repository import is the bounded, GUI-independent tally format parser.
Run from this checkout with Python 3.12 and NumPy; no package installation or
external PHITS tool is needed. This script gives no workflow or clinical authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import time
import unicodedata
from zipfile import ZipFile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dicomxphits.phits_observation_format import (  # noqa: E402
    MAX_TALLY_BYTES, Mesh, _sumtally_output_fields, mesh_from_fields,
    paired_sumtally_values,
)
from dicomxphits.sumtally_inputs import plan_mu_normalization_evidence  # noqa: E402

SCHEMA = "dicomxphits_standalone_phits_roi_statistics_v1"
FRAME = "phits_iec_fixed_cm_isocenter_anchored"
MAX_JSON = 4 * 1024 * 1024
MAX_MASK = 256 * 1024 * 1024
MAX_CASES = 100
NUMBER_KEYS = (
    "radius_cm", "analytic_volume_cm3", "sample_spacing_cm", "sample_points",
    "sampling_volume_cm3", "grid_points", "grid_volume_cm3",
    "voxel_dose_sum_cgy", "mean_dose_cgy", "min_dose_cgy", "max_dose_cgy",
    "spatial_stddev_cgy", "error_eligible_count", "zero_dose_count",
    "positive_dose_zero_error_count", "error_excluded_count",
    "mean_voxel_rerr_percent", "median_voxel_rerr_percent",
    "p95_voxel_rerr_percent", "max_voxel_rerr_percent",
    "mean_voxel_standard_error_cgy", "max_voxel_standard_error_cgy",
)


class AnalysisError(ValueError):
    """A selected snapshot cannot support the requested report."""


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise AnalysisError(reason)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_manifest_digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("utf-8")
    return digest(raw)


def relative_name(value: str) -> str:
    need(isinstance(value, str) and bool(value) and "\\" not in value
         and "\x00" not in value and not re.match(r"^[A-Za-z]:", value),
         "unsafe relative selector")
    path = PurePosixPath(value)
    need(not path.is_absolute() and all(p not in {"", ".", ".."} for p in value.split("/"))
         and str(path) == value, "unsafe relative selector")
    return value


def ordinary_path(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    for part in (absolute, *absolute.parents):
        mode = part.lstat().st_mode
        need(not stat.S_ISLNK(mode) and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400),
             "linked/reparse-backed path")
    need(absolute.is_file(), "selected input is not an ordinary file")
    need(absolute.stat().st_nlink == 1, "linked/reparse-backed path")


def stable_file(path: Path, limit: int) -> bytes:
    ordinary_path(path)
    before = path.stat()
    need(before.st_size <= limit, "input size limit")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
        after_fd = os.fstat(stream.fileno())
    after = path.stat()
    need(len(raw) <= limit and len(raw) == before.st_size and
         (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) ==
         (after_fd.st_dev, after_fd.st_ino, after_fd.st_size, after_fd.st_mtime_ns),
         "input changed during read")
    return raw


class Source:
    def __init__(self, location: str):
        self.path = Path(location).absolute()
        need(self.path.exists(), "source does not exist")
        if self.path.is_dir():
            for part in (self.path, *self.path.parents):
                mode = part.lstat().st_mode
                need(not stat.S_ISLNK(mode) and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400),
                     "linked/reparse-backed source")
            self.archive = False
        else:
            ordinary_path(self.path)
            need(self.path.suffix.lower() == ".zip", "source must be directory or ZIP")
            self.archive = True

    def read(self, member: str, limit: int) -> bytes:
        member = relative_name(member)
        if not self.archive:
            root = self.path
            path = root.joinpath(*member.split("/"))
            need(path.is_relative_to(root), "selector escapes source")
            return stable_file(path, limit)
        before = self.path.stat()
        with ZipFile(self.path) as archive:
            matches = [x for x in archive.infolist() if x.filename == member]
            need(len(matches) == 1, "selected ZIP member missing or duplicated")
            entry = matches[0]
            mode = entry.external_attr >> 16
            need(not entry.is_dir() and (not stat.S_IFMT(mode) or stat.S_ISREG(mode))
                 and entry.file_size <= limit and entry.compress_size <= limit
                 and entry.flag_bits & 1 == 0, "unsupported ZIP entry")
            with archive.open(entry) as stream:
                raw = stream.read(limit + 1)
        after = self.path.stat()
        need(len(raw) == entry.file_size and len(raw) <= limit and
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
             "ZIP changed during read")
        return raw


def json_object(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError) as exc:
        raise AnalysisError(f"invalid {label} JSON") from exc
    need(isinstance(value, dict), f"invalid {label} JSON root")
    return value


def finite_positive(value, label: str) -> float:
    need(isinstance(value, (int, float)) and not isinstance(value, bool), f"invalid {label}")
    result = float(value)
    need(math.isfinite(result) and result > 0, f"invalid {label}")
    return result


def close_printed(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=2e-11, abs_tol=2e-9)


def phits_six_digits(a: float, b: float) -> bool:
    """PHITS 3.35 echoes Sumtally weights and sumfactor with six digits."""
    return a == float(f"{b:.6g}")


def validate_evidence(manifest: dict, generation: dict, execution: dict,
                      dose_sha: str, error_sha: str, metadata: dict, mesh: Mesh) -> None:
    need(manifest.get("schema_version") == "segment_manifest_v2" and
         manifest.get("workflow_mode") == "full_plan", "unsupported manifest")
    need(generation.get("schema_version") == "dicomxphits_public_sumtally_generation_v1" and
         execution.get("schema_version") == "dicomxphits_public_sumtally_execution_v1" and
         generation.get("stage_status") == execution.get("stage_status") == "success" and
         generation.get("returncode") == execution.get("returncode") == 0,
         "unsupported or unsuccessful Sumtally evidence")
    manifest_sha = canonical_manifest_digest(manifest)
    need(generation.get("manifest_sha256") == execution.get("manifest_sha256") == manifest_sha,
         "manifest digest mismatch")
    for key, expected in (("sumtally_mode", "totalfield"), ("weight_field", "segment_mu"),
                          ("sumtally_scope", "all_active_segments"),
                          ("sumtally_normalization", "active_treatment_segments_totalfield_segment_mu_sum")):
        need(generation.get(key) == execution.get(key) == expected, f"{key} mismatch")
    need(execution.get("expected_sumtally_output_sha256") == dose_sha and
         isinstance(execution.get("expected_sumtally_output_after_run"), dict) and
         execution["expected_sumtally_output_after_run"].get("sha256") == dose_sha and
         execution.get("expected_sumtally_output_updated_by_run") is True,
         "terminal dose digest mismatch")
    need(generation.get("sum_input_sha256") == execution.get("sum_input_sha256") and
         generation.get("sumtally_input_sha256") == execution.get("sumtally_input_sha256"),
         "generated input digest mismatch")
    evidence = generation.get("sumtally_normalization_evidence")
    try:
        expected_normalization = plan_mu_normalization_evidence(manifest)
    except ValueError as exc:
        raise AnalysisError("manifest does not prove active-treatment normalization") from exc
    need(isinstance(evidence, dict) and evidence == execution.get("sumtally_normalization_evidence") and
         evidence == expected_normalization and
         evidence.get("schema_version") == "dicomxphits_active_treatment_mu_sum_v1" and
         evidence.get("reconciled") is True and evidence.get("isumtally") == 2 and
         evidence.get("weight_field") == "segment_mu" and
         evidence.get("input_segment_dose_unit") == "GY/MU" and
         evidence.get("output_dose_unit") == "GY" and
         evidence.get("output_dose_state") == "sumtally_active_treatment_mu_sum" and
         evidence.get("summation_rule") == "sum(active_segment_mu * segment_dose_per_mu)" and
         evidence.get("sumfactor_unit") == "MU", "normalization evidence mismatch")
    active = [s for s in manifest.get("segments", []) if isinstance(s, dict) and not s.get("skip_reason")]
    need(bool(active) and len(active) == metadata["nfile"] == len(metadata["sources"]),
         "active segment count mismatch")
    mus = [finite_positive(s.get("segment_mu"), "segment MU") for s in active]
    need(all(close_printed(finite_positive(s.get("mu_weight"), "MU weight"), mu)
                 for s, mu in zip(active, mus)) and
         all(phits_six_digits(m["weight"], mu) for m, mu in zip(metadata["sources"], mus)),
         "source weights mismatch")
    total = sum(mus)
    need(all(close_printed(finite_positive(evidence.get(k), k), total) for k in
             ("sumfactor", "active_segment_mu_sum", "active_treatment_beam_meterset_sum")) and
         phits_six_digits(metadata["sumfactor"], total), "sumfactor mismatch")
    need(all(close_printed(finite_positive(manifest.get(k), k), finite_positive(evidence.get(k), k))
                 for k in ("plan_total_mu", "included_total_mu", "dose_normalization_mu")),
         "manifest normalization mismatch")
    hint = generation.get("rt_dose_conversion_hint")
    need(hint == execution.get("rt_dose_conversion_hint") and isinstance(hint, dict) and
         hint.get("input_dose_state") == "sumtally_active_treatment_mu_sum" and
         hint.get("input_dose_unit") == "GY" and hint.get("phits2dicom_factor") == 1.0,
         "dose-basis hint mismatch")
    binding = generation.get("tally_geometry_binding")
    need(isinstance(binding, dict) and binding == execution.get("tally_geometry_binding"),
         "geometry binding mismatch")
    geometry = binding.get("mesh_geometry")
    need(isinstance(geometry, dict) and geometry.get("coordinate_system") == FRAME and
         geometry.get("bounds_semantics") == "bin_edges", "unsupported coordinate system")
    axes = geometry.get("axes", {})
    for name, count, (lo, hi) in zip("xyz", mesh.counts, mesh.bounds):
        axis = axes.get(name, {})
        need(axis.get("bin_count") == count and close_printed(float(axis.get("minimum_cm", math.nan)), lo)
             and close_printed(float(axis.get("maximum_cm", math.nan)), hi)
             and close_printed(float(axis.get("spacing_cm", math.nan)), (hi-lo)/count),
             "bound mesh mismatch")
    pair = execution.get("combined_relative_error_evidence")
    if pair is not None:
        need(isinstance(pair, dict), "invalid combined error evidence")
        normalized = {"schema_version": "dicomxphits_public_tally_geometry_v1",
                      "coordinate_system": FRAME, "bounds_semantics": "bin_edges", "axes": {}}
        for name in "xyz":
            axis = axes[name]
            minimum, maximum = float(axis["minimum_cm"]), float(axis["maximum_cm"])
            minimum = 0.0 if minimum == 0.0 else minimum
            maximum = 0.0 if maximum == 0.0 else maximum
            count = int(axis["bin_count"])
            normalized["axes"][name] = {
                "minimum_cm": minimum, "maximum_cm": maximum, "bin_count": count,
                "spacing_cm": (maximum-minimum)/count,
            }
        need(pair.get("schema_version") == "dicomxphits_sumtally_relative_error_pair_v1" and
             pair.get("semantics") == "phits_3_35_sumtally_isumtally_2_relative_error_v1" and
             pair.get("validated") is True and pair.get("dose_sha256") == dose_sha and
             pair.get("error_sha256") == error_sha and
             pair.get("sum_input_sha256") == execution.get("sum_input_sha256") and
             pair.get("mesh_geometry_sha256") == canonical_manifest_digest(normalized) and
             pair.get("cell_count") == mesh.cells and
             pair.get("pair_metadata_sha256") == canonical_manifest_digest(metadata),
             "combined error evidence mismatch")


def parse_pair(dose_raw: bytes, error_raw: bytes) -> tuple[Mesh, np.ndarray, np.ndarray, dict]:
    try:
        header = dose_raw.split(b"#newpage:", 1)[0].decode("ascii").replace("\r\n", "\n")
        match = re.search(r"(?m)^\s*file\s*=\s*(\S+)", header)
        need(match is not None, "missing output file label")
        fields, _ = _sumtally_output_fields(header, match[1])
    except Exception as exc:
        raise AnalysisError("unsupported combined dose header") from exc
    try:
        mesh = mesh_from_fields(fields, epsout=None)
        values, errors, metadata = paired_sumtally_values(dose_raw, error_raw, mesh, time.monotonic() + 120)
    except Exception as exc:
        raise AnalysisError(f"invalid combined pair: {exc}") from exc
    # PHITS prints each xy page in descending y and ascending x order.
    nx, ny, nz = mesh.counts
    values = values.reshape(nz, ny, nx)[:, ::-1, :].transpose(2, 1, 0).copy()
    errors = errors.reshape(nz, ny, nx)[:, ::-1, :].transpose(2, 1, 0).copy()
    return mesh, values, errors, metadata


def edges(mesh: Mesh) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return tuple(np.linspace(lo, hi, n + 1) for (lo, hi), n in zip(mesh.bounds, mesh.counts))


def sphere(mesh: Mesh, case: dict) -> tuple[np.ndarray, dict]:
    centre = case.get("center_cm", [0, 0, 0])
    need(isinstance(centre, list) and len(centre) == 3, "invalid sphere centre")
    centre = [float(v) for v in centre]
    need(all(math.isfinite(v) for v in centre), "invalid sphere centre")
    has_radius = "radius_cm" in case
    has_volume = "volume_cm3" in case
    need(has_radius != has_volume, "supply exactly one radius_cm or volume_cm3")
    radius = finite_positive(case["radius_cm"], "radius") if has_radius else (
        3 * finite_positive(case["volume_cm3"], "volume") / (4 * math.pi)) ** (1 / 3)
    spacing = finite_positive(case.get("sample_spacing_cm", 0.1), "sampling spacing")
    grid_edges = edges(mesh)
    need(all(c - radius >= e[0] and c + radius <= e[-1] for c, e in zip(centre, grid_edges)),
         "sphere extends outside mesh")
    centres = [(e[:-1] + e[1:]) / 2 for e in grid_edges]
    x, y, z = np.meshgrid(*(v-c for v, c in zip(centres, centre)), indexing="ij")
    mask = x*x + y*y + z*z <= radius*radius
    reach = math.floor(radius / spacing)
    need((2*reach+1)**3 <= 10_000_000, "sampling point limit")
    offsets = np.arange(-reach, reach + 1, dtype=np.float64) * spacing
    sx, sy, sz = np.meshgrid(offsets, offsets, offsets, indexing="ij")
    points = int(np.count_nonzero(sx*sx + sy*sy + sz*sz <= radius*radius))
    return mask, {"center_cm": centre, "radius_cm": radius,
                  "analytic_volume_cm3": 4*math.pi*radius**3/3,
                  "sample_spacing_cm": spacing, "sample_points": points,
                  "sampling_volume_cm3": points*spacing**3}


def structure(mesh: Mesh, case: dict) -> tuple[np.ndarray, dict, str]:
    need("mask" in case and case["mask"], "Structure geometry requires a mask")
    path = Path(case["mask"]).absolute()
    raw = stable_file(path, MAX_MASK)
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            need(len(members) == 6 and sum(x.file_size for x in members) <= MAX_MASK
                 and all(x.file_size <= MAX_MASK and not x.is_dir() for x in members),
                 "mask size or member limit")
        with np.load(io.BytesIO(raw), allow_pickle=False) as data:
            need(set(data.files) == {"mask", "x_edges_cm", "y_edges_cm", "z_edges_cm",
                                      "coordinate_system", "axis_order"}, "invalid mask fields")
            mask = data["mask"]
            need(mask.dtype == np.bool_ and mask.shape == mesh.counts,
                 "mask shape or type mismatch")
            need(str(data["coordinate_system"].item()) == FRAME and
                 str(data["axis_order"].item()) == "xyz", "mask frame or axis order mismatch")
            for axis, expected in zip("xyz", edges(mesh)):
                actual = data[f"{axis}_edges_cm"]
                need(actual.shape == expected.shape and np.issubdtype(actual.dtype, np.number)
                     and np.isfinite(actual).all() and np.array_equal(actual, expected),
                     "mask edges mismatch")
    except AnalysisError:
        raise
    except Exception as exc:
        raise AnalysisError("invalid NPZ mask") from exc
    return mask, {"center_cm": None, "radius_cm": None, "analytic_volume_cm3": None,
                  "sample_spacing_cm": None, "sample_points": None,
                  "sampling_volume_cm3": None}, digest(raw)


def summarize(mask: np.ndarray, values: np.ndarray, errors: np.ndarray, mesh: Mesh,
              geometry: dict) -> dict:
    result = {key: None for key in NUMBER_KEYS}
    result.update(geometry)
    result["native_spacing_cm"] = [(hi-lo)/n for (lo, hi), n in zip(mesh.bounds, mesh.counts)]
    selected = values[mask] * 100
    selected_err = errors[mask]
    count = len(selected)
    result["grid_points"] = count
    result["grid_volume_cm3"] = count * math.prod(result["native_spacing_cm"])
    if not count:
        result.update(status="empty", reason="no native cell centres selected")
        return result
    result.update(voxel_dose_sum_cgy=float(np.sum(selected)), mean_dose_cgy=float(np.mean(selected)),
                  min_dose_cgy=float(np.min(selected)), max_dose_cgy=float(np.max(selected)),
                  spatial_stddev_cgy=float(np.std(selected, ddof=0)))
    eligible = (selected > 0) & (selected_err > 0)
    result["error_eligible_count"] = int(np.count_nonzero(eligible))
    result["zero_dose_count"] = int(np.count_nonzero(selected == 0))
    result["positive_dose_zero_error_count"] = int(np.count_nonzero((selected > 0) & (selected_err == 0)))
    result["error_excluded_count"] = count - result["error_eligible_count"]
    if not result["error_eligible_count"]:
        result.update(status="partial", reason="no positive-dose cells with positive r.err")
        return result
    percentages = selected_err[eligible] * 100
    absolute = selected[eligible] * selected_err[eligible]
    result.update(status="ok", reason=None,
                  mean_voxel_rerr_percent=float(np.mean(percentages)),
                  median_voxel_rerr_percent=float(np.quantile(percentages, .5, method="linear")),
                  p95_voxel_rerr_percent=float(np.quantile(percentages, .95, method="linear")),
                  max_voxel_rerr_percent=float(np.max(percentages)),
                  mean_voxel_standard_error_cgy=float(np.mean(absolute)),
                  max_voxel_standard_error_cgy=float(np.max(absolute)))
    return result


def analyse(case: dict) -> dict:
    source = Source(case["source"])
    selected = {k: relative_name(case[k]) for k in
                ("dose", "error", "generation", "execution", "manifest")}
    need(len(set(selected.values())) == len(selected), "duplicate selected source members")
    raw = {k: source.read(v, MAX_TALLY_BYTES if k in {"dose", "error"} else MAX_JSON)
           for k, v in selected.items()}
    if case.get("retained_dose"):
        retained_name = relative_name(case["retained_dose"])
        need(retained_name not in selected.values(), "duplicate retained dose selector")
        retained = source.read(retained_name, MAX_TALLY_BYTES)
        need(retained == raw["dose"] and
             PurePosixPath(retained_name).parent == PurePosixPath(selected["error"]).parent,
             "retained/official dose mismatch or not co-located")
        selected["retained_dose"] = retained_name
        raw["retained_dose"] = retained
    else:
        need(PurePosixPath(selected["dose"]).parent == PurePosixPath(selected["error"]).parent,
             "dose and error are not co-located; select retained_dose explicitly")
    manifest = json_object(raw["manifest"], "manifest")
    generation = json_object(raw["generation"], "generation")
    execution = json_object(raw["execution"], "execution")
    mesh, values, errors, metadata = parse_pair(raw["dose"], raw["error"])
    dose_name = PurePosixPath(selected["dose"]).name
    need(dose_name == mesh.file and
         PurePosixPath(selected["error"]).name == dose_name.removesuffix(".out") + "_err.out",
         "selected combined pair names mismatch")
    validate_evidence(manifest, generation, execution, digest(raw["dose"]),
                      digest(raw["error"]), metadata, mesh)
    kind = case.get("region_type", "sphere")
    need(kind in {"sphere", "structure", "rtstruct"}, "invalid region type")
    if kind == "sphere":
        mask, geometry = sphere(mesh, case)
        mask_sha = None
        region_label = case.get("region_label", kind)
    elif kind == "structure":
        mask, geometry, mask_sha = structure(mesh, case)
        region_label = case.get("region_label", kind)
    else:
        from phits_roi_rtstruct import StructureBindingError, rtstruct_membership
        try:
            mask, geometry, mask_sha, region_label = rtstruct_membership(
                mesh, case, source, manifest, generation
            )
        except StructureBindingError as exc:
            raise AnalysisError(str(exc)) from exc
    result = summarize(mask, values, errors, mesh, geometry)
    result.update(case_label=case.get("case_label", "case"),
                  region_label=region_label, region_type=kind,
                  dose_basis="validated one-fraction Sumtally Gy converted to cGy once",
                  source_sha256={k: digest(v) for k, v in raw.items()},
                  mask_sha256=mask_sha)
    return result


def neutralize(value):
    if isinstance(value, str) and value and (value[0] in "=+-@" or unicodedata.category(value[0]) == "Cc"):
        return "'" + value
    return value


def publish(rows: list[dict], output_dir: str, stem: str, sources: list[Source],
            extra_inputs: tuple[str, ...] = ()) -> list[str]:
    folder = Path(output_dir).absolute()
    need(folder.is_dir() and not folder.is_symlink(), "output directory must already exist")
    for part in (folder, *folder.parents):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
             "linked/reparse-backed output directory")
    need(not folder.is_relative_to(Path(__file__).resolve().parents[1]),
         "output directory must be outside the repository")
    for source in sources:
        need(not folder.is_relative_to(source.path) and not source.path.is_relative_to(folder),
             "output directory overlaps source")
    for name in extra_inputs:
        path = Path(name).absolute()
        need(not folder.is_relative_to(path if path.is_dir() else path.parent)
             and not path.is_relative_to(folder),
             "output directory overlaps selected DICOM evidence")
    need(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", stem) is not None,
         "unsafe report stem")
    definitions = {
        "dose": "One-fraction Gy x 100; voxel-dose sum is grid-dependent, not energy or mean",
        "spatial_stddev": "population standard deviation (ddof=0), not Monte Carlo error",
        "rerr": "unweighted positive-dose/positive-r.err voxel values; no low-dose threshold; linear quantiles",
        "voxel_standard_error": "per-voxel dose x r.err; no ROI-mean uncertainty or covariance estimate",
        "sampling": "sphere-centred lattice count x spacing cubed; not geometric volume",
    }
    public_rows = [{k: v for k, v in row.items() if k != "source"} for row in rows]
    json_bytes = (json.dumps({"schema_version": SCHEMA, "definitions": definitions,
                              "results": public_rows}, ensure_ascii=False,
                             allow_nan=False, indent=2) + "\n").encode("utf-8")
    fields = ["case_label", "region_label", "region_type", "status", "reason",
              "dose_basis", "center_cm", "native_spacing_cm", *NUMBER_KEYS,
              "source_sha256", "mask_sha256"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: neutralize(json.dumps(row[k], ensure_ascii=False) if isinstance(row.get(k), (list, dict))
                                    else row.get(k, "")) if row.get(k) is not None else ""
                         for k in fields})
    created = []
    for suffix, content in (("json", json_bytes), ("csv", buffer.getvalue().encode("utf-8"))):
        destination = folder / f"{stem}.{suffix}"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".roi-", dir=folder, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, destination)
        except OSError as exc:
            raise AnalysisError(f"report publication failed; already published: {created}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        created.append(destination.name)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", help="JSON with a cases array of explicit case selectors")
    for name in ("source", "dose", "error", "generation", "execution", "manifest",
                 "retained-dose", "mask", "case-label", "region-label", "region-type",
                 "workspace", "ct-reference", "rtplan", "rtstruct", "preparation",
                 "roi-number"):
        parser.add_argument("--" + name)
    parser.add_argument("--center-cm", nargs=3, type=float)
    parser.add_argument("--radius-cm", type=float)
    parser.add_argument("--volume-cm3", type=float)
    parser.add_argument("--sample-spacing-cm", type=float)
    parser.add_argument("--output-dir")
    parser.add_argument("--report-stem", default="phits-roi-statistics")
    args = parser.parse_args(argv)
    if args.batch:
        path = Path(args.batch).absolute()
        cases = json_object(stable_file(path, MAX_JSON), "batch").get("cases")
        need(isinstance(cases, list) and 0 < len(cases) <= MAX_CASES, "invalid batch cases")
        for case in cases:
            need(isinstance(case, dict), "invalid batch case")
            for key in ("source", "mask", "workspace", "ct_reference", "rtplan", "rtstruct"):
                if case.get(key) and not Path(case[key]).is_absolute():
                    case[key] = str(path.parent / case[key])
    else:
        raw = vars(args)
        cases = [{k: v for k, v in raw.items() if k not in {"batch", "output_dir", "report_stem"}
                  and v is not None}]
    rows = []
    sources = []
    for case in cases:
        try:
            sources.append(Source(case["source"]))
            row = analyse(case)
        except (AnalysisError, KeyError, TypeError, ValueError, OSError) as exc:
            row = {key: None for key in NUMBER_KEYS}
            row.update({"center_cm": None, "native_spacing_cm": None,
                        "source_sha256": None, "mask_sha256": None})
            row.update({"case_label": case.get("case_label", "case"),
                        "region_label": case.get("region_label", "region"),
                        "region_type": case.get("region_type", "sphere"),
                        "status": "invalid", "reason": str(exc) if isinstance(exc, AnalysisError)
                        else "invalid selected case or unreadable input"})
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "source_sha256"},
                         ensure_ascii=False, allow_nan=False))
    if args.output_dir:
        try:
            extra = tuple(case[key] for case in cases for key in
                          ("workspace", "ct_reference", "rtplan", "rtstruct") if case.get(key))
            created = publish(rows, args.output_dir, args.report_stem, sources, extra)
            print("Published: " + ", ".join(created))
        except AnalysisError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 1 if any(r["status"] in {"invalid", "empty"} for r in rows) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AnalysisError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
