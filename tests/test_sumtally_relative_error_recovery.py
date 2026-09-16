from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import dicomxphits.sumtally_relative_error_recovery as recovery
from dicomxphits.gui import _current_sumtally_binding
from dicomxphits.run_segments import phits_error_output_path
from dicomxphits.sumtally_inputs import (
    ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION,
    file_sha256,
    manifest_sha256,
)


GEOMETRY = {
    "axes": {
        "x": {"minimum_cm": -0.1, "maximum_cm": 0.1, "bin_count": 2},
        "y": {"minimum_cm": -0.05, "maximum_cm": 0.05, "bin_count": 1},
        "z": {"minimum_cm": -0.1, "maximum_cm": 0.1, "bin_count": 2},
    }
}


def _header(*, output: bool, epsout: str | None = "1") -> str:
    rows = [
        "title = Synthetic retained recovery fixture",
        "mesh = xyz",
        "x-type = 2",
        "xmin = -0.100000",
        "xmax = 0.100000",
        "nx = 2",
        "y-type = 2",
        "ymin = -0.050000",
        "ymax = 0.050000",
        "ny = 1",
        "z-type = 2",
        "zmin = -0.100000",
        "zmax = 0.100000",
        "nz = 2",
        "unit = 0",
        "material = all",
        "output = dose",
        "axis = xy",
        "file = dose.out",
        "part = all",
    ]
    if epsout is not None:
        rows.append(f"epsout = {epsout}")
    if output:
        rows.extend(
            ("letmat = 0", "dedxfnc = 0", "deposit = 0", "2D-type = 3", "mother = all")
        )
    return "\n".join(rows) + "\n"


def _deck() -> str:
    return (
        "$OMP = 2\n[ Parameters ]\n icntl = 13\n maxcas = 10\n maxbch = 10\n"
        " istdev = -1\n[ T-Deposit ]\n"
        + _header(output=False, epsout="0")
        + " infl:{sumtally.inp}\n"
    )


def _tally(values: list[float], *, role: str = "dose") -> bytes:
    rows = [
        "[ T-Deposit ]",
        _header(output=True, epsout=None),
        "sumtally start",
        "isumtally = 2",
        "nfile = 1",
        "segments/seg_001/dose.out",
        "1.0",
        "sfile = dose.out",
        "sumfactor = 1.0",
        "sumtally end",
        "#newpage:",
    ]
    for index in range(1, 3):
        if index > 1:
            rows.append(" newpage:")
        page = values[(index - 1) * 2 : index * 2]
        zlo = -0.1 + (index - 1) * 0.1
        zhi = zlo + 0.1
        rows.extend(
            (
                f"#   no. ={index:3d}   iz  ={index:3d}   part. = all",
                f"#   z = ( {zlo:.4E} - {zhi:.4E} )",
                f"'no. ={index:3d},  iz ={index:3d}'",
                "msuc: {Synthetic retained recovery fixture}",
                r"msdl: {\it calculated by \PHITS  3.35}",
                "#  ny =   1   nx =   2",
                "# ( ( data(x,y), x = 1, nx ), y = ny, 1, -1 )",
                "",
                "hc:  y = 0.0000000 to 0.0000000 by 0.1000000 ; x = -0.05000000 to 0.05000000 by 0.1000000 ;",
                " ".join(str(value) for value in page),
                "",
                "#" + "-" * 78,
                "hc: y= 0.005 to 0.995 by 0.01 ; x= 0.5 to 0.5 by 1 ;",
                " ".join(str(value) for value in range(1, 101)),
                "z: xorg(0.0)",
                "y: " + ("Dose [Gy/source]" if role == "dose" else "Relative Error"),
                "e:",
                "z: xorg[-1.03/0.05]",
                "p: ymin(-1) ymax(1)",
                "",
            )
        )
    return ("\n".join(rows) + "\n").encode("ascii")


