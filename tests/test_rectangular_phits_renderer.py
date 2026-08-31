from __future__ import annotations

import copy
import hashlib
import inspect
import math
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

import dicomxphits.rectangular_phits_renderer as renderer_module
from dicomxphits.calculation_config import load_calculation_config
from dicomxphits.public_spectrum import (
    PUBLIC_SPECTRUM_BIN_COUNT,
    PUBLIC_SPECTRUM_SHA256,
    PUBLIC_SPECTRUM_SIZE,
    PUBLIC_SPECTRUM_TERMINAL_BOUNDARY_MEV,
    PUBLIC_SPECTRUM_TEXT,
    public_spectrum_lines,
)
from dicomxphits.rectangular_phits_renderer import (
    RectangularPhitsRendererError,
    render_rectangular_phits_input,
    render_rectangular_model_sections,
)


MODEL_SECTIONS = [
    "[ Source ]",
    "[ Surface ]",
    "[ Cell ]",
    "[ Material ]",
    "[ E N D ]",
]
ALL_SECTION_HEADERS = [
    "[ Title ]",
    "[ Parameters ]",
    "[ S o u r c e ]",
    "[ Source ]",
    "[ Surface ]",
    "[ Cell ]",
    "[ Material ]",
    "[ Transform ]",
    "[ T-Deposit ]",
    "[ E N D ]",
]
LEGACY_PLACEHOLDER_MARKERS = [
    "9001 so 100.0",
    "Segment dose placeholder",
    "minimal water sphere",
]


def jaw_only_geometry(**overrides):
    """Minimal valid renderer-facing PR 2B jaw-only intermediate geometry."""

    geometry = {
        "segment_id": "seg_b0001_s0000",
        "geometry_mode": "rectangular_3dcrt",
        "units": {"geometry": "cm", "angles": "deg", "density": "g/cm3"},
        "delivery_type": "3dcrt_static",
        "jaw_positions_cm": {"x1": -4.0, "x2": 4.0, "y1": -5.0, "y2": 5.0},
        "mlc_aperture_state": "no_mlc",
        "mlc_positions_cm": None,
        "angles_deg": {"gantry": 10.0, "collimator": 20.0, "couch": 0.0},
        "fluence_weight": {"kind": "monitor_units", "value": 100.0},
        "source": {"model": "point", "position_cm": [0.0, 0.0, -100.0]},
        "y_diaphragm": {"upstream_z_cm": -46.1, "downstream_z_cm": -38.0, "material": "shielding"},
        "mlc_geometry": {
            "leaf_pair_count": 2,
            "leaf_widths_cm": [0.5, 0.5],
            "leaf_depth_cm": 6.0,
            "upstream_z_cm": -35.0,
            "downstream_z_cm": -30.0,
            "material": "shielding",
        },
        "materials": {
            "shielding": {
                "density_g_cm3": 17.0,
                "material_block": "74W 1",
            },
            "unused": {
                "density_g_cm3": 1.0,
                "material_block": "1H 2\n16O 1",
            },
        },
        "coordinate_system": {"origin": "isocenter", "z_axis": "beam", "z_positive": "downstream"},
        "transport": {
            "photon_cutoff_mev": 0.01,
            "electron_cutoff_mev": 0.7,
            "positron_cutoff_mev": 0.7,
        },
        "renderer_ready_unit_marker": "cm_deg_g_cm3",
    }
    geometry.update(overrides)
    return geometry


def jaw_mlc_geometry(**overrides):
    """Valid renderer-facing PR 2B jaw+MLC intermediate geometry."""

    geometry = jaw_only_geometry(
        mlc_aperture_state="present",
        mlc_positions_cm={"bank_a": [-2.0, -1.0], "bank_b": [2.0, 1.0]},
    )
    geometry.update(overrides)
    return geometry


def render(geometry=None, **kwargs):
    return render_rectangular_model_sections(
        geometry or jaw_mlc_geometry(),
        **kwargs,
    )


def render_runtime(geometry=None, **kwargs):
    return render_rectangular_phits_input(
        geometry or jaw_mlc_geometry(),
        "segments/seg_001/deposit-target-3D.out",
        voxel_counts=(4, 3, 2),
        **kwargs,
    )


def section_positions(text):
    return [text.index(section) for section in MODEL_SECTIONS]


