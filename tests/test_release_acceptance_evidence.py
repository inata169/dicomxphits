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

    assert evidence["prior_release_physical_rerun_performed"] is False
    assert evidence["prior_physical_evidence"]["content_mismatch_count"] == 0
    assert evidence["water_regression"]["status"] == "knowledge_based_skip"
    assert evidence["water_regression"]["report_available_in_public_candidate"] is False
    assert evidence["water_regression"]["new_result_claimed"] is False
    assert evidence["voxel_regression"]["status"] == "approved_knowledge_based_reuse"
    assert evidence["multi_beam_regression"]["status"] == "approved_knowledge_based_reuse"
    assert evidence["target_release"] == "v1.0.3"
    gpr = evidence["gpr_regression"]
    assert gpr["status"] == "historical_v1.0.0_evidence_only"
    assert gpr["historical_release"] == "v1.0.0"
    assert gpr["applicable_to_target_release"] is False
    assert gpr["evaluation_scale_factor_allowed"] is False

    manual = evidence["target_release_external_manual_check"]
    assert manual["status"] == "human_reported_complete_untracked"
    assert manual["release_gate_status"] == "passed"
    assert manual["agent_result_file_inspected"] is False
    assert manual["numerical_result_recorded"] is False
    assert manual["result_file_recorded"] is False
    assert manual["image_recorded"] is False
    assert manual["absolute_path_recorded"] is False
    assert manual["dicom_recorded"] is False
    assert "external_gpr_comparison" in manual["workflow_stages_completed"]

    offline = evidence["target_release_offline_bundle_check"]
    assert offline["status"] == "withheld_from_public_release"
    assert offline["publication_policy"] == "no_public_offline_asset"
    assert offline["artifact_name"] is None
    assert offline["artifact_sha256"] is None
    assert offline["manifest_source_head"] is None
    assert offline["installation"] == "human_reported_passed"
    assert offline["gui_launch"] == "human_reported_passed"
    assert (
        offline["verified_uninstall"]
        == "human_reported_failed_endpoint_security_blocked"
    )
    assert offline["final_artifact_confirmed"] is False
    assert offline["github_release_published"] is False
    assert offline["release_asset_uploaded"] is False
    assert offline["endpoint_protection_disable_or_exclusion_recommended"] is False


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
    assert "C:\\" not in text


def test_public_offline_guides_match_withdrawal_policy() -> None:
    english = (ROOT / "docs" / "windows-offline-installation.md").read_text(
        encoding="utf-8-sig"
    )
    japanese = (ROOT / "docs" / "windows-offline-installation.ja.md").read_text(
        encoding="utf-8-sig"
    )
    release_notes = (ROOT / "docs" / "release-notes-v1.0.3.md").read_text(
        encoding="utf-8-sig"
    )

    assert "no currently supported public Windows offline bundle" in english
    assert "maintainer evaluation" in english
    assert "現在、supported public Windows offline bundleはありません" in japanese
    assert "maintainer evaluation" in japanese
    assert "will not include a Windows offline ZIP" in release_notes
