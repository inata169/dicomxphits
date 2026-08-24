from __future__ import annotations

import json
from pathlib import Path

import pytest

from dicomxphits.calculation_config import (
    CalculationConfigError,
    load_calculation_config,
    public_default_calculation_config,
    require_rendered_3d_mesh,
    validate_rtdose_serialization_preflight,
)


PUBLIC_ROOT = Path(__file__).resolve().parents[1]


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "calculation.json"
    path.write_text(body, encoding="utf-8")
    return path


def config_text(
    *,
    center_min: str = "[-150, -150, -100]",
    center_max: str = "[150, 150, 200]",
    voxel_size: str = "[3, 3, 3]",
    extra_root: str = "",
) -> str:
    return (
        "{\n"
        '  "schema_version": "dicomxphits_public_calculation_config_v1",\n'
        '  "dose_tally_3d": {\n'
        f'    "center_min_mm": {center_min},\n'
        f'    "center_max_mm": {center_max},\n'
        f'    "voxel_size_mm": {voxel_size}\n'
        "  }"
        f"{extra_root}\n"
        "}\n"
    )


def test_public_example_and_built_in_default_normalize_identically() -> None:
    example = load_calculation_config(
        PUBLIC_ROOT / "config" / "dicomxphits.calculation.example.json"
    )
    default = public_default_calculation_config()

    assert example.semantic_sha256 == default.semantic_sha256
    assert default.renderer_mesh() == {
        "axes": {
            "x": {
                "minimum_cm": "-15.15",
                "maximum_cm": "15.15",
                "bin_count": 101,
                "voxel_size_mm": "3",
            },
            "y": {
                "minimum_cm": "-15.15",
                "maximum_cm": "15.15",
                "bin_count": 101,
                "voxel_size_mm": "3",
            },
            "z": {
                "minimum_cm": "-10.15",
                "maximum_cm": "20.15",
                "bin_count": 101,
                "voxel_size_mm": "3",
            },
        }
    }
    assert default.source == "built_in_legacy_default"
    assert example.source == "user_supplied"
    assert example.source_sha256 is not None


def test_asymmetric_anisotropic_decimal_mesh_is_exact(tmp_path: Path) -> None:
    config = load_calculation_config(
        write_config(
            tmp_path,
            config_text(
                center_min="[-1.25, -2, -3]",
                center_max="[1.25, 2, 3]",
                voxel_size="[0.25, 0.5, 1.5]",
            ),
        )
    )

    assert config.counts == (11, 9, 5)
    assert config.renderer_mesh()["axes"]["x"] == {
        "minimum_cm": "-0.1375",
        "maximum_cm": "0.1375",
        "bin_count": 11,
        "voxel_size_mm": "0.25",
    }
    assert config.renderer_mesh()["axes"]["z"] == {
        "minimum_cm": "-0.375",
        "maximum_cm": "0.375",
        "bin_count": 5,
        "voxel_size_mm": "1.5",
    }


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("not json", "malformed JSON"),
        (
            config_text().replace(
                "dicomxphits_public_calculation_config_v1",
                "unsupported",
            ),
            "schema_version",
        ),
        (
            '{"schema_version":"dicomxphits_public_calculation_config_v1"}',
            "dose_tally_3d",
        ),
        (
            config_text(extra_root=',\n  "unexpected": true'),
            "unsupported field",
        ),
        (
            config_text().replace(
                '"voxel_size_mm": [3, 3, 3]',
                '"voxel_size_mm": [3, 3, 3], "unexpected": 1',
            ),
            "unsupported field",
        ),
        (config_text(center_min="[false, -150, -100]"), "JSON number"),
        (config_text(voxel_size='["3", 3, 3]'), "JSON number"),
        (config_text(center_min="[-150, -150]"), "exactly three"),
        (config_text(center_min="[0, -150, -100]", center_max="[0, 150, 200]"), "must be less"),
        (config_text(voxel_size="[0, 3, 3]"), "must be positive"),
        (config_text(center_max="[1, 150, 200]", voxel_size="[0.3, 3, 3]"), "exact multiple"),
    ],
)
def test_invalid_configurations_fail_closed(
    tmp_path: Path,
    body: str,
    message: str,
) -> None:
    with pytest.raises(CalculationConfigError, match=message):
        load_calculation_config(write_config(tmp_path, body))


def test_oversized_file_and_numeric_token_fail_before_parsing(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * 65_537)
    with pytest.raises(CalculationConfigError, match="65536 bytes"):
        load_calculation_config(oversized)

    token = "1." + "2" * 63
    with pytest.raises(CalculationConfigError, match="numeric token"):
        load_calculation_config(
            write_config(tmp_path, config_text(center_min=f"[{token}, -150, -100]"))
        )


def test_oversized_file_read_is_bounded(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * 70_000)
    original_open = Path.open
    requested_sizes: list[int] = []

    class RecordingReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def read(self, size=-1):
            requested_sizes.append(size)
            return self.stream.read(size)

    def recording_open(self, *args, **kwargs):
        return RecordingReader(original_open(self, *args, **kwargs))

    monkeypatch.setattr(Path, "open", recording_open)
    with pytest.raises(CalculationConfigError, match="65536 bytes"):
        load_calculation_config(path)

    assert requested_sizes == [65_537]