def parsed_surfaces_and_cells(text):
    surface_ids = set()
    cells = {}
    section = None
    current_cell_id = None
    for line in text.splitlines():
        if line in ALL_SECTION_HEADERS:
            section = line
            current_cell_id = None
            continue
        parts = line.split()
        if not parts:
            continue
        if section == "[ Surface ]" and parts[0].isdigit():
            surface_ids.add(int(parts[0]))
        elif section == "[ Cell ]" and parts[0].isdigit():
            cell_id = int(parts[0])
            material = int(parts[1])
            cell_tokens = parts[: parts.index("$")] if "$" in parts else parts
            expression_start = 3 if material > 0 else 2
            cells[cell_id] = {
                "material": material,
                "expression": cell_tokens[expression_start:],
                "raw": cell_tokens,
            }
            current_cell_id = cell_id
        elif section == "[ Cell ]" and current_cell_id is not None:
            continuation_tokens = parts[: parts.index("$")] if "$" in parts else parts
            cells[current_cell_id]["expression"].extend(continuation_tokens)
            cells[current_cell_id]["raw"].extend(continuation_tokens)
    return surface_ids, cells


def parsed_section_key_values(text, section_name):
    values = {}
    section = None
    for line in text.splitlines():
        if line in ALL_SECTION_HEADERS:
            section = line
            continue
        if section != section_name:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("c ") or stripped.startswith("$ "):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parsed_runtime_tr3(text, gantry_deg):
    transform = text.split("[ Transform ]\n", 1)[1].split("\n[ T-Deposit ]", 1)[0]
    lines = transform.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("tr3 "))
    tokens = [line.strip() for line in lines[start + 1 : start + 10]]
    sine = math.sin(math.radians(gantry_deg))
    cosine = math.cos(math.radians(gantry_deg))

    def value(token):
        if token == "0":
            return 0.0
        if token == "1":
            return 1.0
        if token == "cos(c20/180*pi)":
            return cosine
        if token == "sin(c20/180*pi)":
            return sine
        if token == "-sin(c20/180*pi)":
            return -sine
        raise AssertionError(f"unexpected tr3 token: {token}")

    values = [value(token) for token in tokens]
    return [values[0:3], values[3:6], values[6:9]]


def parsed_runtime_tr2(text, collimator_deg):
    transform = text.split("[ Transform ]\n", 1)[1].split("\n[ T-Deposit ]", 1)[0]
    lines = transform.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("tr2 "))
    tokens = [line.strip() for line in lines[start + 1 : start + 10]]
    sine = math.sin(math.radians(collimator_deg))
    cosine = math.cos(math.radians(collimator_deg))
    values_by_token = {
        "cos(c10/180*pi)*cos(c21/180*pi)": cosine,
        "-sin(c10/180*pi)*cos(c31/180*pi)+cos(c10/180*pi)*sin(c21/180*pi)*sin(c31/180*pi)": -sine,
        "-sin(c10/180*pi)*sin(c31/180*pi)-cos(c10/180*pi)*sin(c21/180*pi)*cos(c31/180*pi)": 0.0,
        "sin(c10/180*pi)*cos(c21/180*pi)": sine,
        "cos(c10/180*pi)*cos(c31/180*pi)+sin(c10/180*pi)*sin(c21/180*pi)*sin(c31/180*pi)": cosine,
        "cos(c10/180*pi)*sin(c31/180*pi)-sin(c10/180*pi)*sin(c21/180*pi)*cos(c31/180*pi)": 0.0,
        "sin(c21/180*pi)": 0.0,
        "-cos(c21/180*pi)*sin(c31/180*pi)": 0.0,
        "cos(c21/180*pi)*cos(c31/180*pi)": 1.0,
    }
    values = [values_by_token[token] for token in tokens]
    return [values[0:3], values[3:6], values[6:9]]


def complement_cell_ids(expression):
    return {int(token[1:]) for token in expression if token.startswith("#") and token[1:].isdigit()}


def surface_ids_in_expression(expression):
    return {abs(int(token)) for token in expression if token.lstrip("-").isdigit()}


def physical_cell_lines(text, cell_id):
    lines = []
    section = None
    in_target = False
    for line in text.splitlines():
        if line in ALL_SECTION_HEADERS:
            section = line
            in_target = False
            continue
        parts = line.split()
        if section != "[ Cell ]" or not parts:
            continue
        if parts[0].isdigit():
            in_target = int(parts[0]) == cell_id
        if in_target:
            lines.append(line)
    return lines


def test_renderer_docstring_and_fixtures_define_pr2b_contract():
    doc = inspect.getdoc(render_rectangular_phits_input)

    assert "complete public CT-voxel" in doc
    assert "centimeters" in doc
    assert "does not read DICOM" in doc
    assert "voxel_counts" in doc
    assert jaw_only_geometry()["renderer_ready_unit_marker"] == "cm_deg_g_cm3"
    assert jaw_only_geometry()["mlc_positions_cm"] is None
    assert jaw_mlc_geometry()["mlc_positions_cm"]["bank_a"] == [-2.0, -1.0]


