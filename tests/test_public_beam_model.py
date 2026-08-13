from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.prepare_3dcrt_workspace import export_segment_manifest
from dicomxphits.public_beam_model import validate_public_beam_model
from dicomxphits.public_spectrum import (
    PUBLIC_BEAM_MODEL_DISPLAY_NAME,
    PUBLIC_BEAM_MODEL_ENERGY_GUI_LINE,
    PUBLIC_BEAM_MODEL_GUI_LINE,
    PUBLIC_BEAM_MODEL_NOMINAL_ENERGY_MV,
)


_MISSING = object()


def energy_control_point(index: int, energy: object = _MISSING) -> SimpleNamespace:
    point = SimpleNamespace(ControlPointIndex=index)
    if energy is not _MISSING:
        point.NominalBeamEnergy = energy
    return point


def energy_beam(
    number: int,
    *energies: object,
    radiation_type: str = "PHOTON",
    name: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        BeamNumber=number,
        BeamName=name or f"Synthetic beam {number}",
        RadiationType=radiation_type,
        ControlPointSequence=[
            energy_control_point(index, energy)
            for index, energy in enumerate(energies)
        ],
    )


def energy_plan(*beams: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(BeamSequence=list(beams))


def limiting_position(device_type: str, positions: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        RTBeamLimitingDeviceType=device_type,
        LeafJawPositions=positions,
    )


def workspace_control_point(index: int, cmw: float) -> SimpleNamespace:
    point = SimpleNamespace(
        ControlPointIndex=index,
        GantryAngle=0.0,
        BeamLimitingDeviceAngle=0.0,
        PatientSupportAngle=0.0,
        GantryRotationDirection="NONE",
        BeamLimitingDeviceRotationDirection="NONE",
        CumulativeMetersetWeight=cmw,
        BeamLimitingDevicePositionSequence=[
            limiting_position("ASYMX", ["-40.0", "40.0"]),
            limiting_position("ASYMY", ["-50.0", "50.0"]),
            limiting_position("MLCX", ["-20.0", "-15.0", "20.0", "15.0"]),
        ],
    )
    if index == 0:
        point.NominalBeamEnergy = 6.0
    return point


def workspace_beam(number: int = 1, *, energy: float = 6.0) -> SimpleNamespace:
    first = workspace_control_point(0, 0.0)
    first.NominalBeamEnergy = energy
    return SimpleNamespace(
        BeamNumber=number,
        BeamName=f"Workspace beam {number}",
        BeamType="STATIC",
        RadiationType="PHOTON",
        TreatmentDeliveryType="TREATMENT",
        FinalCumulativeMetersetWeight=1.0,
        BeamLimitingDeviceSequence=[
            SimpleNamespace(
                RTBeamLimitingDeviceType="ASYMX",
                NumberOfLeafJawPairs=1,
            ),
            SimpleNamespace(
                RTBeamLimitingDeviceType="ASYMY",
                NumberOfLeafJawPairs=1,
            ),
            SimpleNamespace(
                RTBeamLimitingDeviceType="MLCX",
                NumberOfLeafJawPairs=2,
                LeafPositionBoundaries=["-10.0", "0.0", "10.0"],
            ),
        ],
        ControlPointSequence=[first, workspace_control_point(1, 1.0)],
    )


def workspace_plan(*beams: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        SOPInstanceUID="1.2.826.0.1.3680043.10.54321.600",
        RTPlanLabel="SYNTHETIC_6MV",
        BeamSequence=list(beams),
        FractionGroupSequence=[
            SimpleNamespace(
                ReferencedBeamSequence=[
                    SimpleNamespace(
                        ReferencedBeamNumber=beam.BeamNumber,
                        BeamMeterset=100.0,
                    )
                    for beam in beams
                ]
            )
        ],
    )


def test_fixed_public_model_identity_is_nominal_6mv_not_monoenergetic() -> None:
    assert PUBLIC_BEAM_MODEL_NOMINAL_ENERGY_MV == 6.0
    assert PUBLIC_BEAM_MODEL_DISPLAY_NAME == (
        "Elekta Precise 6 MV public research model"
    )
    assert PUBLIC_BEAM_MODEL_GUI_LINE == (
        "Beam model: Elekta Precise 6 MV public research model"
    )
    assert PUBLIC_BEAM_MODEL_ENERGY_GUI_LINE == "Nominal energy: 6 MV (fixed)"


def test_one_6mv_beam_succeeds() -> None:
    evidence = validate_public_beam_model(
        energy_plan(energy_beam(1, 6.0, 6.0)),
        included_beam_numbers=[1],
    )

    assert evidence["validation_status"] == "passed"
    assert evidence["nominal_energy_mv"] == 6.0
    assert evidence["included_treatment_beams"][0]["nominal_energy_mv"] == 6.0


def test_multiple_6mv_beams_succeed() -> None:
    evidence = validate_public_beam_model(
        energy_plan(
            energy_beam(1, 6.0, _MISSING),
            energy_beam(2, 6.0, 6.0),
        ),
        included_beam_numbers=[1, 2],
    )

    assert [
        item["beam_number"] for item in evidence["included_treatment_beams"]
    ] == [1, 2]


def test_later_control_point_omission_inherits_6mv() -> None:
    evidence = validate_public_beam_model(
        energy_plan(energy_beam(1, 6.0, _MISSING, _MISSING)),
        included_beam_numbers=[1],
    )

    assert evidence["included_treatment_beams"][0][
        "control_point_inheritance_used"
    ] is True


@pytest.mark.parametrize("energy", [10.0, "bad", math.nan, math.inf, 0.0, -1.0])
def test_unsupported_or_invalid_energy_fails_closed(energy: object) -> None:
    with pytest.raises(ValueError, match="no PHITS input was generated"):
        validate_public_beam_model(
            energy_plan(energy_beam(1, energy)),
            included_beam_numbers=[1],
        )


def test_mixed_beam_energies_fail_closed() -> None:
    with pytest.raises(ValueError, match=r"BeamNumber 2.*10 MV"):
        validate_public_beam_model(
            energy_plan(energy_beam(1, 6.0), energy_beam(2, 10.0)),
            included_beam_numbers=[1, 2],
        )


def test_energy_change_within_beam_fails_closed() -> None:
    with pytest.raises(ValueError, match=r"changes from 6 MV to 10 MV"):
        validate_public_beam_model(
            energy_plan(energy_beam(1, 6.0, 10.0)),
            included_beam_numbers=[1],
        )


def test_missing_first_control_point_energy_fails_closed() -> None:
    with pytest.raises(ValueError, match=r"control point 0 is missing"):
        validate_public_beam_model(
            energy_plan(energy_beam(1, _MISSING, 6.0)),
            included_beam_numbers=[1],
        )


def test_non_photon_beam_fails_closed() -> None:
    with pytest.raises(ValueError, match=r"RadiationType 'ELECTRON'.*PHOTON"):
        validate_public_beam_model(
            energy_plan(energy_beam(1, 6.0, radiation_type="ELECTRON")),
            included_beam_numbers=[1],
        )


def test_error_contains_beam_identity_fixed_model_and_no_output_statement() -> None:
    with pytest.raises(ValueError) as caught:
        validate_public_beam_model(
            energy_plan(energy_beam(7, 10.0, name="Field A")),
            included_beam_numbers=[7],
        )

    message = str(caught.value)
    assert "BeamNumber 7" in message
    assert 'BeamName "Field A"' in message
    assert PUBLIC_BEAM_MODEL_DISPLAY_NAME in message
    assert "no PHITS input was generated" in message


def test_export_records_additive_manifest_evidence(monkeypatch, tmp_path: Path) -> None:
    plan = workspace_plan(workspace_beam())
    monkeypatch.setattr(
        "dicomxphits.prepare_3dcrt_workspace.load_rtplan",
        lambda _path: plan,
    )
    workspace = tmp_path / "workspace"

    manifest, manifest_path = export_segment_manifest(
        rtplan_path=tmp_path / "synthetic-plan.dcm",
        case_root=workspace,
        case_id="synthetic-6mv",
        workflow_mode="full_plan",
        expected_output_name="deposit-target-3D.out",
    )

    evidence = manifest["public_beam_model"]
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "segment_manifest_v2"
    assert evidence["nominal_energy_mv"] == 6.0
    assert evidence["included_treatment_beams"][0]["beam_number"] == 1
    assert persisted["public_beam_model"] == evidence


def test_export_rejects_10mv_before_creating_workspace(monkeypatch, tmp_path: Path) -> None:
    plan = workspace_plan(workspace_beam(energy=10.0))
    monkeypatch.setattr(
        "dicomxphits.prepare_3dcrt_workspace.load_rtplan",
        lambda _path: plan,
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match=r"10 MV.*no PHITS input was generated"):
        export_segment_manifest(
            rtplan_path=tmp_path / "synthetic-plan.dcm",
            case_root=workspace,
            case_id="synthetic-10mv",
            workflow_mode="full_plan",
            expected_output_name="deposit-target-3D.out",
        )

    assert not workspace.exists()
