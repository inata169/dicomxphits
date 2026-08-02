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
    GuiConfig,
    StageExecutionGuard,
    StageResult,
    GuiValidationError,
    _browse_directories,
    _ct2phits_handoff_from_result,
    _default_values,
    _save_gui_settings,
    browse_initial_directory,
    build_stage_command,
    ct2phits_handoff_values,
    gui_defaults_path,
    geometry_mode_guidance,
    run_stage,
    stage_by_key,
    suggest_case_paths,
    validate_stage,
    workspace_path_from_parent,
)
from dicomxphits.prepare_3dcrt_workspace import build_parser


def write_file(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    assert parser.parse_args(["--rtplan", "plan.dcm", "--workspace-root", "workspace"]).geometry_mode == "rectangular_3dcrt"
    assert tuple(parser_actions["geometry_mode"].choices) == ("rectangular_3dcrt",)


def test_gui_config_defaults_to_rectangular_public_model(tmp_path: Path) -> None:
    config = base_config(tmp_path)

    assert config.geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT


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
    assert values["rtplan_path"] == "relative-or-user-local-plan.dcm"
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
        assert "--phits-out" in cmd
        assert cmd[cmd.index("--phits-out") + 1] == str(expected_phits_out)
        write_file(summary_path, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "prepare_rtdose", runner=fake_runner)

    assert result.summary == {"stage_status": "success"}


def test_prepare_stage_allows_new_workspace_and_uses_parent_cwd(tmp_path: Path) -> None:
    workspace = tmp_path / "new_workspace"
    config = base_config(tmp_path, workspace=workspace)

    def fake_runner(cmd, **kwargs):
        assert cmd[0] == "dicomxphits-prepare-3dcrt-workspace"
        assert kwargs["cwd"] == tmp_path.resolve()
        workspace.mkdir()
        summary = workspace / stage_by_key("prepare_workspace").summary_relative_path
        write_file(summary, json.dumps({"stage_status": "success"}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    result = run_stage(config, "prepare_workspace", runner=fake_runner)

    assert result.summary == {"stage_status": "success"}


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


def test_gui_settings_persist_stable_paths_and_independent_browse_history(
    tmp_path: Path,
) -> None:
    defaults_path = tmp_path / "dicomxphits.gui.local.json"
    plan_dir = write_dir(tmp_path / "plan-browser")
    tool_dir = write_dir(tmp_path / "tool-browser")
    values = {
        "geometry_mode": GEOMETRY_MODE_RECTANGULAR_3DCRT,
        "rtphits_root": "remembered-rtphits",
        "phits_root_folder": "remembered-phits",
        "phits_executable_path": "remembered-phits.exe",
        "phits2dicom_executable_path": "remembered-phits2dicom.exe",
        "rtdose_template_dicom": "remembered-template.dcm",
        "machine_config_path": "remembered-machine.json",
        "source_rtplan_path": "must-not-be-persisted.dcm",
        "confirmed_non_patient_phantom": "true",
        "allow_overwrite": "true",
    }
    history = {
        "source_rtplan_path": str(plan_dir),
        "phits_executable_path": str(tool_dir),
    }

    _save_gui_settings(values, history, defaults_path)
    saved = json.loads(defaults_path.read_text(encoding="utf-8"))

    assert saved["settings_version"] == 2
    assert saved["rtphits_root"] == "remembered-rtphits"
    assert "source_rtplan_path" not in saved
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


def test_gui_stage_execution_guard_prevents_overlapping_stages() -> None:
    guard = StageExecutionGuard()

    guard.begin("run_ct2phits")

    with pytest.raises(GuiValidationError, match="already running"):
        guard.begin("prepare_workspace")

    assert guard.active_stage == "run_ct2phits"
    guard.finish()
    guard.begin("prepare_workspace")
    assert guard.active_stage == "prepare_workspace"