def test_minimal_jaw_only_fixture_renders_without_mlc_cells():
    text = render(jaw_only_geometry())

    assert "lower Y-Diaphragm shield" in text
    assert "upper Y-Diaphragm shield" in text
    assert "MLC bank" not in text
    assert "MAT[1] $ shielding" in text


def test_jaw_mlc_fixture_renders_y_diaphragm_and_rectangular_mlc_cells():
    text = render(jaw_mlc_geometry())

    assert "1101 rpp" in text
    assert "1102 rpp" in text
    assert "2001 rpp" in text
    assert "2002 rpp" in text
    assert "MLC bank A leaf pair 0" in text
    assert "MLC bank B leaf pair 1" in text


def test_deterministic_section_order_and_final_end_line():
    text = render()

    assert section_positions(text) == sorted(section_positions(text))
    assert text.rstrip().splitlines()[-1] == "[ E N D ]"
    assert text.endswith("[ E N D ]\n")


def test_repeated_rendering_is_identical_and_does_not_mutate_input():
    geometry = jaw_mlc_geometry()
    before = copy.deepcopy(geometry)

    first = render(geometry)
    second = render(geometry)

    assert first == second
    assert geometry == before


def test_scalar_parameters_are_rendered():
    text = render_runtime(maxcas=25, maxbch=3, epsout=1)

    assert " maxcas = 25" in text
    assert " maxbch = 3" in text
    assert " epsout = 1" in text
    assert " e-type = 1" in text
    assert " ne = 59" in text
    assert "photon_spectrum = Precise06mv_energy-112.inp" in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"maxcas": 0},
        {"maxcas": True},
        {"maxbch": 0},
        {"maxbch": 1.5},
        {"epsout": float("inf")},
    ],
)
def test_invalid_scalar_parameters_raise(kwargs):
    with pytest.raises(RectangularPhitsRendererError):
        render_runtime(**kwargs)


def test_angles_drive_runtime_source_and_transforms():
    text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={"gantry": 90.0, "collimator": 45.0, "couch": 0.0}
        )
    )

    assert "set: c10[45] $ Collimator angle (deg)" in text
    assert "set: c20[90] $ Gantry angle (deg)" in text
    assert "tr2   0 0 0" in text
    assert "tr3   0.0000 0.0000 0.0000" in text
    source = text.split("[ S o u r c e ]\n", 1)[1].split("\n[ Surface ]", 1)[0]
    assert " x0 = -100" in source
    assert " dir = 0" in source
    assert " phi = 0" in source


