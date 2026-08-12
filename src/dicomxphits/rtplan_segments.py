#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dicomxphits.rtplan_helpers import (
    as_float,
    dcm_get,
)
from dicomxphits.csv_security import neutralize_external_csv_value
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.rtplan_manifest_construction import (
    DEFAULT_TOLERANCES,
    DELIVERY_TYPES,
    MIDPOINT_APPROXIMATION,
    SCHEMA_VERSION,
    SUBINTERVAL_APPROXIMATION,
    build_manifest as _build_manifest,
)
from dicomxphits.rtplan_state import (
    beam_number,
    carried_control_point_states,
)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency guard
    yaml = None


WORKFLOW_MODES = ("full_plan", "selected_beam", "dry_run")
DEFAULT_EXPECTED_OUTPUT_NAME = "deposit-target-3D.out"
DEFAULT_SAMPLING_POLICY = {
    "static_imrt": {
        "interval_subdivision": 1,
        "skip_zero_mu_intervals": True,
    },
    "dynamic_imrt": {
        "interval_subdivision": 2,
        "interpolation": "linear",
        "sampling_point": "midpoint",
        "skip_zero_mu_intervals": True,
    },
    "vmat": {
        "interval_subdivision": 2,
        "interpolation": "linear",
        "sampling_point": "midpoint",
        "skip_zero_mu_intervals": True,
    },
}