def _workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "workspace"
    analysis = root / "analysis"
    sumtally = root / "sumtally"
    segments = root / "segments"
    analysis.mkdir(parents=True)
    sumtally.mkdir()
    segments.mkdir()
    (root / ".dicomxphits-execution.lock").write_bytes(b"")

    manifest = {"schema_version": "synthetic_manifest_v1"}
    manifest_path = segments / "segment_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sum_input = sumtally / "segment_sum.inp"
    sum_input.write_text(_deck(), encoding="utf-8")
    sumtally_input = sumtally / "sumtally.inp"
    sumtally_input.write_text("sumtally start\nisumtally = 2\nsumtally end\n", encoding="utf-8")
    dose = sumtally / "dose.out"
    dose.write_bytes(_tally([10.0, 8.0, 6.0, 4.0]))

    bound_manifest_sha256 = manifest_sha256(manifest)
    generation = {
        "schema_version": recovery.GENERATION_SCHEMA_VERSION,
        "stage_status": "success",
        "workspace_root": str(root.resolve()),
        "manifest_sha256": bound_manifest_sha256,
        "sum_input_sha256": file_sha256(sum_input),
        "sumtally_input_sha256": file_sha256(sumtally_input),
        "segment_output_evidence": [],
        "wrapper_include_evidence": [
            {"path": str(sumtally_input.resolve()), "sha256": file_sha256(sumtally_input)}
        ],
        "outputs": {
            "sum_input": str(sum_input.resolve()),
            "sumtally_input": str(sumtally_input.resolve()),
            "sumtally_output": str(dose.resolve()),
        },
        "sumtally_normalization": ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION,
        "sumtally_normalization_evidence": {"synthetic": True},
    }
    execution = {
        **{key: value for key, value in generation.items() if key != "outputs"},
        "schema_version": recovery.EXECUTION_SCHEMA_VERSION,
        "expected_sumtally_output": str(dose.resolve()),
        "expected_sumtally_output_updated_by_run": True,
        "expected_sumtally_output_sha256": file_sha256(dose),
        "combined_relative_error_evidence": None,
    }
    (analysis / "sumtally_generation_summary.json").write_text(
        json.dumps(generation), encoding="utf-8"
    )
    (analysis / "sumtally_execution_summary.json").write_text(
        json.dumps(execution), encoding="utf-8"
    )

    binding = {
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": bound_manifest_sha256,
        "sum_input_sha256": file_sha256(sum_input),
        "sumtally_input_sha256": file_sha256(sumtally_input),
        "sumtally_output_path": str(dose.resolve()),
        "sumtally_output_sha256": file_sha256(dose),
        "tally_geometry_binding": {"mesh_geometry": GEOMETRY},
    }
    monkeypatch.setattr(
        recovery,
        "validate_sumtally_manifest_binding",
        lambda **_kwargs: binding,
    )

    staging = root / ".sumtally-run-0123456789abcdef"
    staging.mkdir()
    (staging / sum_input.name).write_bytes(sum_input.read_bytes())
    (staging / sumtally_input.name).write_bytes(sumtally_input.read_bytes())
    (staging / dose.name).write_bytes(dose.read_bytes())
    phits_error_output_path(staging / dose.name).write_bytes(
        _tally([0.1, 0.2, 0.3, 0.4], role="error")
    )
    return root, staging


def test_preview_and_apply_publish_only_error_and_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    generation = root / recovery.GENERATION_RELATIVE_PATH
    execution = root / recovery.EXECUTION_RELATIVE_PATH
    dose = root / "sumtally/dose.out"
    protected = {path: path.read_bytes() for path in (generation, execution, dose)}
    staging_before = {
        path.relative_to(staging): path.read_bytes()
        for path in staging.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("recovery must not start an external tool"),
    )

    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    assert preview["status"] == "eligible"
    assert preview["plan"]["destination_state"] == "missing_error_and_receipt"
    assert not (root / recovery.RECEIPT_RELATIVE_PATH).exists()
    assert not (root / "sumtally/dose_err.out").exists()

    result = recovery.apply_sumtally_relative_error_recovery(
        root, staging, preview["recovery_plan_sha256"]
    )
    assert result["status"] == "recovered"
    assert (root / "sumtally/dose_err.out").is_file()
    assert (root / recovery.RECEIPT_RELATIVE_PATH).is_file()
    assert all(path.read_bytes() == content for path, content in protected.items())
    assert {
        path.relative_to(staging): path.read_bytes()
        for path in staging.rglob("*")
        if path.is_file()
    } == staging_before
    pair, _receipt_sha256 = recovery.resolved_combined_relative_error_evidence(root)
    assert pair["error_sha256"] == file_sha256(root / "sumtally/dose_err.out")