@pytest.mark.parametrize(
    ("gantry_deg", "source_lps_mm", "direction_lps"),
    [
        (0.0, (0.0, -1000.0, 0.0), (0.0, 1.0, 0.0)),
        (90.0, (1000.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
        (180.0, (0.0, 1000.0, 0.0), (0.0, -1.0, 0.0)),
        (270.0, (-1000.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (
            45.0,
            (1000.0 / math.sqrt(2.0), -1000.0 / math.sqrt(2.0), 0.0),
            (-1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0),
        ),
        (
            315.0,
            (-1000.0 / math.sqrt(2.0), -1000.0 / math.sqrt(2.0), 0.0),
            (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0),
        ),
    ],
)
def test_runtime_gantry_geometry_has_independent_dicom_lps_anchors(
    gantry_deg,
    source_lps_mm,
    direction_lps,
):
    text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={"gantry": gantry_deg, "collimator": 0.0, "couch": 0.0}
        )
    )
    source = parsed_section_key_values(text, "[ S o u r c e ]")
    source_phits = (
        float(source["x0"]),
        float(source["y0"]),
        float(source["z0"]),
    )
    polar_cosine = float(source["dir"])
    azimuth = math.radians(float(source["phi"]))
    transverse = math.sqrt(max(0.0, 1.0 - polar_cosine**2))
    direction_phits = (
        transverse * math.cos(azimuth),
        transverse * math.sin(azimuth),
        polar_cosine,
    )
    expected_direction_phits = (
        math.sin(math.radians(gantry_deg)),
        0.0,
        math.cos(math.radians(gantry_deg)),
    )
    expected_source_phits = tuple(-100.0 * value for value in expected_direction_phits)
    assert source_phits == pytest.approx(expected_source_phits, abs=1.0e-10)
    assert direction_phits == pytest.approx(expected_direction_phits, abs=1.0e-10)
    assert tuple(
        source_phits[index] + 100.0 * direction_phits[index]
        for index in range(3)
    ) == pytest.approx((0.0, 0.0, 0.0), abs=1.0e-10)

    tr3 = parsed_runtime_tr3(text, gantry_deg)
    transformed_local_beam = tuple(tr3[2])
    transformed_local_source = tuple(-100.0 * value for value in tr3[2])
    assert transformed_local_beam == pytest.approx(direction_phits, abs=1.0e-10)
    assert transformed_local_source == pytest.approx(source_phits, abs=1.0e-10)

    mapped_source = (
        -10.0 * source_phits[0],
        10.0 * source_phits[2],
        10.0 * source_phits[1],
    )
    mapped_direction = (
        -direction_phits[0],
        direction_phits[2],
        direction_phits[1],
    )
    assert mapped_source == pytest.approx(source_lps_mm, abs=1.0e-9)
    assert mapped_direction == pytest.approx(direction_lps, abs=1.0e-10)


@pytest.mark.parametrize(
    ("collimator_deg", "mlcx_axis_lps", "mlcy_axis_lps"),
    [
        (0.0, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        (90.0, (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0)),
        (180.0, (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        (270.0, (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)),
        (
            30.0,
            (math.sqrt(3.0) / 2.0, 0.0, 0.5),
            (-0.5, 0.0, math.sqrt(3.0) / 2.0),
        ),
    ],
)
def test_runtime_collimator_geometry_has_independent_dicom_lps_anchors(
    collimator_deg,
    mlcx_axis_lps,
    mlcy_axis_lps,
):
    text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={
                "gantry": 0.0,
                "collimator": collimator_deg,
                "couch": 0.0,
            }
        )
    )

    tr2 = parsed_runtime_tr2(text, collimator_deg)
    # DICOM MLCX +X is PHITS local -X; MLCY +Y is PHITS local +Y.
    mlcx_phits = tuple(-value for value in tr2[0])
    mlcy_phits = tuple(tr2[1])

    def phits_to_dicom_lps(vector):
        x_value, y_value, z_value = vector
        return (-x_value, z_value, y_value)

    actual_mlcx_axis_lps = phits_to_dicom_lps(mlcx_phits)
    actual_mlcy_axis_lps = phits_to_dicom_lps(mlcy_phits)
    assert actual_mlcx_axis_lps == pytest.approx(
        mlcx_axis_lps,
        abs=1.0e-10,
    )
    assert actual_mlcy_axis_lps == pytest.approx(
        mlcy_axis_lps,
        abs=1.0e-10,
    )
    assert sum(value**2 for value in actual_mlcx_axis_lps) == pytest.approx(1.0)
    assert sum(value**2 for value in actual_mlcy_axis_lps) == pytest.approx(1.0)
    assert sum(
        x_value * y_value
        for x_value, y_value in zip(
            actual_mlcx_axis_lps,
            actual_mlcy_axis_lps,
            strict=True,
        )
    ) == pytest.approx(0.0, abs=1.0e-10)
    assert actual_mlcx_axis_lps[1] == pytest.approx(0.0, abs=1.0e-10)
    assert actual_mlcy_axis_lps[1] == pytest.approx(0.0, abs=1.0e-10)


@pytest.mark.parametrize(
    ("gantry_deg", "collimator_deg"),
    [
        (0.0, 0.0),
        (90.0, 0.0),
        (45.0, 30.0),
        (315.0, 90.0),
    ],
)
def test_ct_wrapper_excludes_complete_transformed_accelerator_at_supported_angles(
    gantry_deg,
    collimator_deg,
):
    text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={
                "gantry": gantry_deg,
                "collimator": collimator_deg,
                "couch": 0.0,
            }
        )
    )

    assert "1201 0 -98 #2 fill=4000" in text
    assert "2 0 11 -12 -13 fill=2 trcl=3" in text
    assert text.index("1201 0 -98 #2 fill=4000") < text.index(
        "2 0 11 -12 -13 fill=2 trcl=3"
    )


def test_runtime_collimator_positive_angle_preserves_asymmetric_feature_orientation():
    def transformed_feature_lps(collimator_deg):
        text = render_runtime(
            jaw_mlc_geometry(
                angles_deg={
                    "gantry": 0.0,
                    "collimator": collimator_deg,
                    "couch": 0.0,
                }
            )
        )
        tr2 = parsed_runtime_tr2(text, collimator_deg)
        mlcx_phits = tuple(-value for value in tr2[0])
        mlcy_phits = tuple(tr2[1])

        def phits_to_dicom_lps(vector):
            x_value, y_value, z_value = vector
            return (-x_value, z_value, y_value)

        mlcx_lps = phits_to_dicom_lps(mlcx_phits)
        mlcy_lps = phits_to_dicom_lps(mlcy_phits)
        return tuple(
            2.0 * mlcx_value + mlcy_value
            for mlcx_value, mlcy_value in zip(mlcx_lps, mlcy_lps, strict=True)
        )

    positive = transformed_feature_lps(30.0)
    negative = transformed_feature_lps(-30.0)
    assert positive == pytest.approx(
        (math.sqrt(3.0) - 0.5, 0.0, 1.0 + math.sqrt(3.0) / 2.0),
        abs=1.0e-10,
    )
    assert negative == pytest.approx(
        (math.sqrt(3.0) + 0.5, 0.0, -1.0 + math.sqrt(3.0) / 2.0),
        abs=1.0e-10,
    )
    assert positive != pytest.approx(negative, abs=1.0e-10)


def test_collimator_correction_preserves_dicom_angle_source_and_gantry_transform():
    zero_text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={"gantry": 90.0, "collimator": 0.0, "couch": 0.0}
        )
    )
    positive_text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={"gantry": 90.0, "collimator": 30.0, "couch": 0.0}
        )
    )

    def source_section(text):
        return text.split("[ S o u r c e ]\n", 1)[1].split("\n[ Surface ]", 1)[0]

    def tr3_lines(text):
        transform = text.split("[ Transform ]\n", 1)[1].split(
            "\n[ T-Deposit ]",
            1,
        )[0]
        lines = transform.splitlines()
        start = next(index for index, line in enumerate(lines) if line.startswith("tr3 "))
        return lines[start : start + 11]

    assert "set: c10[30] $ Collimator angle (deg)" in positive_text
    assert "set: c10[-30]" not in positive_text
    assert source_section(positive_text) == source_section(zero_text)
    assert tr3_lines(positive_text) == tr3_lines(zero_text)


