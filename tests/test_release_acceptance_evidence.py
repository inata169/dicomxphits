from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from dicomxphits.rtplan_delivery import classify_delivery_type


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "release_acceptance_evidence.json"
TOLERANCES = {
    "cmw_tolerance": 1.0e-6,
    "angle_tolerance_deg": 0.01,
    "jaw_tolerance_mm": 0.01,
    "leaf_tolerance_mm": 0.01,
}


def load_evidence() -> dict:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8-sig"))


def fixed_state(*, cmw: float) -> dict:
    return {
        "gantry_angle_deg": 0.0,
        "collimator_angle_deg": 0.0,
        "couch_angle_deg": 0.0,
        "gantry_rotation_direction": "NONE",
        "cmw": cmw,
        "jaw_positions_mm": {
            "ASYMX": [-50.0, 50.0],
            "ASYMY": [-50.0, 50.0],
        },
        "leaf_pair_count": 2,
        "leaf_positions_mm": {
            "bank_1": [-5.0, -5.0],
            "bank_2": [5.0, 5.0],
        },
    }


def test_water_voxel_and_gpr_evidence_records_honest_reuse_boundaries() -> None:
    evidence = load_evidence()

    assert evidence["physical_rerun_performed"] is False
    assert evidence["prior_physical_evidence"]["content_mismatch_count"] == 0
    assert evidence["water_regression"]["status"] == "knowledge_based_skip"
    assert evidence["water_regression"]["report_available_in_public_candidate"] is False
    assert evidence["water_regression"]["new_result_claimed"] is False
    assert evidence["voxel_regression"]["status"] == "approved_knowledge_based_reuse"
    assert evidence["multi_beam_regression"]["status"] == "approved_knowledge_based_reuse"
    assert evidence["gpr_regression"]["status"] == "reusable_without_rerun"
    assert evidence["gpr_regression"]["approved_pass_rate_percent"] == 98.079471112706
    assert evidence["gpr_regression"]["evaluation_scale_factor_allowed"] is False


def test_beam6_controls_map_approved_evidence_to_current_public_classifier() -> None:
    evidence = load_evidence()["beam6_classification"]
    golden8 = evidence["golden8_control"]
    segment_imrt = evidence["segment_based_imrt_control"]

    golden8_classification, golden8_warnings = classify_delivery_type(
        SimpleNamespace(
            BeamNumber=golden8["beam_number"],
            BeamType=golden8["beam_type"],
            TreatmentDeliveryType="TREATMENT",
        ),
        [fixed_state(cmw=0.0), fixed_state(cmw=1.0)],
        TOLERANCES,
    )
    assert golden8_classification == golden8["expected_public_classification"]
    assert golden8_warnings == []
    assert golden8["expected_gate"] == "pass"

    dynamic_states = []
    for index in range(segment_imrt["control_point_count"]):
        state = fixed_state(cmw=index / 40.0)
        state["leaf_positions_mm"] = {
            "bank_1": [-5.0 - index / 100.0, -5.0],
            "bank_2": [5.0, 5.0 + index / 100.0],
        }
        dynamic_states.append(state)
    imrt_classification, imrt_warnings = classify_delivery_type(
        SimpleNamespace(
            BeamNumber=segment_imrt["beam_number"],
            BeamType=segment_imrt["beam_type"],
            TreatmentDeliveryType="TREATMENT",
        ),
        dynamic_states,
        TOLERANCES,
    )
    assert imrt_classification == segment_imrt["expected_public_classification"]
    assert imrt_warnings == []
    assert segment_imrt["positive_cmw_interval_count"] == 40
    assert segment_imrt["expected_gate"] == "reject"


def test_acceptance_evidence_contains_no_private_absolute_paths_or_uids() -> None:
    text = EVIDENCE_PATH.read_text(encoding="utf-8-sig")

    assert "DICOM/" not in text
    assert "1.2.840." not in text
