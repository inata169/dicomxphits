from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from dicomxphits.prepare_ct_calibration import (
    CtCalibrationError,
    MIN_ACCEPTED_HISTORIES,
    parse_batch_allocation,
    prepare_ct_calibration_packages,
)
from dicomxphits.public_spectrum import (
    PUBLIC_SPECTRUM_NAME,
    PUBLIC_SPECTRUM_SHA256,
)


def write_ct_assets(root: Path) -> Path:
    root.mkdir()
    (root / "CTusrparam.dat").write_text(
        "\n".join(
            [
                "set: c81[ 4]",
                "set: c82[ 3]",
                "set: c83[ 2]",
                "set: c84[ 0.1]",
                "set: c85[ 0.1]",
                "set: c86[ 0.5]",
                "set: c87[-0.05]",
                "set: c88[-0.05]",
                "set: c89[-0.25]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "CTtrans.inp").write_text(
        "tr500 0 0 0\n -1 0 0\n 0 0 1\n 0 1 0\n 1\n",
        encoding="utf-8",
    )
    (root / "CTsurf.dat").write_text(
        "5000 rpp -0.05 0.05 -0.05 0.05 -0.25 0.25\n"
        "99 so 500\n"
        "97 rpp -0.05 0.35 -0.05 0.25 -0.25 0.75\n"
        "98 500 rpp -0.049 0.349 -0.049 0.249 -0.249 0.749\n",
        encoding="utf-8",
    )
    (root / "CTmaterial.dat").write_text(
        "MAT[5001]\n 1H -11.2\n 16O -88.8\n",
        encoding="utf-8",
    )
    (root / "CTuniverse.inp").write_text(
        "5001 5001 -1.0 -99 u=5001\n",
        encoding="utf-8",
    )
    (root / "CTvoxel.inp").write_text(
        "5001 24\n",
        encoding="utf-8",
    )
    return root


def test_batch_allocation_accepts_one_or_three_pc_minimum() -> None:
    assert parse_batch_allocation("64,0,0") == (64, 0, 0)
    assert parse_batch_allocation("64,64,64") == (64, 64, 64)

    with pytest.raises(CtCalibrationError, match="total at least 64"):
        parse_batch_allocation("21,21,21")


def test_default_packages_use_64_batches_on_each_pc(tmp_path: Path) -> None:
    ct_root = write_ct_assets(tmp_path / "ct_assets")
    output_root = tmp_path / "packages"

    manifest = prepare_ct_calibration_packages(
        ct_asset_root=ct_root,
        output_root=output_root,
        confirmed_non_patient_phantom=True,
    )

    history = manifest["history_requirement"]
    assert history["configured_batch_allocation"] == {
        "pc_a": 64,
        "pc_b": 64,
        "pc_c": 64,
    }
    assert history["configured_total_batches"] == 192
    assert history["configured_total_histories"] == 3_840_000_000
    assert history["minimum_accepted_histories"] == MIN_ACCEPTED_HISTORIES
    assert history["pc_count_is_release_criterion"] is False
    assert manifest["field_order"] == ["10x10", "3x3", "5x5", "20x20"]
    assert manifest["publication_gate"]["blocking_field"] == "10x10"
    assert manifest["publication_gate"]["non_blocking_follow_up_fields"] == [
        "3x3",
        "5x5",
        "20x20",
    ]

    input_a = (
        output_root / "field_10x10" / "pc_a" / "public_ct_10x10.inp"
    ).read_text(encoding="utf-8")
    input_b = (
        output_root / "field_10x10" / "pc_b" / "public_ct_10x10.inp"
    ).read_text(encoding="utf-8")
    input_c = (
        output_root / "field_10x10" / "pc_c" / "public_ct_10x10.inp"
    ).read_text(encoding="utf-8")

    assert "$OMP = 8" in input_a
    assert "maxcas = 20000000" in input_a
    assert "maxbch = 64" in input_a
    assert "irskip = -1000" in input_a
    assert "irskip = -2000" in input_b
    assert "irskip = -3000" in input_c
    assert "istdev = -1" in input_a
    assert "infl:{libpath.inp}" in input_a
    assert "infl:{CTusrparam.dat}" in input_a
    assert "infl:{CTsurf.dat}" in input_a
    assert "infl:{CTmaterial.dat}" in input_a
    assert "infl:{CTtrans.inp}" in input_a
    assert "infl:{CTuniverse.inp}" in input_a
    assert "infl:{CTvoxel.inp}" in input_a
    assert "fill=0:3 0:2 0:1" in input_a
    assert "ct_chassis = gui_validated_ct2phits_air_universe" in input_a
    assert "1200 2 -1.20e-3 -999 #1201 #2" in input_a
    assert "1201 0 -98 #2 fill=4000" in input_a
    assert "998 0 97 trcl=500 u=4000" in input_a
    assert "997 0 -97 trcl=500 fill=5000 u=4000" in input_a
    assert "901 0 -901 fill=1 trcl=2 u=2" in input_a
    assert "900 2 -1.20e-3 -999 #901 u=2" in input_a
    assert "1000 2 -1.20e-3 -999 #3101 #3102" in input_a
    assert "3101 1 -11.34 -1101 u=1" in input_a
    assert "4101 1 -11.34 -2001 u=1" in input_a
    assert "3001 0 -9000" not in input_a
    assert "nx = 101" in input_a
    assert "ny = 101" in input_a
    assert input_a.count("nz = 101") == 2
    assert "xmin = -15.15" in input_a
    assert "xmax = 15.15" in input_a
    assert "zmin = -10.15" in input_a
    assert "zmax = 20.15" in input_a
    assert "file = deposit-target-3D.out" in input_a
    assert "file = deposit-pdd.out" in input_a
    assert "unit = 0" in input_a
    assert "totfact" not in input_a
    assert "Public rectangular 3D-CRT PHITS input" not in input_a
    assert "scoring placeholder" not in input_a
    assert "x0 = -0.15" in input_a
    assert "x1 = 0.15" in input_a
    assert "y0 = -0.15" in input_a
    assert "y1 = 0.15" in input_a
    assert "11 pz -60.07001" in input_a
    assert "12 pz -41.19999" in input_a
    assert "1101 rpp -15 15 -15 -2.855 -48.9 -41.2" in input_a
    assert "author_tuned_tungsten_alloy" in input_a
    assert "-11.34" in input_a
    assert "184W -90.5" in input_a
    assert "surfacex_1.inp" not in input_a
    assert "surfacey.inp" not in input_a
    assert "surfacez.inp" not in input_a
    assert "cell.inp" not in input_a

    spectrum_path = output_root / "field_10x10" / "pc_a" / PUBLIC_SPECTRUM_NAME
    assert hashlib.sha256(spectrum_path.read_bytes()).hexdigest() == PUBLIC_SPECTRUM_SHA256

    run_bat = (output_root / "field_10x10" / "pc_a" / "run_this_pc.bat").read_text(
        encoding="utf-8"
    )
    assert "if not defined PHITS_ROOT" in run_bat
    assert "if not defined PHITS_EXE" in run_bat
    assert 'if not exist "%PHITS_ROOT%\\."' in run_bat
    assert 'if not exist "%PHITS_EXE%"' in run_bat
    assert 'set "PHITS_ROOT_PHITS=%PHITS_ROOT:\\=/%"' in run_bat
    assert '> "libpath.inp.tmp" echo file(1) = %PHITS_ROOT_PHITS%' in run_bat
    assert 'move /y "libpath.inp.tmp" "libpath.inp" >nul' in run_bat
    assert "deposit-target-3D.out" in run_bat
    assert "deposit-pdd.out" in run_bat
    assert "run_complete.txt" in run_bat
    assert '^<' not in run_bat
    assert '"%PHITS_EXE%" < "public_ct_10x10.inp" > "run_console.log" 2>&1' in run_bat

    sumtally = (
        output_root / "field_10x10" / "sumtally" / "sumtally_3d_all_files.inp"
    ).read_text(encoding="utf-8")
    assert "isumtally = 2" in sumtally
    assert "nfile = 3" in sumtally
    assert "../pc_a/deposit-target-3D.out  1280000000" in sumtally
    assert "../pc_b/deposit-target-3D.out  1280000000" in sumtally
    assert "../pc_c/deposit-target-3D.out  1280000000" in sumtally
    assert (
        output_root / "field_10x10" / "sumtally" / "run_sumtally_pc_a.bat"
    ).is_file()
    sumtally_bat = (
        output_root / "field_10x10" / "sumtally" / "run_sumtally_pc_a.bat"
    ).read_text(encoding="utf-8")
    assert "if not defined PHITS_ROOT" in sumtally_bat
    assert "if not defined PHITS_EXE" in sumtally_bat
    assert 'move /y "libpath.inp.tmp" "libpath.inp" >nul' in sumtally_bat
    pc_a_sumtally = (
        output_root / "field_10x10" / "sumtally" / "sumtally_3d_pc_a_files.inp"
    ).read_text(encoding="utf-8")
    assert "nfile = 1" in pc_a_sumtally
    assert "../pc_a/deposit-target-3D.out  1280000000" in pc_a_sumtally

    saved = json.loads(
        (output_root / "calibration_manifest.json").read_text(encoding="utf-8")
    )
    assert saved == manifest
    assert saved["phantom"]["source_path_recorded"] is False
    assert saved["phantom"]["chassis"] == "gui_validated_ct2phits_air_universe"
    assert saved["phantom"]["transform_asset"] == "CTtrans.inp"
    assert saved["phantom"]["material_assignment"] == "ct2phits_preserved"
    assert saved["phits_execution_performed"] is False


def test_one_pc_allocation_is_sufficient_and_omits_unused_replicas(
    tmp_path: Path,
) -> None:
    ct_root = write_ct_assets(tmp_path / "ct_assets")
    output_root = tmp_path / "packages"

    manifest = prepare_ct_calibration_packages(
        ct_asset_root=ct_root,
        output_root=output_root,
        batch_allocation="64,0,0",
        confirmed_non_patient_phantom=True,
    )

    assert manifest["history_requirement"]["configured_total_histories"] == MIN_ACCEPTED_HISTORIES
    assert (output_root / "field_10x10" / "pc_a").is_dir()
    assert not (output_root / "field_10x10" / "pc_b").exists()
    assert not (output_root / "field_10x10" / "pc_c").exists()
    sumtally = (
        output_root / "field_10x10" / "sumtally" / "sumtally_3d_all_files.inp"
    ).read_text(encoding="utf-8")
    assert "nfile = 1" in sumtally
    assert "../pc_a/deposit-target-3D.out  1280000000" in sumtally


def test_preparation_requires_non_patient_confirmation(tmp_path: Path) -> None:
    ct_root = write_ct_assets(tmp_path / "ct_assets")
    output_root = tmp_path / "packages"

    with pytest.raises(CtCalibrationError, match="non-patient phantom"):
        prepare_ct_calibration_packages(
            ct_asset_root=ct_root,
            output_root=output_root,
        )

    assert not output_root.exists()


def test_preparation_refuses_existing_output_root(tmp_path: Path) -> None:
    ct_root = write_ct_assets(tmp_path / "ct_assets")
    output_root = tmp_path / "packages"
    output_root.mkdir()

    with pytest.raises(CtCalibrationError, match="refusing to overwrite"):
        prepare_ct_calibration_packages(
            ct_asset_root=ct_root,
            output_root=output_root,
            confirmed_non_patient_phantom=True,
        )


def test_preparation_requires_gui_validated_ct_transform(tmp_path: Path) -> None:
    ct_root = write_ct_assets(tmp_path / "ct_assets")
    (ct_root / "CTtrans.inp").rename(ct_root / "CTtrans.dat")

    with pytest.raises(CtCalibrationError, match="CTtrans.inp"):
        prepare_ct_calibration_packages(
            ct_asset_root=ct_root,
            output_root=tmp_path / "packages",
            confirmed_non_patient_phantom=True,
        )