def test_gantry_zero_source_and_transform_text_remain_unchanged():
    text = render_runtime(
        jaw_mlc_geometry(
            angles_deg={"gantry": 0.0, "collimator": 0.0, "couch": 0.0}
        )
    )
    source = text.split("[ S o u r c e ]\n", 1)[1].split("\n[ Surface ]", 1)[0]
    transform = text.split("[ Transform ]\n", 1)[1].split("\n[ T-Deposit ]", 1)[0]
    assert " x0 = 0\n" in source
    assert " z0 = -100\n" in source
    assert " dir = 1\n" in source
    assert " phi = 0\n" in source
    assert "      sin(c20/180*pi)\n" in transform
    assert "     -sin(c20/180*pi)\n" in transform


def test_relative_expected_output_path_is_reflected_in_t_deposit():
    text = render_rectangular_phits_input(
        jaw_mlc_geometry(),
        "segments/seg_002/dose.out",
        voxel_counts=(4, 3, 2),
    )

    assert "[ T-Deposit ]" in text
    assert " file = segments/seg_002/dose.out" in text


def test_custom_calculation_config_changes_only_the_3d_tally_mesh(tmp_path):
    config_path = tmp_path / "calculation.json"
    config_path.write_text(
        """{
  "schema_version": "dicomxphits_public_calculation_config_v1",
  "dose_tally_3d": {
    "center_min_mm": [-1.25, -2, -3],
    "center_max_mm": [1.25, 2, 3],
    "voxel_size_mm": [0.25, 0.5, 1.5]
  }
}
""",
        encoding="utf-8",
    )
    default_text = render_runtime()
    custom_text = render_runtime(
        calculation_config=load_calculation_config(config_path)
    )

    _default_prefix, default_3d, default_pdd = default_text.split(
        "[ T-Deposit ]\n", 2
    )
    _custom_prefix, custom_3d, custom_pdd = custom_text.split(
        "[ T-Deposit ]\n", 2
    )
    assert "[ T-Deposit ]\n" + default_3d == (
        "[ T-Deposit ]\n"
        " title = Public CT voxel 101x101x101 dose grid, 3 mm spacing\n"
        " mesh = xyz\n"
        " x-type = 2\n"
        " xmin = -15.15\n"
        " xmax = 15.15\n"
        " nx = 101\n"
        " y-type = 2\n"
        " ymin = -15.15\n"
        " ymax = 15.15\n"
        " ny = 101\n"
        " z-type = 2\n"
        " zmin = -10.15\n"
        " zmax = 20.15\n"
        " nz = 101\n"
        " unit = 0\n"
        " material = all\n"
        " output = dose\n"
        " axis = xy\n"
        " file = segments/seg_001/deposit-target-3D.out\n"
        " part = all\n"
        " epsout = 1\n\n"
    )
    assert default_pdd == custom_pdd
    assert " title = Public CT voxel 11x9x5 dose grid, x/y/z spacing 0.25/0.5/1.5 mm" in custom_3d
    assert " xmin = -0.1375" in custom_3d
    assert " xmax = 0.1375" in custom_3d
    assert " nx = 11" in custom_3d
    assert " ymin = -0.225" in custom_3d
    assert " ymax = 0.225" in custom_3d
    assert " ny = 9" in custom_3d
    assert " zmin = -0.375" in custom_3d
    assert " zmax = 0.375" in custom_3d
    assert " nz = 5" in custom_3d


