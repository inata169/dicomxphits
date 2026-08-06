from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PUBLIC_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SRC = PUBLIC_ROOT / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

import dicomxphits.gui as gui_module
from dicomxphits.gui import (
    GEOMETRY_MODE_RECTANGULAR_3DCRT,
    RTDOSE_COMPLETED,
    RTDOSE_NOT_PREPARED,
    RTDOSE_PREPARED,
    GuiConfig,
    StageExecutionGuard,
    StageResult,
    GuiValidationError,
    _browse_directories,
    _ct2phits_handoff_from_result,
    _default_values,
    _read_gui_settings,
    _save_browse_history,
    _save_gui_settings,
    apply_case_path_suggestions,
    bind_tool_profile_revalidation,
    browse_initial_directory,
    build_stage_command,
    ct2phits_handoff_values,
    gui_defaults_path,
    geometry_mode_guidance,
    preserve_tool_profile_mode_values,
    rtdose_action_enabled,
    rtdose_nav_status,
    rtdose_stage_state,
    run_stage,
    stage_by_key,
    suggest_case_paths,
    successful_nav_status,
    validation_nav_status,
    validate_prepare_handoff_selection,
    validate_stage,
    workspace_path_from_parent,
)
from dicomxphits.gui_tool_profile import (
    ROLE_PHITS2DICOM_EXECUTABLE,
    STANDARD_WINDOWS_LAYOUT_ID,
    TOOL_PROFILE_CUSTOM,
    TOOL_PROFILE_STANDARD,
    resolve_standard_tool_profile,
    resolve_tool_profile,
    validate_custom_tool_profile,
)
from dicomxphits.prepare_3dcrt_workspace import build_parser


