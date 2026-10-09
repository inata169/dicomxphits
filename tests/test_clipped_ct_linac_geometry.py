"""Synthetic placement and accelerator-invariance checks; no external tool run.

The raw crop parameters model the separately observed CT2PHITS contract.
They do not validate the external program's surface generation or transport.
"""
from pathlib import Path
import re

import numpy as np
import pytest

from dicomxphits.ct2phits_datfiles import RAW_CT2PHITS_NAMES, prepare_ct2phits_assets
from dicomxphits.prepare_3dcrt_workspace import generate_rectangular_phits_workspace
from test_run_ct2phits import _uid, _write_ct_series, _write_rtplan
from test_prepare_3dcrt_workspace import manifest_with, rectangular_segment


def prepared_case(root: Path, bounds: tuple[int, ...], factors: tuple[int, ...]):
    root.mkdir()
    frame = _uid()
    paths = _write_ct_series(
        root / "CT", frame_uid=frame, series_uid=_uid(), rows=24, columns=32,
        pixel_spacing_mm=(2, 2), z_positions_mm=tuple(-100 + 3 * i for i in range(6)),
    )
    plan = _write_rtplan(root / "RTPLAN.dcm", frame_uid=frame)
    raw = root / "DATfiles"
    raw.mkdir()
    x0, x1, y0, y1, z0, z1 = bounds
    counts = tuple(n // f for n, f in zip((x1-x0+1, y1-y0+1, z1-z0+1), factors))
    pitch = np.array((0.2, 0.2, 0.3))
    params = dict(zip(range(81, 84), counts))
    params.update(zip(range(84, 87), pitch * factors))
    params.update(zip(range(87, 90), ((x0-1.5)*pitch[0], (y0-1.5)*pitch[1], -pitch[2]/2)))
    params.update(zip(range(91, 94), (-12, -8, (-100+3*(z0-1))/10)))
    for name in RAW_CT2PHITS_NAMES:
        text = ("".join(f"set: c{k}[{int(v) if k < 84 else f'{v:.5f}'}]\n" for k, v in params.items())
                if name == "CTusrparam.dat" else f"$ synthetic placeholder: {name}\n")
        (raw / name).write_text(text, encoding="utf8")
    prepared = prepare_ct2phits_assets(
        raw_datfiles_root=raw, ct_reference_dicom=paths[0], rtplan_path=plan,
        output_root=root / "prepared", confirmed_non_patient_phantom=True,
        placement_reference_dicom=paths[z0-1],
    )
    return prepared


@pytest.mark.parametrize("factors", [(8, 8, 2), (8, 8, 1)])
@pytest.mark.parametrize("bounds", [
    (1, 32, 1, 24, 1, 6), (9, 24, 5, 20, 1, 6),
    (1, 32, 1, 24, 3, 6), (4, 20, 4, 20, 2, 6),
])
def test_retained_voxel_centres_stay_at_dicom_position_relative_to_isocenter(
    tmp_path, bounds, factors,
):
    prepared = prepared_case(tmp_path / "case", bounds, factors)
    text = (prepared.assets.root / "CTusrparam.dat").read_text()
    params = {int(k): float(v) for k, v in re.findall(r"c(\d+)\[([^]]+)\]", text)}
    transform = (prepared.assets.root / "CTtrans.inp").read_text().splitlines()
    matrix_start = next(i for i, line in enumerate(transform) if line.startswith("tr500")) + 1
    matrix = np.array([[float(v) for v in line.split()] for line in transform[matrix_start:matrix_start+3]])
    shift = np.array([params[k] for k in (91, 92, 93)])
    starts = np.array([bounds[0], bounds[2], bounds[4]])
    source_pitch = np.array([0.2, 0.2, 0.3])
    for index in np.ndindex(prepared.assets.voxel_counts):
        local = np.array([params[k] for k in (87, 88, 89)]) + (np.array(index)+0.5)*np.array([params[k] for k in (84, 85, 86)])
        actual = matrix @ local + shift
        # Independent source DICOM coordinates of the averaged block's centre.
        source_index = starts - 1 + np.array(index)*factors + (np.array(factors)-1)/2
        dicom = np.array([-12, -8, -10]) + source_index*source_pitch
        delta = dicom - np.array([1, 2, 3])  # synthetic RT Plan isocentre, cm
        expected = np.array([-delta[0], delta[2], delta[1]])
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)


@pytest.mark.parametrize("gantry", [0, 90, 180, 270])
@pytest.mark.parametrize("collimator", [0, 37])
def test_clipping_changes_only_lattice_counts_in_generated_linac_input(tmp_path, gantry, collimator):
    inputs = []
    for name, bounds in [("full", (1, 32, 1, 24, 1, 6)), ("crop", (9, 24, 5, 20, 3, 6))]:
        prepared = prepared_case(tmp_path / name, bounds, (8, 8, 2))
        manifest = manifest_with(rectangular_segment(
            gantry_angle_deg=gantry, collimator_angle_deg=collimator,
            resolved_mlc_positions_mm={"bank_a": [-20.0]*80, "bank_b": [20.0]*80},
        ))
        workspace = tmp_path / f"workspace_{name}"
        result = generate_rectangular_phits_workspace(
            manifest=manifest, case_root=workspace, machine_config_path=None,
            ct_asset_root=prepared.assets.root, ct_preparation=prepared,
            confirmed_non_patient_phantom=True,
        )
        text = (workspace / result["generated_phits_inputs"][0]).read_text()
        assert "1201 0 -98 #2 fill=4000" in text
        assert "1200 2 -1.20e-3 -999 #1201 #2" in text
        assert len(re.findall(r"fill=0:\d+ 0:\d+ 0:\d+", text)) == 1
        inputs.append(re.sub(r"fill=0:\d+ 0:\d+ 0:\d+", "<CT lattice counts>", text))
    # Includes source, head surfaces/cells, rotation, materials, dose factor and tally.
    assert inputs[0] == inputs[1]