def finite_positive(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > 0.0


def positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(value)


def validate_sampling_policy(policy: dict[str, dict[str, Any]]) -> None:
    for delivery_type in ("static_imrt", "dynamic_imrt", "vmat"):
        settings = policy.get(delivery_type)
        if not isinstance(settings, dict):
            raise ValueError(f"rtplan_sampling.{delivery_type} must be configured")
        subdivision = positive_int(
            settings.get("interval_subdivision"),
            label=f"rtplan_sampling.{delivery_type}.interval_subdivision",
        )
        if delivery_type == "static_imrt" and subdivision != 1:
            raise ValueError("Static IMRT interval_subdivision > 1 is unsupported in this version")
        interpolation = str(settings.get("interpolation", "linear"))
        if delivery_type in {"dynamic_imrt", "vmat"} and interpolation != "linear":
            raise ValueError(f"rtplan_sampling.{delivery_type}.interpolation must be linear")
        sampling_point = str(settings.get("sampling_point", "midpoint"))
        if delivery_type in {"dynamic_imrt", "vmat"} and sampling_point != "midpoint":
            raise ValueError(f"rtplan_sampling.{delivery_type}.sampling_point must be midpoint")


def deep_merge_sampling_policy(overrides: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    policy = deepcopy(DEFAULT_SAMPLING_POLICY)
    for delivery_type, values in (overrides or {}).items():
        if delivery_type not in policy:
            raise ValueError(f"Unsupported rtplan_sampling delivery type: {delivery_type}")
        if not isinstance(values, dict):
            raise ValueError(f"rtplan_sampling.{delivery_type} must be a mapping")
        policy[delivery_type].update(values)
    validate_sampling_policy(policy)
    return policy


def load_sampling_policy(path: Path | None = None) -> tuple[dict[str, dict[str, Any]], str | None]:
    if path is None:
        return deep_merge_sampling_policy(), None
    if yaml is None:
        raise RuntimeError("PyYAML is required to read rtplan sampling config")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Sampling config must be a YAML mapping: {path}")
    root = data.get("rtplan_sampling")
    if not isinstance(root, dict):
        raise ValueError(f"Sampling config must contain a rtplan_sampling mapping: {path}")
    return deep_merge_sampling_policy(root), str(path)


def load_rtplan(path: Path) -> Any:
    try:
        import pydicom  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("pydicom is required to read RT Plan DICOM files") from exc
    return pydicom.dcmread(str(path), stop_before_pixels=True, force=True)

def parse_beam_filter(values: list[str] | None) -> set[int] | None:
    if not values:
        return None
    selected: set[int] = set()
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                selected.add(int(part))
    return selected


def build_manifest(
    ds: Any,
    *,
    case_id: str,
    workflow_mode: str,
    include_beams: set[int] | None,
    dose_normalization_mu: float | None,
    output_name: str,
    tolerances: dict[str, float] | None = None,
    sampling_policy: dict[str, dict[str, Any]] | None = None,
    sampling_config_path: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    return _build_manifest(
        ds,
        case_id=case_id,
        workflow_mode=workflow_mode,
        include_beams=include_beams,
        dose_normalization_mu=dose_normalization_mu,
        output_name=output_name,
        tolerances=tolerances,
        sampling_policy=deep_merge_sampling_policy(sampling_policy),
        sampling_config_path=sampling_config_path,
        states_table_builder=states_table,
    )


def states_table(ds: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for beam in dcm_get(ds, "BeamSequence", []) or []:
        bnum = beam_number(beam)
        for state in carried_control_point_states(beam):
            rows.append(
                {
                    "beam_number": bnum,
                    "control_point_index": state.get("control_point_index"),
                    "cmw": state.get("cmw"),
                    "gantry_angle_deg": state.get("gantry_angle_deg"),
                    "gantry_rotation_direction": state.get("gantry_rotation_direction"),
                    "collimator_angle_deg": state.get("collimator_angle_deg"),
                    "couch_angle_deg": state.get("couch_angle_deg"),
                    "mlc_type": state.get("mlc_type"),
                    "leaf_pair_count": state.get("leaf_pair_count"),
                }
            )
    return rows


def write_json(path: Path, data: Any, *, guard: WorkspaceOutputGuard) -> None:
    guard.write_text(
        path,
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    *,
    guard: WorkspaceOutputGuard,
) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: neutralize_external_csv_value(row.get(key, ""))
                for key in fieldnames
            }
        )
    guard.write_text(path, stream.getvalue(), newline="")


def write_outputs(case_root: Path, manifest: dict[str, Any], beam_rows: list[dict[str, Any]], cp_rows: list[dict[str, Any]]) -> None:
    with WorkspaceOutputGuard(case_root, create_root=True) as guard:
        _write_outputs_guarded(case_root, manifest, beam_rows, cp_rows, guard=guard)


def _write_outputs_guarded(
    case_root: Path,
    manifest: dict[str, Any],
    beam_rows: list[dict[str, Any]],
    cp_rows: list[dict[str, Any]],
    *,
    guard: WorkspaceOutputGuard,
) -> None:
    write_json(
        case_root / "segments" / "segment_manifest.json", manifest, guard=guard
    )
    segment_rows = [
        {
            "beam_number": s.get("beam_number"),
            "beam_name": s.get("beam_name"),
            "delivery_type": s.get("delivery_type"),
            "segment_index": s.get("segment_index"),
            "cp_start": s.get("cp_start"),
            "cp_end": s.get("cp_end"),
            "cmw_start": s.get("cmw_start"),
            "cmw_end": s.get("cmw_end"),
            "delta_cmw_raw": s.get("delta_cmw_raw"),
            "segment_weight": s.get("segment_weight"),
            "segment_mu": s.get("segment_mu"),
            "source_interval_index": s.get("source_interval_index"),
            "source_interval_positive_index": s.get("source_interval_positive_index"),
            "subinterval_index": s.get("subinterval_index"),
            "subinterval_count": s.get("subinterval_count"),
            "subinterval_t_start": s.get("subinterval_t_start"),
            "subinterval_t_mid": s.get("subinterval_t_mid"),
            "subinterval_t_end": s.get("subinterval_t_end"),
            "source_segment_mu": s.get("source_segment_mu"),
            "subinterval_segment_mu": s.get("subinterval_segment_mu"),
            "skip_reason": s.get("skip_reason") or "",
            "expected_output_path": s.get("expected_output_path"),
            "warnings": "; ".join(s.get("warnings", [])),
        }
        for s in manifest["segments"]
    ]
    write_csv(
        case_root / "segments" / "segment_table.csv",
        segment_rows,
        [
            "beam_number",
            "beam_name",
            "delivery_type",
            "segment_index",
            "cp_start",
            "cp_end",
            "cmw_start",
            "cmw_end",
            "delta_cmw_raw",
            "segment_weight",
            "segment_mu",
            "source_interval_index",
            "source_interval_positive_index",
            "subinterval_index",
            "subinterval_count",
            "subinterval_t_start",
            "subinterval_t_mid",
            "subinterval_t_end",
            "source_segment_mu",
            "subinterval_segment_mu",
            "skip_reason",
            "expected_output_path",
            "warnings",
        ],
        guard=guard,
    )
    write_json(
        case_root / "analysis" / "rtplan_summary.json",
        {
            "case_id": manifest["case_id"],
            "plan_uid": manifest["plan_uid"],
            "workflow_mode": manifest["workflow_mode"],
            "plan_total_mu": manifest["plan_total_mu"],
            "included_total_mu": manifest["included_total_mu"],
            "dose_normalization_mu": manifest["dose_normalization_mu"],
            "rtplan_sampling": manifest.get("rtplan_sampling"),
            "sampling_config_path": manifest.get("sampling_config_path"),
            "sampling_policy_role": manifest.get("sampling_policy_role"),
            "beam_count": len(beam_rows),
            "segment_count": len([s for s in manifest["segments"] if not s.get("skip_reason")]),
            "skipped_segment_count": len([s for s in manifest["segments"] if s.get("skip_reason")]),
            "warnings": manifest.get("warnings", []),
        },
        guard=guard,
    )
    write_csv(
        case_root / "analysis" / "beam_summary.csv",
        beam_rows,
        [
            "beam_number",
            "beam_name",
            "beam_meterset_mu",
            "final_cumulative_meterset_weight",
            "delivery_type",
            "segment_count",
            "skipped_segment_count",
            "sampling_policy",
            "warnings",
        ],
        guard=guard,
    )
    write_csv(
        case_root / "analysis" / "control_point_table.csv",
        cp_rows,
        [
            "beam_number",
            "control_point_index",
            "cmw",
            "gantry_angle_deg",
            "gantry_rotation_direction",
            "collimator_angle_deg",
            "couch_angle_deg",
            "mlc_type",
            "leaf_pair_count",
        ],
        guard=guard,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export 3D CRT/static IMRT segment manifest from DICOM RT Plan")
    parser.add_argument("--rtplan", required=True, help="Path to DICOM RT Plan")
    parser.add_argument("--case-root", required=True, help="Output case root")
    parser.add_argument("--case-id", default=None, help="Case identifier; defaults to RTPlanLabel or RT Plan filename")
    parser.add_argument("--workflow-mode", choices=WORKFLOW_MODES, default="full_plan")
    parser.add_argument("--include-beams", nargs="*", help="Beam numbers to include; accepts comma-separated values")
    parser.add_argument("--dose-normalization-mu", type=float, default=None)
    parser.add_argument("--expected-output-name", default=DEFAULT_EXPECTED_OUTPUT_NAME)
    parser.add_argument(
        "--sampling-config",
        default=None,
        help="rtplan_sampling.yaml workflow approximation policy; defaults to the built-in policy",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rtplan_path = Path(args.rtplan)
    if not rtplan_path.exists():
        print(f"ERROR: RT Plan not found: {rtplan_path}", file=sys.stderr)
        return 1
    try:
        ds = load_rtplan(rtplan_path)
        case_id = args.case_id or str(dcm_get(ds, "RTPlanLabel", "") or rtplan_path.stem)
        sampling_policy, sampling_config_path = load_sampling_policy(Path(args.sampling_config) if args.sampling_config else None)
        manifest, beam_rows, cp_rows = build_manifest(
            ds,
            case_id=case_id,
            workflow_mode=args.workflow_mode,
            include_beams=parse_beam_filter(args.include_beams),
            dose_normalization_mu=args.dose_normalization_mu,
            output_name=args.expected_output_name,
            sampling_policy=sampling_policy,
            sampling_config_path=sampling_config_path,
        )
        write_outputs(Path(args.case_root), manifest, beam_rows, cp_rows)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Exported {len(manifest['segments'])} segment row(s) to {args.case_root}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