def write_file(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_current_sumtally_binding(
    workspace: Path,
    *,
    token: str = "current",
) -> dict[str, object]:
    normalization_contract = (
        "active_treatment_segments_totalfield_segment_mu_sum"
    )
    normalization = {
        "schema_version": "synthetic_active_treatment_mu_sum_v1",
        "sumfactor": 700.0,
    }
    segment_evidence = [
        {"path": f"segment-{token}.out", "sha256": f"segment-{token}"}
    ]
    wrapper_evidence = [
        {"path": f"wrapper-{token}.inp", "sha256": f"wrapper-{token}"}
    ]
    manifest = {"token": token}
    write_file(
        workspace / "segments" / "segment_manifest.json",
        json.dumps(manifest, indent=2) + "\n",
    )
    generation = {
        "stage_status": "success",
        "manifest_sha256": gui_module.manifest_sha256(manifest),
        "sum_input_sha256": f"sum-input-{token}",
        "sumtally_input_sha256": f"sumtally-input-{token}",
        "sumtally_normalization": normalization_contract,
        "sumtally_normalization_evidence": normalization,
        "segment_output_evidence": segment_evidence,
        "wrapper_include_evidence": wrapper_evidence,
    }
    execution = {
        **generation,
        "expected_sumtally_output_sha256": f"sumtally-output-{token}",
        "expected_sumtally_output_updated_by_run": True,
    }
    analysis = workspace / "analysis"
    write_file(
        analysis / "sumtally_generation_summary.json",
        json.dumps(generation),
    )
    write_file(
        analysis / "sumtally_execution_summary.json",
        json.dumps(execution),
    )
    return {
        "manifest_sha256": generation["manifest_sha256"],
        "sum_input_sha256": generation["sum_input_sha256"],
        "sumtally_input_sha256": generation["sumtally_input_sha256"],
        "segment_output_evidence": segment_evidence,
        "wrapper_include_evidence": wrapper_evidence,
        "sumtally_normalization": normalization_contract,
        "sumtally_output_sha256": execution["expected_sumtally_output_sha256"],
        "sumtally_normalization_evidence": normalization,
    }


def write_standard_tool_layout(root: Path) -> dict[str, Path]:
    rtphits_root = write_dir(root / "utility" / "RTphits")
    return {
        "root": write_dir(root),
        "phits": write_file(root / "bin" / "phits335_win_openmp.exe"),
        "rtphits": rtphits_root,
        "batch": write_file(rtphits_root / "RTphits_win.bat"),
        "table": write_file(rtphits_root / "data" / "HumanVoxelTable.data"),
        "phits2dicom": write_file(
            rtphits_root / "bin" / "phits2dicom_win.exe"
        ),
    }


def base_config(tmp_path: Path, *, workspace: Path | None = None, allow_overwrite: bool = False) -> GuiConfig:
    phits_root = write_dir(tmp_path / "phits-root")
    ct_datfiles_root = write_dir(tmp_path / "DATfiles")
    return GuiConfig(
        rtplan_path=str(write_file(tmp_path / "input" / "plan.dcm")),
        workspace_root=str(workspace or (tmp_path / "workspace")),
        phits_root_folder=str(phits_root),
        phits_executable_path=str(write_file(phits_root / "bin" / "phits")),
        phits2dicom_executable_path=str(write_file(tmp_path / "tools" / "phits2dicom")),
        rtdose_template_dicom=str(write_file(tmp_path / "dicom" / "template.dcm")),
        ct_reference_dicom=str(write_file(tmp_path / "dicom" / "ct.dcm")),
        machine_config_path=str(write_file(tmp_path / "config" / "machine.json")),
        allow_overwrite=allow_overwrite,
        ct_datfiles_root=str(ct_datfiles_root),
        confirmed_non_patient_phantom=True,
    )


def test_missing_required_path_does_not_start_subprocess(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    config = replace(
        base_config(tmp_path),
        ct_datfiles_root=str(tmp_path / "missing-DATfiles"),
    )

    with pytest.raises(GuiValidationError, match="CT2PHITS DATfiles directory"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_pr3_cli_contract_exposes_rectangular_geometry_mode() -> None:
    parser = build_parser()
    parser_actions = {action.dest: action for action in parser._actions}

    assert "geometry_mode" in parser_actions
    assert "machine_config_path" in parser_actions
    assert "ct_datfiles_root" in parser_actions
    assert "ct_reference_dicom" in parser_actions
    assert "confirm_non_patient_phantom" in parser_actions
    assert parser_actions["maxcas"].default == 1_000_000
    assert parser_actions["maxbch"].default == 10
    assert parser_actions["omp_threads"].default == 8
    assert parser.parse_args(["--rtplan", "plan.dcm", "--workspace-root", "workspace"]).geometry_mode == "rectangular_3dcrt"
    assert tuple(parser_actions["geometry_mode"].choices) == ("rectangular_3dcrt",)


def test_gui_config_defaults_to_rectangular_public_model(tmp_path: Path) -> None:
    config = base_config(tmp_path)

    assert config.geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT


def test_standard_tool_profile_resolves_approved_phits_335_layout(
    tmp_path: Path,
) -> None:
    layout = write_standard_tool_layout(tmp_path / "phits")

    resolution = resolve_standard_tool_profile(layout["root"])

    assert resolution.ready is True
    assert resolution.layout_id == STANDARD_WINDOWS_LAYOUT_ID
    assert resolution.phits_root_folder == str(layout["root"].resolve())
    assert resolution.rtphits_root == str(layout["rtphits"].resolve())
    assert resolution.phits_executable_path == str(layout["phits"].resolve())
    assert resolution.phits2dicom_executable_path == str(
        layout["phits2dicom"].resolve()
    )


def test_standard_tool_profile_ignores_other_platform_converter_siblings(
    tmp_path: Path,
) -> None:
    layout = write_standard_tool_layout(tmp_path / "phits")
    layout["table"].unlink()
    write_file(layout["rtphits"] / "bin" / "phits2dicom_lin.exe")
    write_file(layout["rtphits"] / "bin" / "phits2dicom_mac.exe")

    resolution = resolve_standard_tool_profile(layout["root"])

    assert resolution.ready is False
    rendered = "\n".join(issue.message for issue in resolution.issues)
    assert "HumanVoxelTable.data" in rendered
    assert "Multiple phits2dicom executables" not in rendered
    assert resolution.phits2dicom_executable_path == str(
        layout["phits2dicom"].resolve()
    )
    assert resolution.ready_for_stage("run_ct2phits") is False
    assert resolution.ready_for_stage("run_segments") is True
    assert resolution.ready_for_stage("run_rtdose") is True


def test_missing_rtphits_folder_disables_ct2phits_and_rtdose(
    tmp_path: Path,
) -> None:
    root = write_dir(tmp_path / "phits")
    write_file(root / "bin" / "phits335_win_openmp.exe")

    resolution = resolve_standard_tool_profile(root)

    assert resolution.ready_for_stage("run_ct2phits") is False
    assert resolution.ready_for_stage("run_rtdose") is False
    assert any(
        issue.role == ROLE_PHITS2DICOM_EXECUTABLE
        for issue in resolution.issues
    )


def test_unselected_standard_folder_disables_all_dependent_stages() -> None:
    resolution = resolve_standard_tool_profile("")

    for stage_key in (
        "run_ct2phits",
        "prepare_workspace",
        "run_segments",
        "generate_sumtally",
        "run_sumtally",
        "run_rtdose",
    ):
        assert resolution.ready_for_stage(stage_key) is False
    assert resolution.ready_for_stage("prepare_rtdose") is True


def test_standard_profile_rejects_rtphits_symlink_escape(
    tmp_path: Path,
) -> None:
    root = write_dir(tmp_path / "selected-phits")
    write_file(root / "bin" / "phits335_win_openmp.exe")
    utility = write_dir(root / "utility")
    outside = write_standard_tool_layout(tmp_path / "outside-phits")["rtphits"]
    try:
        (utility / "RTphits").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    resolution = resolve_standard_tool_profile(root)

    assert resolution.ready is False
    assert resolution.rtphits_root == ""
    assert resolution.phits2dicom_executable_path == ""
    assert "escapes the selected installation" in "\n".join(
        issue.message for issue in resolution.issues
    )


def test_custom_tool_profile_uses_same_rtphits_markers(tmp_path: Path) -> None:
    layout = write_standard_tool_layout(tmp_path / "nonstandard")
    values = {
        "phits_root_folder": str(layout["root"]),
        "rtphits_root": str(layout["rtphits"]),
        "phits_executable_path": str(layout["phits"]),
        "phits2dicom_executable_path": str(layout["phits2dicom"]),
    }

    assert validate_custom_tool_profile(values).ready is True

    layout["batch"].unlink()
    resolution = validate_custom_tool_profile(values)

    assert resolution.ready is False
    assert "RTphits_win.bat" in "\n".join(
        issue.message for issue in resolution.issues
    )


@pytest.mark.parametrize("help_flag", ["-h", "--help"])
def test_gui_help_is_side_effect_free_and_states_public_scope(
    help_flag: str,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        gui_module,
        "_build_gui",
        lambda: pytest.fail("GUI must not start while displaying help"),
    )

    assert gui_module.main([help_flag]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "3D-CRT fixed-field" in captured.out
    assert "workflows only" in captured.out
    assert "IMRT" in captured.out
    assert "dynamic MLC delivery" in captured.out
    assert "VMAT" in captured.out


def test_gui_config_preserves_positional_allow_overwrite_compatibility(tmp_path: Path) -> None:
    values = base_config(tmp_path).__dict__

    config = GuiConfig(
        values["rtplan_path"],
        values["workspace_root"],
        values["phits_root_folder"],
        values["phits_executable_path"],
        values["phits2dicom_executable_path"],
        values["rtdose_template_dicom"],
        values["ct_reference_dicom"],
        values["machine_config_path"],
        True,
    )

    assert config.allow_overwrite is True
    assert config.geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT


def test_gui_defaults_load_local_json_without_private_fixture_paths(tmp_path: Path) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_text(
        json.dumps(
            {
                "geometry_mode": GEOMETRY_MODE_RECTANGULAR_3DCRT,
                "rtplan_path": "relative-or-user-local-plan.dcm",
                "workspace_root": "relative-or-user-local-workspace",
                "phits_root_folder": "phits-root",
                "phits_executable_path": "phits.exe",
                "phits2dicom_executable_path": "phits2dicom.exe",
                "rtdose_template_dicom": "template.dcm",
                "ct_reference_dicom": "ct-reference.dcm",
                "machine_config_path": "machine-config.json",
                "unknown_key": "ignored",
            }
        ),
        encoding="utf-8",
    )

    values = _default_values(defaults_path)

    assert values["geometry_mode"] == GEOMETRY_MODE_RECTANGULAR_3DCRT
    assert values["rtplan_path"] == ""
    assert values["machine_config_path"] == "machine-config.json"
    assert "unknown_key" not in values


def test_gui_defaults_missing_or_invalid_file_falls_back_safely(tmp_path: Path) -> None:
    assert _default_values(tmp_path / "missing.json")["geometry_mode"] == GEOMETRY_MODE_RECTANGULAR_3DCRT

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")

    assert _default_values(invalid)["geometry_mode"] == GEOMETRY_MODE_RECTANGULAR_3DCRT


def test_gui_defaults_invalid_geometry_mode_falls_back_to_rectangular(tmp_path: Path) -> None:
    defaults_path = tmp_path / "defaults.json"
    defaults_path.write_text(json.dumps({"geometry_mode": "invalid"}), encoding="utf-8")

    assert _default_values(defaults_path)["geometry_mode"] == GEOMETRY_MODE_RECTANGULAR_3DCRT


def test_gui_defaults_path_uses_local_config_or_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DICOMXPHITS_GUI_DEFAULTS_JSON", raising=False)
    assert gui_defaults_path() == PUBLIC_ROOT / "config" / "dicomxphits.gui.local.json"

    custom_path = tmp_path / "custom-local-defaults.json"
    monkeypatch.setenv("DICOMXPHITS_GUI_DEFAULTS_JSON", str(custom_path))

    assert gui_defaults_path() == custom_path


def test_public_tree_workspace_does_not_start_subprocess(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    workspace = PUBLIC_ROOT / "_gui_test_workspace"
    config = base_config(tmp_path, workspace=workspace)

    with pytest.raises(GuiValidationError, match="outside public_release"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_existing_workspace_overwrite_detection_does_not_start_subprocess(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    workspace = write_dir(tmp_path / "workspace")
    write_file(workspace / "existing.txt")
    config = base_config(tmp_path, workspace=workspace)

    with pytest.raises(GuiValidationError, match="already contains files"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_rectangular_prepare_requires_non_patient_ct_confirmation(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    config = replace(
        base_config(tmp_path, workspace=tmp_path / "workspace"),
        confirmed_non_patient_phantom=False,
    )

    with pytest.raises(GuiValidationError, match="non-patient phantom"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_existing_stage_summary_does_not_start_subprocess(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    workspace = write_dir(tmp_path / "workspace")
    summary = workspace / stage_by_key("run_segments").summary_relative_path
    write_file(summary, "{}")
    config = base_config(tmp_path, workspace=workspace)

    with pytest.raises(GuiValidationError, match="stage output already exists"):
        run_stage(config, "run_segments", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_segment_stage_uses_run_segments_adapter_and_reads_summary(tmp_path: Path) -> None:
    workspace = write_dir(tmp_path / "workspace")
    config = base_config(tmp_path, workspace=workspace)
    summary_path = workspace / stage_by_key("run_segments").summary_relative_path

    def fake_runner(cmd, **kwargs):
        assert cmd[0] == "dicomxphits-run-segments"
        assert kwargs["shell"] is False
        assert kwargs["cwd"] == workspace.resolve()
        write_file(summary_path, json.dumps({"stage_status": "success", "status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    result = run_stage(config, "run_segments", runner=fake_runner)

    assert result.return_code == 0
    assert result.summary == {"stage_status": "success", "status": "success"}
    assert "--phits-executable-path" in result.command


def test_downstream_stage_ignores_geometry_mode_and_machine_config(tmp_path: Path) -> None:
    workspace = write_dir(tmp_path / "workspace")
    config = base_config(
        tmp_path,
        workspace=workspace,
    )
    config = replace(
        config,
        geometry_mode=GEOMETRY_MODE_RECTANGULAR_3DCRT,
        machine_config_path=str(tmp_path / "missing machine config.json"),
    )
    summary_path = workspace / stage_by_key("run_segments").summary_relative_path

    def fake_runner(cmd, **kwargs):
        assert "--geometry-mode" not in cmd
        assert "--machine-config-path" not in cmd
        write_file(summary_path, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "run_segments", runner=fake_runner)

    assert result.summary == {"stage_status": "success"}


def test_prepare_rtdose_stage_passes_default_phits_out(tmp_path: Path) -> None:
    workspace = write_dir(tmp_path / "workspace")
    config = base_config(tmp_path, workspace=workspace)
    summary_path = workspace / stage_by_key("prepare_rtdose").summary_relative_path
    expected_phits_out = (workspace / "sumtally" / "phits.out").resolve()

    def fake_runner(cmd, **kwargs):
        assert cmd[0] == "dicomxphits-prepare-rtdose"
        assert cmd[cmd.index("--rtplan") + 1] == str(Path(config.rtplan_path).resolve())
        assert "--phits-out" in cmd
        assert cmd[cmd.index("--phits-out") + 1] == str(expected_phits_out)
        write_file(summary_path, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "prepare_rtdose", runner=fake_runner)

    assert result.summary == {"stage_status": "success"}


def successful_rtdose_prepare_summary(
    *,
    sumtally_manifest_binding: dict[str, object] | None = None,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "stage_status": "success",
        "rtdose_placement": {"schema_version": "synthetic-placement-v1"},
    }
    if sumtally_manifest_binding is not None:
        summary["sumtally_manifest_binding"] = sumtally_manifest_binding
    return summary


def test_successful_rtdose_prepare_is_reported_as_prepared(tmp_path: Path) -> None:
    workspace = write_dir(tmp_path / "workspace")

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED
    assert successful_nav_status("prepare_rtdose") == "Prepared"
    assert successful_nav_status("generate_sumtally") == "Generated"
    assert rtdose_action_enabled("prepare_rtdose", RTDOSE_NOT_PREPARED) is True
    assert rtdose_action_enabled("run_rtdose", RTDOSE_NOT_PREPARED) is False

    prepare_summary_path = (
        workspace / stage_by_key("prepare_rtdose").summary_relative_path
    )
    current_binding = write_current_sumtally_binding(workspace)
    write_file(
        prepare_summary_path,
        json.dumps({"stage_status": "success", "rtdose_placement": {}}),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED
    config = base_config(tmp_path, workspace=workspace)
    with pytest.raises(GuiValidationError, match="summary is stale"):
        validate_stage(config, stage_by_key("prepare_rtdose"))
    assert (
        validate_stage(
            replace(config, allow_overwrite=True),
            stage_by_key("prepare_rtdose"),
        )
        == workspace.resolve()
    )

    write_file(
        prepare_summary_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )
    assert rtdose_stage_state(workspace) == RTDOSE_PREPARED
    assert rtdose_action_enabled("prepare_rtdose", RTDOSE_PREPARED) is False
    assert rtdose_action_enabled("run_rtdose", RTDOSE_PREPARED) is True
    assert (
        rtdose_action_enabled(
            "prepare_rtdose",
            RTDOSE_PREPARED,
            allow_overwrite=True,
        )
        is True
    )
    assert validation_nav_status(
        "prepare_rtdose", rtdose_state=RTDOSE_PREPARED
    ) == "Prepared"
    assert validation_nav_status(
        "run_rtdose", rtdose_state=RTDOSE_PREPARED
    ) == "Prepared"


def test_rtdose_nav_status_resets_for_unprepared_workspace() -> None:
    assert rtdose_nav_status(RTDOSE_COMPLETED) == "Completed"
    assert rtdose_nav_status(RTDOSE_PREPARED) == "Prepared"
    assert rtdose_nav_status(RTDOSE_NOT_PREPARED) == "Not run"


def test_rtdose_state_treats_malformed_summary_as_unsuccessful(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    prepare_summary = workspace / stage_by_key("prepare_rtdose").summary_relative_path
    run_summary = workspace / stage_by_key("run_rtdose").summary_relative_path
    write_file(prepare_summary, "{truncated")

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED

    current_binding = write_current_sumtally_binding(workspace)
    write_file(
        prepare_summary,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )
    write_file(run_summary, "{truncated")

    assert rtdose_stage_state(workspace) == RTDOSE_PREPARED


def test_rtdose_state_rejects_prepare_bound_to_stale_sumtally(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    current_binding = write_current_sumtally_binding(workspace)
    stale_binding = dict(current_binding)
    stale_binding["sumtally_input_sha256"] = "sumtally-input-stale"
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(
            {
                "stage_status": "success",
                "sumtally_manifest_binding": stale_binding,
            }
        ),
    )
    write_file(
        workspace / stage_by_key("run_rtdose").summary_relative_path,
        json.dumps({"stage_status": "success"}),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED
    assert rtdose_action_enabled("prepare_rtdose", RTDOSE_NOT_PREPARED) is True
    assert rtdose_action_enabled("run_rtdose", RTDOSE_NOT_PREPARED) is False


def test_rtdose_state_rejects_changed_current_segment_manifest(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    current_binding = write_current_sumtally_binding(workspace)
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_PREPARED
    assert rtdose_action_enabled("run_rtdose", RTDOSE_PREPARED) is True

    write_file(
        workspace / "segments" / "segment_manifest.json",
        json.dumps({"token": "changed-after-prepare"}),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED
    assert rtdose_action_enabled("prepare_rtdose", RTDOSE_NOT_PREPARED) is True
    assert rtdose_action_enabled("run_rtdose", RTDOSE_NOT_PREPARED) is False


def test_rtdose_state_rejects_changed_phits_dependency_before_sumtally_run(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    current_binding = write_current_sumtally_binding(workspace)
    generation_path = workspace / "analysis" / "sumtally_generation_summary.json"
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    generation["segment_output_evidence"] = [
        {"path": "segment-new.out", "sha256": "segment-new"}
    ]
    write_file(generation_path, json.dumps(generation))
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED


def test_rtdose_state_rejects_sumtally_run_without_output_update(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    current_binding = write_current_sumtally_binding(workspace)
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["expected_sumtally_output_updated_by_run"] = False
    write_file(execution_path, json.dumps(execution))
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED


def test_rtdose_state_requires_execution_to_match_current_prepare(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    current_binding = write_current_sumtally_binding(workspace)
    prepare_path = (
        workspace / stage_by_key("prepare_rtdose").summary_relative_path
    )
    write_file(
        prepare_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )
    execution_path = (
        workspace / stage_by_key("run_rtdose").summary_relative_path
    )
    write_file(execution_path, json.dumps({"stage_status": "success"}))

    assert rtdose_stage_state(workspace) == RTDOSE_PREPARED

    write_file(
        execution_path,
        json.dumps(
            {
                "stage_status": "success",
                "rtdose_prepare_summary_sha256": gui_module.file_sha256(
                    prepare_path
                ),
                "coordinate_placement_validation": {"validated": True},
            }
        ),
    )
    assert rtdose_stage_state(workspace) == RTDOSE_COMPLETED

    write_file(
        prepare_path,
        json.dumps(
            {
                "stage_status": "success",
                "sumtally_manifest_binding": current_binding,
                "rtdose_placement": {"schema_version": "synthetic-placement-v1"},
                "new_prepare": True,
            }
        ),
    )
    assert rtdose_stage_state(workspace) == RTDOSE_PREPARED


def test_stage_status_treats_summary_read_error_as_failure(tmp_path: Path) -> None:
    result = StageResult(
        stage_key="prepare_rtdose",
        command=["dicomxphits-prepare-rtdose"],
        return_code=0,
        summary_path=tmp_path / "rtdose_conversion_prepare_summary.json",
        summary={"summary_error": "JSONDecodeError: truncated summary"},
        stdout="",
        stderr="",
    )

    assert gui_module._stage_status(result) == "invalid_summary"


def test_legacy_unbound_rtdose_summaries_do_not_report_completed(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(successful_rtdose_prepare_summary()),
    )
    write_file(
        workspace / stage_by_key("run_rtdose").summary_relative_path,
        json.dumps(
            {
                "stage_status": "success",
                "coordinate_placement_validation": {"validated": True},
            }
        ),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED
    assert rtdose_action_enabled("prepare_rtdose", RTDOSE_NOT_PREPARED) is True
    assert rtdose_action_enabled("run_rtdose", RTDOSE_NOT_PREPARED) is False


def test_completed_rtdose_requires_explicit_overwrite_to_reprepare(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    current_binding = write_current_sumtally_binding(workspace)
    prepare_path = workspace / stage_by_key("prepare_rtdose").summary_relative_path
    write_file(
        prepare_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )
    write_file(
        workspace / stage_by_key("run_rtdose").summary_relative_path,
        json.dumps(
            {
                "stage_status": "success",
                "rtdose_prepare_summary_sha256": gui_module.file_sha256(
                    prepare_path
                ),
                "coordinate_placement_validation": {"validated": True},
            }
        ),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_COMPLETED
    assert rtdose_action_enabled("prepare_rtdose", RTDOSE_COMPLETED) is False
    assert (
        rtdose_action_enabled(
            "prepare_rtdose",
            RTDOSE_COMPLETED,
            allow_overwrite=True,
        )
        is True
    )
    assert rtdose_action_enabled("run_rtdose", RTDOSE_COMPLETED) is False
    assert successful_nav_status("run_rtdose") == "Completed"


@pytest.mark.parametrize(
    "execution",
    [
        {"stage_status": "success"},
        {
            "stage_status": "success",
            "coordinate_placement_validation": {"validated": False},
        },
    ],
)
def test_rtdose_success_without_coordinate_proof_remains_prepared(
    tmp_path: Path,
    execution: dict[str, object],
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    config = base_config(tmp_path, workspace=workspace)
    current_binding = write_current_sumtally_binding(workspace)
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )
    write_file(
        workspace / stage_by_key("run_rtdose").summary_relative_path,
        json.dumps(execution),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_PREPARED
    assert rtdose_action_enabled("run_rtdose", RTDOSE_PREPARED) is True
    assert validate_stage(config, stage_by_key("run_rtdose")) == workspace.resolve()


def test_duplicate_successful_rtdose_prepare_guides_user_to_run(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    config = base_config(tmp_path, workspace=workspace)
    current_binding = write_current_sumtally_binding(workspace)
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps(
            successful_rtdose_prepare_summary(
                sumtally_manifest_binding=current_binding,
            )
        ),
    )

    with pytest.raises(
        GuiValidationError,
        match="already prepared.*Run RTDOSE",
    ):
        validate_stage(config, stage_by_key("prepare_rtdose"))


def test_failed_rtdose_prepare_does_not_unlock_run(tmp_path: Path) -> None:
    workspace = write_dir(tmp_path / "workspace")
    write_file(
        workspace / stage_by_key("prepare_rtdose").summary_relative_path,
        json.dumps({"stage_status": "failed"}),
    )

    assert rtdose_stage_state(workspace) == RTDOSE_NOT_PREPARED
    assert rtdose_action_enabled("run_rtdose", RTDOSE_NOT_PREPARED) is False


def test_prepare_stage_allows_new_workspace_and_uses_parent_cwd(tmp_path: Path) -> None:
    workspace = tmp_path / "new_workspace"
    config = base_config(tmp_path, workspace=workspace)

    def fake_runner(cmd, **kwargs):
        assert cmd[0] == "dicomxphits-prepare-3dcrt-workspace"
        assert cmd[cmd.index("--maxcas") + 1] == "1000000"
        assert cmd[cmd.index("--maxbch") + 1] == "10"
        assert cmd[cmd.index("--omp-threads") + 1] == "8"
        assert kwargs["cwd"] == tmp_path.resolve()
        workspace.mkdir()
        summary = workspace / stage_by_key("prepare_workspace").summary_relative_path
        write_file(summary, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "prepare_workspace", runner=fake_runner)

    assert result.summary == {"stage_status": "success"}


def test_prepare_stage_passes_explicit_runtime_values(tmp_path: Path) -> None:
    config = replace(
        base_config(tmp_path, workspace=tmp_path / "new-workspace"),
        maxcas="250000",
        maxbch="24",
        omp_threads="12",
    )

    command = build_stage_command(config, stage_by_key("prepare_workspace"))

    assert command[command.index("--maxcas") + 1] == "250000"
    assert command[command.index("--maxbch") + 1] == "24"
    assert command[command.index("--omp-threads") + 1] == "12"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("maxcas", ""),
        ("maxcas", "0"),
        ("maxbch", "-1"),
        ("maxbch", "1.5"),
        ("omp_threads", "eight"),
    ],
)
def test_prepare_stage_rejects_invalid_runtime_before_subprocess(
    tmp_path: Path,
    field_name: str,
    value: str,
) -> None:
    calls: list[list[str]] = []
    config = replace(base_config(tmp_path), **{field_name: value})

    with pytest.raises(GuiValidationError, match=field_name):
        run_stage(
            config,
            "prepare_workspace",
            runner=lambda cmd, **kwargs: calls.append(cmd),
        )

    assert calls == []


def test_ct2phits_stage_uses_existing_rtphits_root_as_cwd(
    tmp_path: Path,
) -> None:
    rtphits_root = write_dir(tmp_path / "rtphits")
    workspace = rtphits_root / "work" / "new-case"
    config = replace(
        base_config(tmp_path),
        source_rtplan_path=str(write_file(tmp_path / "source-plan.dcm")),
        ct_dicom_root=str(write_dir(tmp_path / "ct")),
        rtphits_root=str(rtphits_root),
        ct2phits_workspace_root=str(workspace),
    )
    summary_path = workspace / stage_by_key("run_ct2phits").summary_relative_path

    def fake_runner(cmd, **kwargs):
        assert cmd[0] == "dicomxphits-run-ct2phits"
        assert kwargs["cwd"] == rtphits_root.resolve()
        assert not workspace.parent.exists()
        workspace.mkdir(parents=True)
        write_file(summary_path, json.dumps({"status": "completed"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "run_ct2phits", runner=fake_runner)

    assert result.summary == {"status": "completed"}


def test_legacy_tool_smoke_mode_fails_before_subprocess(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    config = replace(base_config(tmp_path), geometry_mode="tool_smoke")

    with pytest.raises(GuiValidationError, match="unknown geometry_mode"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_unknown_geometry_mode_fails_before_subprocess(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    config = replace(base_config(tmp_path), geometry_mode="unexpected_mode")

    with pytest.raises(GuiValidationError, match="unknown geometry_mode"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


@pytest.mark.parametrize(
    "machine_config_value",
    [
        "missing config.json",
        "config-directory",
    ],
)
def test_rectangular_3dcrt_machine_config_validation_fails_before_subprocess(
    tmp_path: Path,
    machine_config_value: str,
) -> None:
    calls: list[list[str]] = []
    config_dir = write_dir(tmp_path / "config-directory")
    value_path = config_dir if machine_config_value == "config-directory" else tmp_path / machine_config_value
    config = base_config(tmp_path)
    config = replace(
        config,
        geometry_mode=GEOMETRY_MODE_RECTANGULAR_3DCRT,
        machine_config_path=str(value_path) if machine_config_value else "",
    )

    with pytest.raises(GuiValidationError, match="existing regular file"):
        run_stage(config, "prepare_workspace", runner=lambda cmd, **kwargs: calls.append(cmd))

    assert calls == []


def test_rectangular_3dcrt_empty_machine_config_uses_built_in_default(
    tmp_path: Path,
) -> None:
    config = replace(
        base_config(tmp_path, workspace=tmp_path / "workspace"),
        machine_config_path="",
        phits_executable_path="",
        phits2dicom_executable_path="",
    )

    command = build_stage_command(config, stage_by_key("prepare_workspace"))

    assert command[command.index("--geometry-mode") + 1] == GEOMETRY_MODE_RECTANGULAR_3DCRT
    assert "--machine-config-path" not in command
    assert "--phits-executable-path" not in command
    assert "--phits2dicom-executable-path" not in command
    assert command[command.index("--ct-datfiles-root") + 1] == str(
        Path(config.ct_datfiles_root).resolve()
    )
    assert command[command.index("--ct-reference-dicom") + 1] == str(
        Path(config.ct_reference_dicom).resolve()
    )
    assert "--confirm-non-patient-phantom" in command


def test_rectangular_3dcrt_prepare_command_passes_machine_config_as_single_token(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    machine_config = write_file(tmp_path / "config dir" / "machine config.json", "{}")
    config = replace(
        base_config(tmp_path, workspace=workspace),
        geometry_mode=GEOMETRY_MODE_RECTANGULAR_3DCRT,
        machine_config_path=str(machine_config),
    )
    summary_path = workspace / stage_by_key("prepare_workspace").summary_relative_path
    calls: list[list[str]] = []

    def fake_runner(cmd, **kwargs):
        calls.append(cmd)
        workspace.mkdir()
        write_file(summary_path, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "prepare_workspace", runner=fake_runner)

    assert result.summary == {"stage_status": "success"}
    command = calls[0]
    assert command[command.index("--geometry-mode") + 1] == GEOMETRY_MODE_RECTANGULAR_3DCRT
    assert command[command.index("--machine-config-path") + 1] == str(machine_config.resolve())
    assert str(machine_config.resolve()) in command


def test_geometry_mode_guidance_labels_validation_limits() -> None:
    rectangular = geometry_mode_guidance(GEOMETRY_MODE_RECTANGULAR_3DCRT)

    assert "no dose validation" in rectangular
    assert "clinical validity" in rectangular


@pytest.mark.parametrize(
    ("stage_key", "missing_fields", "expected_command", "forbidden_flags"),
    [
        (
            "prepare_workspace",
            ("phits_executable_path", "phits2dicom_executable_path"),
            "dicomxphits-prepare-3dcrt-workspace",
            ("--phits-executable-path", "--phits2dicom-executable-path"),
        ),
        (
            "run_segments",
            ("phits_root_folder", "phits2dicom_executable_path", "machine_config_path"),
            "dicomxphits-run-segments",
            ("--phits-root-folder", "--phits2dicom-executable-path"),
        ),
        (
            "generate_sumtally",
            ("phits_executable_path", "phits2dicom_executable_path", "machine_config_path"),
            "dicomxphits-generate-sumtally",
            ("--phits-executable-path", "--phits2dicom-executable-path"),
        ),
        (
            "run_sumtally",
            ("phits_root_folder", "phits2dicom_executable_path", "machine_config_path"),
            "dicomxphits-run-sumtally",
            ("--phits-root-folder", "--phits2dicom-executable-path"),
        ),
        (
            "prepare_rtdose",
            ("phits_root_folder", "phits_executable_path", "phits2dicom_executable_path", "machine_config_path"),
            "dicomxphits-prepare-rtdose",
            ("--phits-root-folder", "--phits-executable-path", "--phits2dicom-executable-path"),
        ),
        (
            "run_rtdose",
            ("phits_root_folder", "phits_executable_path", "rtdose_template_dicom", "ct_reference_dicom", "machine_config_path"),
            "dicomxphits-run-rtdose",
            ("--phits-root-folder", "--phits-executable-path", "--template-dicom", "--ct-reference-dicom"),
        ),
    ],
)
def test_stage_specific_validation_ignores_unused_paths(
    tmp_path: Path,
    stage_key: str,
    missing_fields: tuple[str, ...],
    expected_command: str,
    forbidden_flags: tuple[str, ...],
) -> None:
    workspace = write_dir(tmp_path / "workspace")
    config = base_config(tmp_path, workspace=workspace)
    missing_values = {field: str(tmp_path / f"missing-{field}") for field in missing_fields}
    config = replace(config, **missing_values)
    summary_path = workspace / stage_by_key(stage_key).summary_relative_path

    def fake_runner(cmd, **kwargs):
        assert cmd[0] == expected_command
        for flag in forbidden_flags:
            assert flag not in cmd
        write_file(summary_path, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, stage_key, runner=fake_runner)

    assert result.summary == {"stage_status": "success"}


def test_launcher_does_not_install_dependencies() -> None:
    launcher = PUBLIC_ROOT / "launchers" / "run_gui_venv.ps1"
    text = launcher.read_text(encoding="utf-8-sig").lower()

    assert "pip install" not in text
    assert "install-package" not in text
    assert "-m dicomxphits.gui" in text
    assert "$env:path" in text
    assert ".venv\\scripts" in text


def test_cmd_launcher_uses_project_venv_without_powershell() -> None:
    launcher = PUBLIC_ROOT / "launchers" / "run_gui_venv.cmd"
    text = launcher.read_text(encoding="utf-8-sig").lower()

    assert "pip install" not in text
    assert "install-package" not in text
    assert "powershell" not in text
    assert "executionpolicy" not in text
    assert "-m dicomxphits.gui" in text
    assert 'set "path=' in text
    assert ".venv\\scripts" in text


def test_ct2phits_is_the_first_guided_gui_stage(tmp_path: Path) -> None:
    rtphits_root = write_dir(tmp_path / "rtphits")
    config = replace(
        base_config(tmp_path),
        source_rtplan_path=str(write_file(tmp_path / "input" / "source-plan.dcm")),
        ct_dicom_root=str(write_dir(tmp_path / "input" / "ct")),
        rtphits_root=str(rtphits_root),
        ct2phits_workspace_root=str(rtphits_root / "work" / "new-case"),
        ct_series_instance_uid="1.2.3.4",
        ct2phits_timeout_seconds=125.0,
    )
    spec = stage_by_key("run_ct2phits")

    workspace = validate_stage(config, spec)
    command = build_stage_command(config, spec)

    assert spec.workspace_field == "ct2phits_workspace_root"
    assert workspace == (rtphits_root / "work" / "new-case").resolve()
    assert command[0] == "dicomxphits-run-ct2phits"
    assert command[command.index("--ct-dicom-root") + 1] == str(
        Path(config.ct_dicom_root).resolve()
    )
    assert command[command.index("--rtplan") + 1] == str(
        Path(config.source_rtplan_path).resolve()
    )
    assert command[command.index("--rtphits-root") + 1] == str(
        rtphits_root.resolve()
    )
    assert command[command.index("--ct-series-instance-uid") + 1] == "1.2.3.4"
    assert command[command.index("--timeout-seconds") + 1] == "125"
    assert "--confirm-non-patient-phantom" in command


def test_ct2phits_gui_stage_keeps_explicit_confirmation_and_new_workspace_gate(
    tmp_path: Path,
) -> None:
    rtphits_root = write_dir(tmp_path / "rtphits")
    workspace = write_dir(rtphits_root / "work" / "existing-case")
    config = replace(
        base_config(tmp_path),
        source_rtplan_path=str(write_file(tmp_path / "source-plan.dcm")),
        ct_dicom_root=str(write_dir(tmp_path / "ct")),
        rtphits_root=str(rtphits_root),
        ct2phits_workspace_root=str(workspace),
        confirmed_non_patient_phantom=False,
        allow_overwrite=True,
    )
    spec = stage_by_key("run_ct2phits")

    with pytest.raises(GuiValidationError, match="non-patient phantom"):
        validate_stage(config, spec)

    with pytest.raises(GuiValidationError, match="must be new"):
        validate_stage(
            replace(config, confirmed_non_patient_phantom=True),
            spec,
        )


def test_rtplan_path_suggestions_are_visible_derivations_only(tmp_path: Path) -> None:
    plan = tmp_path / "selected" / "RT PLAN 01.dcm"
    rtphits_root = tmp_path / "rtphits"
    public_parent = tmp_path / "deliverables"

    suggestions = suggest_case_paths(
        plan,
        rtphits_root=rtphits_root,
        workspace_parent=public_parent,
    )

    assert suggestions == {
        "ct_dicom_root": str(plan.parent),
        "ct2phits_workspace_root": str(
            rtphits_root / "work" / "RT-PLAN-01-ct2phits"
        ),
        "workspace_root": str(public_parent / "RT-PLAN-01-3dcrt"),
    }
    assert workspace_path_from_parent(
        public_parent,
        plan,
        "workspace_root",
    ) == public_parent / "RT-PLAN-01-3dcrt"


def test_standard_profile_replaces_stale_derived_ct2phits_workspace(
    tmp_path: Path,
) -> None:
    new_plan = tmp_path / "new case" / "RT PLAN 02.dcm"
    rtphits_root = tmp_path / "phits" / "utility" / "RTphits"
    suggestions = suggest_case_paths(new_plan, rtphits_root=rtphits_root)
    current = {
        "ct_dicom_root": "explicit-ct-folder",
        "ct2phits_workspace_root": "stale-workspace",
    }

    standard = apply_case_path_suggestions(
        current,
        suggestions,
        tool_profile_mode=TOOL_PROFILE_STANDARD,
    )
    custom = apply_case_path_suggestions(
        current,
        suggestions,
        tool_profile_mode=TOOL_PROFILE_CUSTOM,
    )

    assert standard["ct_dicom_root"] == "explicit-ct-folder"
    assert standard["ct2phits_workspace_root"] == str(
        rtphits_root / "work" / "RT-PLAN-02-ct2phits"
    )
    assert custom["ct2phits_workspace_root"] == "stale-workspace"


def test_completed_ct2phits_handoff_uses_frozen_documented_paths(
    tmp_path: Path,
) -> None:
    workspace = write_dir(tmp_path / "ct2phits-workspace")
    write_file(workspace / "RTPLAN.dcm")
    write_file(workspace / "CT" / "CT000001.dcm")
    write_dir(workspace / "DATfiles")

    handoff = ct2phits_handoff_values(workspace, {"status": "completed"})

    assert handoff == {
        "rtplan_path": str((workspace / "RTPLAN.dcm").resolve()),
        "ct_reference_dicom": str(
            (workspace / "CT" / "CT000001.dcm").resolve()
        ),
        "ct_datfiles_root": str((workspace / "DATfiles").resolve()),
    }

    with pytest.raises(GuiValidationError, match="does not report completion"):
        ct2phits_handoff_values(workspace, {"status": "failed"})


def test_completed_handoff_is_bound_to_result_summary_workspace(
    tmp_path: Path,
) -> None:
    completed_workspace = write_dir(tmp_path / "completed-workspace")
    write_file(completed_workspace / "RTPLAN.dcm")
    write_file(completed_workspace / "CT" / "CT000001.dcm")
    write_dir(completed_workspace / "DATfiles")
    result = StageResult(
        stage_key="run_ct2phits",
        command=["dicomxphits-run-ct2phits"],
        return_code=0,
        summary_path=completed_workspace / "ct2phits_execution_summary.json",
        summary={"status": "completed"},
        stdout="",
        stderr="",
    )

    handoff = _ct2phits_handoff_from_result(result)

    assert handoff == {
        "rtplan_path": str((completed_workspace / "RTPLAN.dcm").resolve()),
        "ct_reference_dicom": str(
            (completed_workspace / "CT" / "CT000001.dcm").resolve()
        ),
        "ct_datfiles_root": str((completed_workspace / "DATfiles").resolve()),
    }


def test_saved_legacy_handoff_paths_do_not_authorize_prepare(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_text(
        json.dumps(
            {
                "rtplan_path": "stale-RTPLAN.dcm",
                "ct_reference_dicom": "stale-CT000001.dcm",
                "ct_datfiles_root": "stale-DATfiles",
            }
        ),
        encoding="utf-8",
    )
    defaults = _default_values(defaults_path)

    assert defaults["rtplan_path"] == ""
    assert defaults["ct_reference_dicom"] == ""
    assert defaults["ct_datfiles_root"] == ""
    with pytest.raises(GuiValidationError, match="Run CT2PHITS successfully"):
        validate_prepare_handoff_selection(
            manual_handoff_selected=False,
            verified_handoff_available=False,
        )


@pytest.mark.parametrize(
    ("manual_handoff_selected", "verified_handoff_available"),
    [(True, False), (False, True)],
)
def test_prepare_accepts_explicit_manual_or_verified_handoff(
    manual_handoff_selected: bool,
    verified_handoff_available: bool,
) -> None:
    validate_prepare_handoff_selection(
        manual_handoff_selected=manual_handoff_selected,
        verified_handoff_available=verified_handoff_available,
    )


def test_gui_settings_persist_stable_paths_and_independent_browse_history(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    plan_dir = write_dir(tmp_path / "plan-browser")
    tool_dir = write_dir(tmp_path / "tool-browser")
    values = {
        "geometry_mode": GEOMETRY_MODE_RECTANGULAR_3DCRT,
        "tool_profile_mode": TOOL_PROFILE_CUSTOM,
        "phits_installation_folder": "remembered-installation",
        "rtphits_root": "remembered-rtphits",
        "phits_root_folder": "remembered-phits",
        "phits_executable_path": "remembered-phits.exe",
        "phits2dicom_executable_path": "remembered-phits2dicom.exe",
        "rtdose_template_dicom": "remembered-template.dcm",
        "machine_config_path": "remembered-machine.json",
        "maxcas": "250000",
        "maxbch": "24",
        "omp_threads": "12",
        "source_rtplan_path": "must-not-be-persisted.dcm",
        "ct2phits_workspace_root": "must-not-be-persisted-workspace",
        "confirmed_non_patient_phantom": "true",
        "allow_overwrite": "true",
    }
    history = {
        "source_rtplan_path": str(plan_dir),
        "phits_executable_path": str(tool_dir),
    }

    _save_gui_settings(values, history, defaults_path)
    saved = json.loads(defaults_path.read_text(encoding="utf-8"))

    assert saved["settings_version"] == 5
    assert saved["tool_profile_mode"] == TOOL_PROFILE_CUSTOM
    assert saved["phits_installation_folder"] == "remembered-installation"
    assert saved["rtphits_root"] == "remembered-rtphits"
    assert saved["maxcas"] == "250000"
    assert saved["maxbch"] == "24"
    assert saved["omp_threads"] == "12"
    assert "source_rtplan_path" not in saved
    assert "ct2phits_workspace_root" not in saved
    assert "confirmed_non_patient_phantom" not in saved
    assert "allow_overwrite" not in saved
    assert _browse_directories(defaults_path) == history
    assert browse_initial_directory(
        "source_rtplan_path",
        {},
        _browse_directories(defaults_path),
    ) == plan_dir
    assert browse_initial_directory(
        "phits_executable_path",
        {},
        _browse_directories(defaults_path),
    ) == tool_dir
    assert browse_initial_directory(
        "ct2phits_workspace_root",
        {"ct2phits_workspace_root": str(tmp_path / "missing" / "new-case")},
        {},
    ) == tmp_path
    assert _default_values(defaults_path)["phits_root_folder"] == "remembered-phits"


def test_gui_settings_invalid_runtime_keeps_last_valid_values(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    _save_gui_settings(
        {"maxcas": "250000", "maxbch": "24", "omp_threads": "12"},
        {},
        defaults_path,
    )

    _save_gui_settings(
        {"maxcas": "0", "maxbch": "1.5", "omp_threads": "bad"},
        {},
        defaults_path,
    )

    restored = _default_values(defaults_path)
    assert restored["maxcas"] == "250000"
    assert restored["maxbch"] == "24"
    assert restored["omp_threads"] == "12"


def test_gui_settings_invalid_or_missing_runtime_uses_defaults(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_text(
        json.dumps({"maxcas": "0", "maxbch": "bad"}),
        encoding="utf-8",
    )

    restored = _default_values(defaults_path)

    assert restored["maxcas"] == "1000000"
    assert restored["maxbch"] == "10"
    assert restored["omp_threads"] == "8"


def test_browse_history_saves_without_persisting_unvalidated_case_values(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    _save_gui_settings(
        {
            "tool_profile_mode": TOOL_PROFILE_CUSTOM,
            "phits_root_folder": "validated-phits-root",
        },
        {},
        defaults_path,
    )

    _save_browse_history(
        {"source_rtplan_path": str(tmp_path / "case-browser")},
        defaults_path,
    )
    saved = json.loads(defaults_path.read_text(encoding="utf-8"))

    assert saved["phits_root_folder"] == "validated-phits-root"
    assert saved["browse_directories"]["source_rtplan_path"] == str(
        tmp_path / "case-browser"
    )
    assert "source_rtplan_path" not in saved


def test_gui_settings_migrate_matching_legacy_layout_to_standard_profile(
    tmp_path: Path,
) -> None:
    layout = write_standard_tool_layout(tmp_path / "phits")
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_text(
        json.dumps(
            {
                "phits_root_folder": str(layout["root"]),
                "rtphits_root": str(layout["rtphits"]),
                "phits_executable_path": str(layout["phits"]),
                "phits2dicom_executable_path": str(layout["phits2dicom"]),
            }
        ),
        encoding="utf-8",
    )

    values = _default_values(defaults_path)

    assert values["tool_profile_mode"] == TOOL_PROFILE_STANDARD
    assert values["phits_installation_folder"] == str(layout["root"])


def test_gui_settings_preserve_unmatched_legacy_layout_as_custom(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_text(
        json.dumps(
            {
                "phits_root_folder": "legacy-phits",
                "rtphits_root": "legacy-rtphits",
                "phits_executable_path": "legacy-phits.exe",
                "phits2dicom_executable_path": "legacy-phits2dicom.exe",
            }
        ),
        encoding="utf-8",
    )

    values = _default_values(defaults_path)

    assert values["tool_profile_mode"] == TOOL_PROFILE_CUSTOM
    assert values["phits_root_folder"] == "legacy-phits"
    assert values["custom_phits_root_folder"] == "legacy-phits"


def test_profile_mode_switch_preserves_explicit_custom_paths() -> None:
    custom_values = {
        "tool_profile_mode": TOOL_PROFILE_CUSTOM,
        "rtphits_root": "custom-rtphits",
        "phits_root_folder": "custom-phits",
        "phits_executable_path": "custom-phits.exe",
        "phits2dicom_executable_path": "custom-phits2dicom.exe",
        "custom_rtphits_root": "",
        "custom_phits_root_folder": "",
        "custom_phits_executable_path": "",
        "custom_phits2dicom_executable_path": "",
        "ct2phits_workspace_root": "custom-workspace",
        "custom_ct2phits_workspace_root": "",
    }

    standard_values = preserve_tool_profile_mode_values(
        custom_values,
        previous_mode=TOOL_PROFILE_CUSTOM,
        selected_mode=TOOL_PROFILE_STANDARD,
    )
    standard_values.update(
        {
            "rtphits_root": "standard-rtphits",
            "phits_root_folder": "standard-phits",
            "phits_executable_path": "standard-phits.exe",
            "phits2dicom_executable_path": "standard-phits2dicom.exe",
            "ct2phits_workspace_root": "standard-derived-workspace",
        }
    )
    restored = preserve_tool_profile_mode_values(
        standard_values,
        previous_mode=TOOL_PROFILE_STANDARD,
        selected_mode=TOOL_PROFILE_CUSTOM,
    )

    assert restored["rtphits_root"] == "custom-rtphits"
    assert restored["phits_root_folder"] == "custom-phits"
    assert restored["phits_executable_path"] == "custom-phits.exe"
    assert restored["phits2dicom_executable_path"] == "custom-phits2dicom.exe"
    assert restored["ct2phits_workspace_root"] == "custom-workspace"


def test_filesystem_invalid_legacy_paths_fall_back_without_crashing(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_text(
        json.dumps({"phits_root_folder": "invalid\u0000path"}),
        encoding="utf-8",
    )

    values = _default_values(defaults_path)
    resolution = resolve_tool_profile(values)

    assert values["tool_profile_mode"] == TOOL_PROFILE_CUSTOM
    assert resolution.ready is False
    assert resolution.ready_for_stage("prepare_workspace") is False


def test_standard_settings_round_trip_keeps_custom_profile_state(
    tmp_path: Path,
) -> None:
    layout = write_standard_tool_layout(tmp_path / "standard-phits")
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    custom_paths = {
        "custom_rtphits_root": "custom-rtphits",
        "custom_phits_root_folder": "custom-phits",
        "custom_phits_executable_path": "custom-phits.exe",
        "custom_phits2dicom_executable_path": "custom-phits2dicom.exe",
    }
    _save_gui_settings(
        {
            "tool_profile_mode": TOOL_PROFILE_STANDARD,
            "phits_installation_folder": str(layout["root"]),
            **custom_paths,
        },
        {},
        defaults_path,
    )

    restored = _default_values(defaults_path)

    assert restored["tool_profile_mode"] == TOOL_PROFILE_STANDARD
    assert restored["phits_root_folder"] == str(layout["root"].resolve())
    for name, value in custom_paths.items():
        assert restored[name] == value


def test_all_editable_tool_paths_bind_immediate_revalidation() -> None:
    class FakeVariable:
        def __init__(self) -> None:
            self.callbacks: list[tuple[str, object]] = []

        def trace_add(self, mode: str, callback) -> None:
            self.callbacks.append((mode, callback))

    names = (
        "phits_installation_folder",
        "rtphits_root",
        "phits_root_folder",
        "phits_executable_path",
        "phits2dicom_executable_path",
    )
    variables = {name: FakeVariable() for name in names}

    callback = lambda *_args: None
    bind_tool_profile_revalidation(variables, callback)

    assert all(
        variable.callbacks == [("write", callback)]
        for variable in variables.values()
    )


def test_gui_settings_invalid_encoding_falls_back_safely(tmp_path: Path) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    defaults_path.write_bytes(b"\x80\x81\x82")

    assert _read_gui_settings(defaults_path) == {}
    assert _default_values(defaults_path) == gui_module._base_default_values()


def test_gui_settings_failed_replace_removes_ignored_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    defaults_path = tmp_path / "config" / "dicomxphits.gui.local.json"
    temporary_path = defaults_path.with_name(
        defaults_path.stem + ".tmp.local.json"
    )

    def fail_replace(_source: Path, _target: Path) -> Path:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        _save_gui_settings({}, {}, defaults_path)

    assert temporary_path.name.endswith(".local.json")
    assert not temporary_path.exists()


def test_gui_stage_execution_guard_prevents_overlapping_stages() -> None:
    guard = StageExecutionGuard()

    guard.begin("run_ct2phits")

    with pytest.raises(GuiValidationError, match="already running"):
        guard.begin("prepare_workspace")

    assert guard.active_stage == "run_ct2phits"
    guard.finish()
    guard.begin("prepare_workspace")
    assert guard.active_stage == "prepare_workspace"
