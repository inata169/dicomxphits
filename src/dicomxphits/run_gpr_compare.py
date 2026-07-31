from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import pydicom


SCHEMA_VERSION = "dicomxphits_public_gpr_handoff_v1"
DEFAULT_REPORT_STEM = "run3d"
DEFAULT_STDOUT_NAME = "rtgamma.stdout.txt"
DEFAULT_STDERR_NAME = "rtgamma.stderr.txt"


def _artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False, "size": None, "mtime_ns": None}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _python_available(python_executable: str) -> bool:
    path = Path(python_executable)
    if path.is_absolute() or path.parent != Path("."):
        return path.is_file()
    return shutil.which(python_executable) is not None


def _dose_identity(path: Path, *, role: str) -> dict[str, Any]:
    dataset = pydicom.dcmread(str(path), stop_before_pixels=True)
    modality = str(getattr(dataset, "Modality", "") or "").upper()
    dose_units = str(getattr(dataset, "DoseUnits", "") or "").upper()
    frame_uid = str(getattr(dataset, "FrameOfReferenceUID", "") or "")
    if modality != "RTDOSE":
        raise ValueError(f"{role} must be an RTDOSE DICOM: {path}")
    if dose_units != "GY":
        raise ValueError(f"{role} DoseUnits must be GY: {path}")
    if not frame_uid:
        raise ValueError(f"{role} is missing FrameOfReferenceUID: {path}")
    return {
        "role": role,
        "path": str(path),
        "modality": modality,
        "dose_units": dose_units,
        "frame_of_reference_uid": frame_uid,
    }


def gamma_criteria(*, dd_percent: float, dta_mm: float, cutoff_percent: float) -> dict[str, Any]:
    for name, value in {
        "dd_percent": dd_percent,
        "dta_mm": dta_mm,
        "cutoff_percent": cutoff_percent,
    }.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")
    return {
        "mode": "3d",
        "dd_percent": float(dd_percent),
        "dta_mm": float(dta_mm),
        "cutoff_percent": float(cutoff_percent),
        "gamma_type": "global",
        "normalization": "global_max",
    }


def build_command(
    *,
    python_executable: str,
    reference_rtdose: Path,
    evaluation_rtdose: Path,
    report_base: Path,
    criteria: dict[str, Any],
) -> list[str]:
    return [
        python_executable,
        "-m",
        "rtgamma.main",
        "--ref",
        str(reference_rtdose),
        "--eval",
        str(evaluation_rtdose),
        "--mode",
        "3d",
        "--dd",
        str(criteria["dd_percent"]),
        "--dta",
        str(criteria["dta_mm"]),
        "--cutoff",
        str(criteria["cutoff_percent"]),
        "--gamma-type",
        "global",
        "--norm",
        "global_max",
        "--report",
        str(report_base),
    ]


def _skip_summary(
    *,
    reason: str,
    reference_rtdose: Path,
    evaluation_rtdose: Path,
    output_dir: Path,
    gpr_root: Path | None,
    criteria: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "skipped",
        "skip_reason": reason,
        "failure_reason": None,
        "gpr_comparing_available": False,
        "gpr_comparing_executed": False,
        "reference_rtdose": str(reference_rtdose),
        "evaluation_rtdose": str(evaluation_rtdose),
        "output_dir": str(output_dir),
        "gpr_root": str(gpr_root) if gpr_root is not None else None,
        "gamma_criteria": criteria,
        "claim_boundary": (
            "External research comparison handoff only; no clinical validity claim."
        ),
    }