def test_apply_rejects_stale_plan_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    (staging / "dose_err.out").write_bytes(
        _tally([0.4, 0.3, 0.2, 0.1], role="error")
    )

    with pytest.raises(recovery.SumtallyRelativeErrorRecoveryUnavailable, match="plan changed"):
        recovery.apply_sumtally_relative_error_recovery(
            root, staging, preview["recovery_plan_sha256"]
        )
    assert not (root / "sumtally/dose_err.out").exists()
    assert not (root / recovery.RECEIPT_RELATIVE_PATH).exists()


def test_apply_validates_temporary_copy_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    original_copy = recovery.WorkspaceOutputGuard.copy_file

    def copy_changed_source(self, source, destination, *, overwrite=True):
        Path(source).write_bytes(_tally([0.4, 0.3, 0.2, 0.1], role="error"))
        return original_copy(self, source, destination, overwrite=overwrite)

    monkeypatch.setattr(
        recovery.WorkspaceOutputGuard,
        "copy_file",
        copy_changed_source,
    )
    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match="changed while being copied",
    ):
        recovery.apply_sumtally_relative_error_recovery(
            root, staging, preview["recovery_plan_sha256"]
        )
    assert not (root / "sumtally/dose_err.out").exists()
    assert not (root / recovery.RECEIPT_RELATIVE_PATH).exists()


def test_interrupted_error_publication_requires_new_resume_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    original_write_json = recovery.WorkspaceOutputGuard.write_json

    def interrupt_receipt(self, path, value, *, overwrite=True):
        if recovery.RECEIPT_RELATIVE_PATH.name in Path(path).name:
            raise OSError("synthetic receipt interruption")
        return original_write_json(self, path, value, overwrite=overwrite)

    monkeypatch.setattr(recovery.WorkspaceOutputGuard, "write_json", interrupt_receipt)
    with pytest.raises(OSError, match="synthetic receipt interruption"):
        recovery.apply_sumtally_relative_error_recovery(
            root, staging, preview["recovery_plan_sha256"]
        )
    assert (root / "sumtally/dose_err.out").is_file()
    assert not (root / recovery.RECEIPT_RELATIVE_PATH).exists()

    resume = recovery.preview_sumtally_relative_error_recovery(root, staging)
    assert resume["plan"]["destination_state"] == "identical_existing_error_without_receipt"
    assert resume["recovery_plan_sha256"] != preview["recovery_plan_sha256"]
    monkeypatch.setattr(recovery.WorkspaceOutputGuard, "write_json", original_write_json)
    recovery.apply_sumtally_relative_error_recovery(
        root, staging, resume["recovery_plan_sha256"]
    )
    assert (root / recovery.RECEIPT_RELATIVE_PATH).is_file()