def test_renderer_emits_exact_approved_totfact_when_supplied():
    text = render_rectangular_phits_input(
        jaw_mlc_geometry(),
        "segments/seg_002/dose.out",
        totfact_per_mu="8.7608E+11",
        voxel_counts=(4, 3, 2),
    )

    assert " totfact = 8.7608E+11" in text
    parameters = text.split("[ Parameters ]\n", 1)[1].split("\n[ S o u r c e ]", 1)[0]
    source = text.split("[ S o u r c e ]\n", 1)[1].split("\n[ Surface ]", 1)[0]
    assert "totfact" not in parameters
    assert " totfact = 8.7608E+11" in source


def test_rectangular_smoke_input_has_source_and_t_deposit_contract():
    expected_output = "segments/seg_b0001_s0000/deposit-target-3D.out"
    geometry = jaw_mlc_geometry(
        angles_deg={"gantry": 0.0, "collimator": 0.0, "couch": 0.0}
    )
    text = render_rectangular_phits_input(
        geometry,
        expected_output,
        voxel_counts=(4, 3, 2),
    )
    source = parsed_section_key_values(text, "[ S o u r c e ]")
    params = parsed_section_key_values(text, "[ Parameters ]")
    tally = parsed_section_key_values(text, "[ T-Deposit ]")

    assert source == {
        "s-type": "5",
        "proj": "photon",
        "x0": "0",
        "x1": "0",
        "y0": "0",
        "y1": "0",
        "z0": "-100",
        "z1": "-100",
        "dir": "1",
        "phi": "0",
        "dom": "atan(sqrt(20**2+20**2)/2.0/100.0)*180.0/pi",
        "e-type": "1",
        "ne": "59",
    }
    assert params["emin(2)"] == "0.01"
    assert params["emin(12)"] == "0.7"
    assert params["emin(13)"] == "0.7"
    assert params["emin(14)"] == "0.01"
    assert params["igamma"] == "2"
    assert params["ipnint"] == "0"
    assert params["negs"] == "1"
    assert params["file(6)"] == "phits.out"
    assert tally["title"] == "Public CT voxel central-axis PDD, reference depth 10 cm"
    assert tally["mesh"] == "xyz"
    assert tally["x-type"] == "2"
    assert tally["y-type"] == "2"
    assert tally["z-type"] == "2"
    assert tally["nx"] == "1"
    assert tally["ny"] == "1"
    assert tally["nz"] == "101"
    assert tally["file"] == "segments/seg_b0001_s0000/deposit-pdd.out"
    assert tally["output"] == "dose"
    assert tally["part"] == "all"


def test_uniform_3mm_source_renders_exact_public_boundaries():
    geometry = jaw_mlc_geometry(
        source={
            "model": "uniform_rectangular",
            "plane_z_cm": -100.0,
            "width_x_cm": 0.3,
            "width_y_cm": 0.3,
        }
    )

    source = parsed_section_key_values(render(geometry), "[ Source ]")

    assert source["s-type"] == "5"
    assert source["x0"] == "-0.15"
    assert source["x1"] == "0.15"
    assert source["y0"] == "-0.15"
    assert source["y1"] == "0.15"
    assert source["z0"] == "-100"
    assert source["z1"] == "-100"
    assert source["dom"] == "atan(sqrt(20**2+20**2)/2.0/100.0)*180.0/pi"