def test_derived_render_token_overflow_fails_closed(tmp_path: Path) -> None:
    minimum = "1" + "0" * 62
    maximum = str(int(minimum) + 1)
    with pytest.raises(CalculationConfigError, match="64-character"):
        load_calculation_config(
            write_config(
                tmp_path,
                config_text(
                    center_min=f"[{minimum}, 0, 0]",
                    center_max=f"[{maximum}, 1, 1]",
                    voxel_size="[1, 1, 1]",
                ),
            )
        )


def test_compact_huge_exponent_fails_before_decimal_expansion(tmp_path: Path) -> None:
    with pytest.raises(CalculationConfigError, match="canonical limit"):
        load_calculation_config(
            write_config(
                tmp_path,
                config_text(
                    center_min="[1e100000000, 1e100000000, 1e100000000]",
                    center_max="[2e100000000, 2e100000000, 2e100000000]",
                    voxel_size="[1e100000000, 1e100000000, 1e100000000]",
                ),
            )
        )


def test_axis_and_total_voxel_limits_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(CalculationConfigError, match="1000"):
        load_calculation_config(
            write_config(
                tmp_path,
                config_text(center_min="[0, 0, 0]", center_max="[1000, 1, 1]", voxel_size="[1, 1, 1]"),
            )
        )
    with pytest.raises(CalculationConfigError, match="10000000"):
        load_calculation_config(
            write_config(
                tmp_path,
                config_text(center_min="[0, 0, 0]", center_max="[215, 215, 215]", voxel_size="[1, 1, 1]"),
            )
        )


def test_binary64_edge_collapse_fails_closed(tmp_path: Path) -> None:
    minimum = "1" + "0" * 60
    maximum = "1" + "0" * 59 + "1"
    with pytest.raises(CalculationConfigError, match="binary64"):
        load_calculation_config(
            write_config(
                tmp_path,
                config_text(
                    center_min=f"[{minimum}, 0, 0]",
                    center_max=f"[{maximum}, 1, 1]",
                    voxel_size="[1, 1, 1]",
                ),
            )
        )


def test_sub_resolution_dicom_spacing_fails_preflight(tmp_path: Path) -> None:
    config = load_calculation_config(
        write_config(
            tmp_path,
            config_text(
                center_min="[0, 0, 0]",
                center_max="[1e-20, 1e-20, 1e-20]",
                voxel_size="[1e-20, 1e-20, 1e-20]",
            ),
        )
    )

    with pytest.raises(CalculationConfigError, match="PixelSpacing"):
        validate_rtdose_serialization_preflight(
            config,
            rtplan_isocenter_dicom_mm=(0.0, 0.0, 0.0),
        )


def test_oversized_dicom_decimal_string_fails_preflight(tmp_path: Path) -> None:
    config = load_calculation_config(
        write_config(
            tmp_path,
            config_text(
                center_min="[1000000, 0, 0]",
                center_max="[1000001, 1, 1]",
                voxel_size="[1, 1, 1]",
            ),
        )
    )

    with pytest.raises(CalculationConfigError, match="16-character"):
        validate_rtdose_serialization_preflight(
            config,
            rtplan_isocenter_dicom_mm=(0.0, 0.0, 0.0),
        )


def test_large_offset_binary64_affine_cancellation_fails_preflight(
    tmp_path: Path,
) -> None:
    config = load_calculation_config(
        write_config(
            tmp_path,
            config_text(
                center_min="[100000000000, 0, 0]",
                center_max="[100000000000.001, 0.001, 0.001]",
                voxel_size="[0.001, 0.001, 0.001]",
            ),
        )
    )

    with pytest.raises(CalculationConfigError, match="voxel-position residual"):
        validate_rtdose_serialization_preflight(
            config,
            rtplan_isocenter_dicom_mm=(100000000000.0, 0.0, 0.0),
        )


def test_semantic_digest_excludes_schema_editor_metadata(tmp_path: Path) -> None:
    plain = load_calculation_config(write_config(tmp_path, config_text()))
    with_schema_path = tmp_path / "with-schema.json"
    payload = json.loads(config_text())
    payload["$schema"] = "editor-only.json"
    with_schema_path.write_text(json.dumps(payload), encoding="utf-8")
    with_schema = load_calculation_config(with_schema_path)

    assert plain.semantic_sha256 == with_schema.semantic_sha256
    assert plain.source_sha256 != with_schema.source_sha256


def test_rendered_mesh_gate_requires_exact_normalized_tokens() -> None:
    config = public_default_calculation_config()
    block = """[ T-Deposit ]
 xmin = -15.15
 xmax = 15.15
 nx = 101
 ymin = -15.15
 ymax = 15.15
 ny = 101
 zmin = -10.15
 zmax = 20.15
 nz = 101

[ T-Deposit ]
"""
    require_rendered_3d_mesh(block, config)

    with pytest.raises(CalculationConfigError, match="normalized 3D tally"):
        require_rendered_3d_mesh(block.replace(" nx = 101", " nx = 100"), config)