def test_conflicting_error_and_invalid_receipt_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    official_error = root / "sumtally/dose_err.out"
    official_error.write_bytes(b"conflicting error")
    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match="conflicts",
    ):
        recovery.preview_sumtally_relative_error_recovery(root, staging)
    official_error.unlink()
    receipt = root / recovery.RECEIPT_RELATIVE_PATH
    receipt.write_text("{}\n", encoding="utf-8")
    before = receipt.read_bytes()
    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match="existing recovery receipt is invalid",
    ):
        recovery.preview_sumtally_relative_error_recovery(root, staging)
    assert receipt.read_bytes() == before
    assert not official_error.exists()


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("retained_dose", "byte-identical"),
        ("malformed_error", "retained combined dose/error pair is invalid"),
        ("changed_include", "does not match recorded.*evidence"),
        ("direct_evidence", "direct combined relative-error evidence"),
    ],
)
def test_preview_rejects_changed_or_unsupported_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    if mutation == "retained_dose":
        (staging / "dose.out").write_bytes(b"different retained dose")
    elif mutation == "malformed_error":
        (staging / "dose_err.out").write_bytes(b"malformed retained error")
    elif mutation == "changed_include":
        (root / "sumtally/sumtally.inp").write_text("changed\n", encoding="utf-8")
    else:
        execution_path = root / recovery.EXECUTION_RELATIVE_PATH
        execution = json.loads(execution_path.read_text(encoding="utf-8"))
        execution["combined_relative_error_evidence"] = {"conflicting": True}
        execution_path.write_text(json.dumps(execution), encoding="utf-8")

    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match=message,
    ):
        recovery.preview_sumtally_relative_error_recovery(root, staging)
    assert not (root / "sumtally/dose_err.out").exists()
    assert not (root / recovery.RECEIPT_RELATIVE_PATH).exists()


@pytest.mark.parametrize(
    ("summary_name", "schema_version"),
    [
        ("generation", None),
        ("generation", "dicomxphits_public_sumtally_generation_future"),
        ("execution", None),
        ("execution", "dicomxphits_public_sumtally_execution_future"),
    ],
)
def test_preview_rejects_missing_or_unknown_summary_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    summary_name: str,
    schema_version: str | None,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    path = root / (
        recovery.GENERATION_RELATIVE_PATH
        if summary_name == "generation"
        else recovery.EXECUTION_RELATIVE_PATH
    )
    summary = json.loads(path.read_text(encoding="utf-8"))
    if schema_version is None:
        summary.pop("schema_version")
    else:
        summary["schema_version"] = schema_version
    path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match=rf"{summary_name} summary has an unsupported schema_version",
    ):
        recovery.preview_sumtally_relative_error_recovery(root, staging)
    assert not (root / "sumtally/dose_err.out").exists()
    assert not (root / recovery.RECEIPT_RELATIVE_PATH).exists()


def test_changed_summary_invalidates_confirmed_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    generation_path = root / recovery.GENERATION_RELATIVE_PATH
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    generation["synthetic_change"] = True
    generation_path.write_text(json.dumps(generation), encoding="utf-8")

    with pytest.raises(recovery.SumtallyRelativeErrorRecoveryUnavailable, match="plan changed"):
        recovery.apply_sumtally_relative_error_recovery(
            root, staging, preview["recovery_plan_sha256"]
        )
    assert not (root / "sumtally/dose_err.out").exists()


def test_tampered_receipt_never_authorizes_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    recovery.apply_sumtally_relative_error_recovery(
        root, staging, preview["recovery_plan_sha256"]
    )
    receipt_path = root / recovery.RECEIPT_RELATIVE_PATH
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["official_pair"]["error_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match="canonical identity",
    ):
        recovery.resolved_combined_relative_error_evidence(root)


def test_recovery_receipt_enables_only_existing_gui_structure_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    assert _current_sumtally_binding(root, require_combined_error=True) is None
    preview = recovery.preview_sumtally_relative_error_recovery(root, staging)
    recovery.apply_sumtally_relative_error_recovery(
        root, staging, preview["recovery_plan_sha256"]
    )
    assert _current_sumtally_binding(root, require_combined_error=True) is not None
    execution = json.loads((root / recovery.EXECUTION_RELATIVE_PATH).read_text())
    assert execution["combined_relative_error_evidence"] is None


def test_preview_rejects_non_explicit_or_linked_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, staging = _workspace(tmp_path, monkeypatch)
    with pytest.raises(
        recovery.SumtallyRelativeErrorRecoveryUnavailable,
        match="directly below",
    ):
        recovery.preview_sumtally_relative_error_recovery(root, staging / "nested")
    link = root / ".sumtally-run-fedcba9876543210"
    try:
        link.symlink_to(staging, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    with pytest.raises(ValueError, match="symbolic link|reparse point"):
        recovery.preview_sumtally_relative_error_recovery(root, link)