def test_approved_public_spectrum_identity_and_rendered_rows_are_exact():
    payload = PUBLIC_SPECTRUM_TEXT.encode("ascii")
    rows = public_spectrum_lines()
    text = render()
    source_text = text.split("[ Source ]\n", 1)[1].split("\n[ Surface ]", 1)[0]

    assert len(payload) == PUBLIC_SPECTRUM_SIZE
    assert hashlib.sha256(payload).hexdigest() == PUBLIC_SPECTRUM_SHA256
    assert len(rows[:-1]) == PUBLIC_SPECTRUM_BIN_COUNT
    assert rows[-1] == PUBLIC_SPECTRUM_TERMINAL_BOUNDARY_MEV
    assert all(row in source_text for row in rows)
    assert " e0 =" not in source_text


@pytest.mark.parametrize("path", ["", "dose.out\nother.out", "dose.out\rother.out"])
def test_invalid_expected_output_path_raises(path):
    with pytest.raises(RectangularPhitsRendererError, match="expected_output_path"):
        render_rectangular_phits_input(
            jaw_mlc_geometry(),
            path,
            voxel_counts=(4, 3, 2),
        )


def test_negative_zero_formats_as_zero_and_nan_geometry_raises():
    geometry = jaw_mlc_geometry(source={"model": "point", "position_cm": [-0.0, 0.0, -100.0]})
    text = render(geometry)

    assert " x0 = 0" in text
    assert " x0 = -0" not in text
    bad = jaw_mlc_geometry()
    bad["jaw_positions_cm"]["x1"] = math.nan
    with pytest.raises(RectangularPhitsRendererError):
        render(bad)


@pytest.mark.parametrize("state", ["no_mlc", "fully_open_mlc"])
def test_explicit_jaw_only_states_render_without_mlc_cells(state):
    text = render(jaw_only_geometry(mlc_aperture_state=state, mlc_positions_cm=None))

    assert "MLC bank" not in text


@pytest.mark.parametrize(
    "patch",
    [
        {"mlc_aperture_state": "present", "mlc_positions_cm": None},
        {"mlc_aperture_state": "no_mlc", "mlc_positions_cm": {"bank_a": [-2.0], "bank_b": [2.0]}},
        {"mlc_positions_cm": {"bank_a": [-2.0], "bank_b": [2.0, 1.0]}},
        {"mlc_positions_cm": {"bank_a": [-2.0, 2.0], "bank_b": [2.0, 1.0]}},
        {"mlc_positions_cm": {"bank_a": [-2.0, -1.0], "bank_b": [2.0, float("inf")]}},
    ],
)
def test_malformed_mlc_geometry_raises_instead_of_downgrading_to_jaw_only(patch):
    geometry = jaw_mlc_geometry()
    geometry.update(patch)

    with pytest.raises(RectangularPhitsRendererError):
        render(geometry)


def test_missing_jaw_aperture_raises():
    geometry = jaw_mlc_geometry(jaw_positions_cm=None)

    with pytest.raises(RectangularPhitsRendererError):
        render(geometry)


def test_material_blocks_emit_only_for_referenced_materials():
    text = render(jaw_mlc_geometry())

    assert "MAT[1] $ shielding" in text
    assert "74W 1" in text
    assert "unused" not in text
    assert "1H 2" not in text


def test_missing_material_block_for_referenced_material_raises():
    geometry = jaw_mlc_geometry()
    geometry["materials"]["shielding"].pop("material_block")

    with pytest.raises(RectangularPhitsRendererError, match="material_block"):
        render(geometry)


@pytest.mark.parametrize("block", ["[ Cell ]\n74W 1", "74W 1\n[ E N D ]"])
def test_material_block_section_injection_raises(block):
    geometry = jaw_mlc_geometry()
    geometry["materials"]["shielding"]["material_block"] = block

    with pytest.raises(RectangularPhitsRendererError, match="section injection"):
        render(geometry)


def test_cell_surface_refs_ids_and_non_void_material_refs_are_validated():
    text = render(jaw_mlc_geometry())
    surface_ids = set()
    cell_ids = set()
    material_ids = set()
    section = None
    for line in text.splitlines():
        if line in ALL_SECTION_HEADERS:
            section = line
            continue
        parts = line.split()
        if not parts:
            continue
        if section == "[ Surface ]" and parts[0].isdigit():
            assert int(parts[0]) not in surface_ids
            surface_ids.add(int(parts[0]))
        elif section == "[ Cell ]" and parts[0].isdigit():
            cell_id = int(parts[0])
            assert cell_id not in cell_ids
            cell_ids.add(cell_id)
            material_id = int(parts[1])
            cell_tokens = parts[: parts.index("$")] if "$" in parts else parts
            refs = [int(part) for part in cell_tokens[3:] if part.lstrip("-").isdigit()]
            assert all(abs(ref) in surface_ids for ref in refs)
            if material_id > 0:
                material_ids.add(material_id)
        elif section == "[ Material ]" and parts[0].startswith("MAT["):
            material_id = int(parts[0].removeprefix("MAT[").removesuffix("]"))
            assert material_id in material_ids

    assert surface_ids
    assert cell_ids
    assert material_ids