def run_adapter(
    *,
    reference_rtdose: Path,
    evaluation_rtdose: Path,
    output_dir: Path,
    gpr_root: Path | None,
    execute: bool = False,
    python_executable: str = sys.executable,
    dd_percent: float = 3.0,
    dta_mm: float = 2.0,
    cutoff_percent: float = 10.0,
    timeout_seconds: float | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    reference_rtdose = reference_rtdose.resolve()
    evaluation_rtdose = evaluation_rtdose.resolve()
    output_dir = output_dir.resolve()
    gpr_root = gpr_root.resolve() if gpr_root is not None else None
    output_dir.mkdir(parents=True, exist_ok=True)
    criteria = gamma_criteria(
        dd_percent=dd_percent,
        dta_mm=dta_mm,
        cutoff_percent=cutoff_percent,
    )

    if gpr_root is None:
        return _skip_summary(
            reason="GPR-comparing root was not configured",
            reference_rtdose=reference_rtdose,
            evaluation_rtdose=evaluation_rtdose,
            output_dir=output_dir,
            gpr_root=None,
            criteria=criteria,
        )
    entrypoint = gpr_root / "rtgamma" / "main.py"
    if not entrypoint.is_file():
        return _skip_summary(
            reason=f"GPR-comparing import path not found: {entrypoint}",
            reference_rtdose=reference_rtdose,
            evaluation_rtdose=evaluation_rtdose,
            output_dir=output_dir,
            gpr_root=gpr_root,
            criteria=criteria,
        )
    if not _python_available(python_executable):
        return _skip_summary(
            reason=f"GPR-comparing Python executable not found: {python_executable}",
            reference_rtdose=reference_rtdose,
            evaluation_rtdose=evaluation_rtdose,
            output_dir=output_dir,
            gpr_root=gpr_root,
            criteria=criteria,
        )

    report_base = output_dir / DEFAULT_REPORT_STEM
    report_json = report_base.with_suffix(".json")
    stdout_path = output_dir / DEFAULT_STDOUT_NAME
    stderr_path = output_dir / DEFAULT_STDERR_NAME
    command = build_command(
        python_executable=python_executable,
        reference_rtdose=reference_rtdose,
        evaluation_rtdose=evaluation_rtdose,
        report_base=report_base,
        criteria=criteria,
    )
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "configured_only",
        "skip_reason": None,
        "failure_reason": None,
        "gpr_comparing_available": True,
        "gpr_comparing_executed": False,
        "reference_rtdose": str(reference_rtdose),
        "evaluation_rtdose": str(evaluation_rtdose),
        "output_dir": str(output_dir),
        "gpr_root": str(gpr_root),
        "command": command,
        "cwd": str(gpr_root),
        "gamma_criteria": criteria,
        "primary_report_json": str(report_json),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "claim_boundary": (
            "External research comparison handoff only; no clinical validity claim."
        ),
    }
    if not execute:
        return summary

    try:
        reference_identity = _dose_identity(reference_rtdose, role="reference")
        evaluation_identity = _dose_identity(evaluation_rtdose, role="evaluation")
    except Exception as exc:
        summary.update(status="failed", failure_reason=str(exc))
        return summary
    summary["dose_identity"] = {
        "reference": reference_identity,
        "evaluation": evaluation_identity,
    }
    if (
        reference_identity["frame_of_reference_uid"]
        != evaluation_identity["frame_of_reference_uid"]
    ):
        summary.update(
            status="failed",
            failure_reason="FrameOfReferenceUID mismatch before GPR-comparing execution",
        )
        return summary

    report_before = _artifact(report_json)
    result = runner(
        command,
        cwd=str(gpr_root),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")
    summary["gpr_comparing_executed"] = True
    summary["returncode"] = int(result.returncode)
    report_after = _artifact(report_json)
    summary["report_artifact_before"] = report_before
    summary["report_artifact"] = report_after
    if result.returncode != 0:
        summary.update(
            status="failed",
            failure_reason=f"GPR-comparing exited with return code {result.returncode}",
        )
        return summary
    if not report_after["exists"] or report_after == report_before:
        summary.update(
            status="failed",
            failure_reason="GPR-comparing did not create a fresh run3d.json",
        )
        return summary
    try:
        report = json.loads(report_json.read_text(encoding="utf-8"))
        pass_rate = float(report["pass_rate_percent"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        summary.update(
            status="failed",
            failure_reason=f"Invalid GPR-comparing report: {exc}",
        )
        return summary
    summary.update(
        status="completed",
        pass_rate_percent=pass_rate,
        report_artifact=_artifact(report_json),
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or execute the external GPR-comparing research handoff. "
            "GPR-comparing is not bundled with dicomxphits."
        )
    )
    parser.add_argument("--reference-rtdose", required=True)
    parser.add_argument("--evaluation-rtdose", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gpr-root")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dd", type=float, default=3.0)
    parser.add_argument("--dta", type=float, default=2.0)
    parser.add_argument("--cutoff", type=float, default=10.0)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--summary-json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    output_dir = Path(args.output_dir)
    summary = run_adapter(
        reference_rtdose=Path(args.reference_rtdose),
        evaluation_rtdose=Path(args.evaluation_rtdose),
        output_dir=output_dir,
        gpr_root=Path(args.gpr_root) if args.gpr_root else None,
        execute=args.execute,
        python_executable=args.python_executable,
        dd_percent=args.dd,
        dta_mm=args.dta,
        cutoff_percent=args.cutoff,
        timeout_seconds=args.timeout_seconds,
    )
    summary_path = (
        Path(args.summary_json)
        if args.summary_json
        else output_dir / "gpr_handoff_summary.json"
    )
    _write_json(summary_path, summary)
    print(summary_path)
    return 3 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