def test_base_transport_cell_excludes_exact_generated_shield_cell_complements():
    text = render(jaw_mlc_geometry())
    surface_ids, cells = parsed_surfaces_and_cells(text)

    assert len(cells) == len(set(cells))
    shield_cell_ids = {cell_id for cell_id, cell in cells.items() if cell["material"] > 0}
    base_cells = {cell_id: cell for cell_id, cell in cells.items() if cell["material"] == 0}
    outside_cells = {cell_id: cell for cell_id, cell in cells.items() if cell["material"] == -1}

    assert len(base_cells) == 1
    assert len(outside_cells) == 1
    base_cell_id, base_cell = next(iter(base_cells.items()))
    outside_cell_id, outside_cell = next(iter(outside_cells.items()))

    assert "-9000" in base_cell["expression"]
    assert "9000" in outside_cell["expression"]
    assert base_cell["expression"] != outside_cell["expression"]
    assert base_cell_id not in complement_cell_ids(base_cell["expression"])
    assert outside_cell_id not in complement_cell_ids(base_cell["expression"])
    assert complement_cell_ids(base_cell["expression"]) == shield_cell_ids

    for shield_cell_id in shield_cell_ids:
        shield_refs = surface_ids_in_expression(cells[shield_cell_id]["expression"])
        assert shield_refs
        assert shield_refs <= surface_ids


def test_base_transport_cell_wraps_agility_sized_shield_exclusions():
    leaf_pair_count = 80
    positions = [float(index) for index in range(leaf_pair_count)]
    geometry = jaw_mlc_geometry(
        mlc_positions_cm={
            "bank_a": [-(value + 1.0) for value in positions],
            "bank_b": [value + 1.0 for value in positions],
        },
        mlc_geometry={
            "leaf_pair_count": leaf_pair_count,
            "leaf_widths_cm": [0.5] * leaf_pair_count,
            "leaf_depth_cm": 6.0,
            "upstream_z_cm": -35.0,
            "downstream_z_cm": -30.0,
            "material": "shielding",
        },
    )

    text = render(geometry)
    _surface_ids, cells = parsed_surfaces_and_cells(text)
    shield_cell_ids = {cell_id for cell_id, cell in cells.items() if cell["material"] > 0}
    base_cell_id, base_cell = next((cell_id, cell) for cell_id, cell in cells.items() if cell["material"] == 0)
    base_lines = physical_cell_lines(text, base_cell_id)

    assert len(shield_cell_ids) == 2 + leaf_pair_count * 2
    assert complement_cell_ids(base_cell["expression"]) == shield_cell_ids
    assert len(base_lines) > 1

    for index, line in enumerate(base_lines):
        tokens = line.split()
        cell_tokens = tokens[: tokens.index("$")] if "$" in tokens else tokens
        geometry_tokens = cell_tokens[2:] if index == 0 else cell_tokens
        assert len(geometry_tokens) <= renderer_module.CELL_GEOMETRY_TOKENS_PER_LINE


def test_base_transport_cell_uses_transport_void_not_outside_world_kill_convention():
    text = render(jaw_only_geometry())
    _surface_ids, cells = parsed_surfaces_and_cells(text)

    base_cells = [cell for cell in cells.values() if cell["material"] == 0]
    outside_cells = [cell for cell in cells.values() if cell["material"] == -1]

    assert len(base_cells) == 1
    assert len(outside_cells) == 1
    assert base_cells[0]["raw"][1] == "0"
    assert outside_cells[0]["raw"][1] == "-1"
    assert base_cells[0]["expression"][0] == "-9000"
    assert outside_cells[0]["expression"] == ["9000"]


def test_legacy_minimal_water_sphere_markers_are_absent():
    text = render()

    for marker in LEGACY_PLACEHOLDER_MARKERS:
        assert marker not in text


def test_renderer_imports_do_not_reference_private_scripts_or_workflow_modules():
    source = inspect.getsource(renderer_module)

    forbidden = [
        "scripts.extract",
        "scripts.flatten",
        "scripts.gen_phits",
        "prepare_3dcrt_workspace",
        "phits_segments",
        "run_segments",
        "gui",
    ]
    for marker in forbidden:
        assert marker not in source
