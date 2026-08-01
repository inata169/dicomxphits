from __future__ import annotations

import hashlib
import math
import re
import shutil
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

import pydicom

from dicomxphits.prepare_ct_calibration import CtAssetSet, validate_ct_assets


RAW_CT2PHITS_NAMES = (
    "CTusrparam.dat",
    "CTcell.dat",
    "CTmaterial.dat",
    "CTuniverse.dat",
    "CTsurf.dat",
    "CTmatnamecolor.dat",
    "CTvoxel.dat",
    "phantominfo.dat",
)

_AXIAL_HFS_ORIENTATION = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
_ORIENTATION_TOLERANCE = 1.0e-6
_ISOCENTER_TOLERANCE_MM = 1.0e-4
_PARAMETER_PATTERN = re.compile(
    r"^(?P<prefix>\s*set:\s*c(?P<number>91|92|93)\[\s*)"
    r"(?P<value>[^\]]+)"
    r"(?P<suffix>\s*\].*)$",
    re.IGNORECASE,
)


class Ct2PhitsDatfilesError(ValueError):
    """Raised when raw CT2PHITS output cannot be prepared safely."""


@dataclass(frozen=True)
class RawCt2PhitsSet:
    root: Path
    files: Mapping[str, Path]
    sha256: Mapping[str, str]


@dataclass(frozen=True)
class PreparedCt2PhitsSet:
    assets: CtAssetSet
    raw_sha256: Mapping[str, str]
    ct_origin_dicom_cm: tuple[float, float, float]
    rtplan_isocenter_dicom_cm: tuple[float, float, float]
    ct_shift_iec_cm: tuple[float, float, float]
    frame_of_reference_uid: str
    ct_series_instance_uid: str
    ct_slice_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_raw_ct2phits_datfiles(
    root: Path,
    *,
    confirmed_non_patient_phantom: bool,
) -> RawCt2PhitsSet:
    if not confirmed_non_patient_phantom:
        raise Ct2PhitsDatfilesError(
            "raw CT2PHITS preparation requires explicit confirmation that "
            "the source is non-patient phantom data"
        )
    resolved = root.resolve()
    if not resolved.is_dir():
        raise Ct2PhitsDatfilesError(
            f"CT2PHITS DATfiles directory does not exist: {root}"
        )
    files: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for name in RAW_CT2PHITS_NAMES:
        path = resolved / name
        if not path.is_file():
            raise Ct2PhitsDatfilesError(
                f"required raw CT2PHITS DATfiles asset is missing: {name}"
            )
        if path.is_symlink():
            raise Ct2PhitsDatfilesError(
                f"raw CT2PHITS DATfiles assets must not be symbolic links: {name}"
            )
        if path.stat().st_size <= 0:
            raise Ct2PhitsDatfilesError(
                f"required raw CT2PHITS DATfiles asset is empty: {name}"
            )
        files[name] = path
        hashes[name] = _sha256(path)
    return RawCt2PhitsSet(root=resolved, files=files, sha256=hashes)


def _finite_vector(value: Any, *, length: int, label: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise Ct2PhitsDatfilesError(
            f"{label} must contain {length} numeric values"
        ) from exc
    if len(values) != length or not all(math.isfinite(item) for item in values):
        raise Ct2PhitsDatfilesError(
            f"{label} must contain {length} finite numeric values"
        )
    return values


def _require_axial_hfs_ct(dataset: Any, *, path: Path) -> None:
    if str(getattr(dataset, "Modality", "") or "") != "CT":
        raise Ct2PhitsDatfilesError(f"CT reference DICOM Modality must be CT: {path}")
    patient_position = str(getattr(dataset, "PatientPosition", "") or "")
    if patient_position != "HFS":
        raise Ct2PhitsDatfilesError(
            f"CT reference DICOM PatientPosition must be HFS; got "
            f"{patient_position or '<missing>'}"
        )
    orientation = _finite_vector(
        getattr(dataset, "ImageOrientationPatient", None),
        length=6,
        label="CT ImageOrientationPatient",
    )
    if any(
        abs(actual - expected) > _ORIENTATION_TOLERANCE
        for actual, expected in zip(orientation, _AXIAL_HFS_ORIENTATION)
    ):
        raise Ct2PhitsDatfilesError(
            "CT reference DICOM must use the supported axial HFS orientation"
        )


def _ct_series_origin(
    ct_reference_dicom: Path,
) -> tuple[tuple[float, float, float], str, str, int]:
    reference_path = ct_reference_dicom.resolve()
    if not reference_path.is_file():
        raise Ct2PhitsDatfilesError(
            f"CT reference DICOM does not exist: {ct_reference_dicom}"
        )
    reference = pydicom.dcmread(
        str(reference_path),
        stop_before_pixels=True,
        force=True,
    )
    _require_axial_hfs_ct(reference, path=reference_path)
    frame_uid = str(getattr(reference, "FrameOfReferenceUID", "") or "")
    series_uid = str(getattr(reference, "SeriesInstanceUID", "") or "")
    if not frame_uid:
        raise Ct2PhitsDatfilesError(
            "CT reference DICOM is missing FrameOfReferenceUID"
        )
    if not series_uid:
        raise Ct2PhitsDatfilesError(
            "CT reference DICOM is missing SeriesInstanceUID"
        )

    positions: list[tuple[float, float, float]] = []
    for candidate in sorted(reference_path.parent.iterdir()):
        if not candidate.is_file():
            continue
        try:
            dataset = pydicom.dcmread(
                str(candidate),
                stop_before_pixels=True,
                force=True,
                specific_tags=[
                    "Modality",
                    "PatientPosition",
                    "ImageOrientationPatient",
                    "ImagePositionPatient",
                    "FrameOfReferenceUID",
                    "SeriesInstanceUID",
                ],
            )
        except Exception:
            continue
        if str(getattr(dataset, "Modality", "") or "") != "CT":
            continue
        if str(getattr(dataset, "SeriesInstanceUID", "") or "") != series_uid:
            continue
        _require_axial_hfs_ct(dataset, path=candidate)
        if str(getattr(dataset, "FrameOfReferenceUID", "") or "") != frame_uid:
            raise Ct2PhitsDatfilesError(
                "CT series contains inconsistent FrameOfReferenceUID values"
            )
        positions.append(
            _finite_vector(
                getattr(dataset, "ImagePositionPatient", None),
                length=3,
                label="CT ImagePositionPatient",
            )
        )
    if not positions:
        raise Ct2PhitsDatfilesError(
            "no CT slices matching the reference SeriesInstanceUID were found"
        )
    origin_mm = min(positions, key=lambda position: position[2])
    origin_cm = tuple(value / 10.0 for value in origin_mm)
    return origin_cm, frame_uid, series_uid, len(positions)


def _rtplan_frame_uids(dataset: Any) -> set[str]:
    values: set[str] = set()
    direct = str(getattr(dataset, "FrameOfReferenceUID", "") or "")
    if direct:
        values.add(direct)
    for item in getattr(dataset, "ReferencedFrameOfReferenceSequence", []) or []:
        value = str(getattr(item, "FrameOfReferenceUID", "") or "")
        if value:
            values.add(value)
    return values


def _require_integral_beam_number(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise Ct2PhitsDatfilesError(f"{label} must be an integer")
    try:
        numeric = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise Ct2PhitsDatfilesError(f"{label} must be an integer") from exc
    if not numeric.is_finite() or numeric != numeric.to_integral_value():
        raise Ct2PhitsDatfilesError(f"{label} must be an integer")
    return int(numeric)


def _referenced_beam_numbers(dataset: Any) -> set[int]:
    numbers: set[int] = set()
    for group in getattr(dataset, "FractionGroupSequence", []) or []:
        for item in getattr(group, "ReferencedBeamSequence", []) or []:
            value = getattr(item, "ReferencedBeamNumber", None)
            numbers.add(
                _require_integral_beam_number(
                    value,
                    label="RTPLAN ReferencedBeamNumber",
                )
            )
    return numbers


def _beam_isocenter_mm(beam: Any) -> tuple[float, float, float]:
    beam_number = getattr(beam, "BeamNumber", "<unknown>")
    values: list[tuple[float, float, float]] = []
    for control_point in getattr(beam, "ControlPointSequence", []) or []:
        raw = getattr(control_point, "IsocenterPosition", None)
        if raw is not None:
            values.append(
                _finite_vector(
                    raw,
                    length=3,
                    label=f"beam {beam_number} IsocenterPosition",
                )
            )
    if not values:
        raise Ct2PhitsDatfilesError(
            f"referenced beam {beam_number} is missing IsocenterPosition"
        )
    first = values[0]
    for value in values[1:]:
        if any(
            abs(actual - expected) > _ISOCENTER_TOLERANCE_MM
            for actual, expected in zip(value, first)
        ):
            raise Ct2PhitsDatfilesError(
                f"beam {beam_number} contains inconsistent IsocenterPosition values"
            )
    return first


def _rtplan_isocenter(
    rtplan_path: Path,
    *,
    expected_frame_uid: str,
) -> tuple[float, float, float]:
    resolved = rtplan_path.resolve()
    if not resolved.is_file():
        raise Ct2PhitsDatfilesError(f"RTPLAN DICOM does not exist: {rtplan_path}")
    dataset = pydicom.dcmread(str(resolved), stop_before_pixels=True, force=True)
    if str(getattr(dataset, "Modality", "") or "") != "RTPLAN":
        raise Ct2PhitsDatfilesError("RTPLAN input Modality must be RTPLAN")
    frame_uids = _rtplan_frame_uids(dataset)
    if frame_uids != {expected_frame_uid}:
        raise Ct2PhitsDatfilesError(
            "RTPLAN and CT reference FrameOfReferenceUID do not match"
        )

    referenced = _referenced_beam_numbers(dataset)
    beams = list(getattr(dataset, "BeamSequence", []) or [])
    numbered_beams: list[tuple[int, Any]] = []
    for beam in beams:
        beam_number = _require_integral_beam_number(
            getattr(beam, "BeamNumber", None),
            label="RTPLAN BeamNumber",
        )
        numbered_beams.append((beam_number, beam))
    selected = [
        beam
        for beam_number, beam in numbered_beams
        if not referenced or beam_number in referenced
    ]
    if not selected:
        raise Ct2PhitsDatfilesError("RTPLAN has no referenced treatment beams")
    isocenters = [_beam_isocenter_mm(beam) for beam in selected]
    first = isocenters[0]
    for value in isocenters[1:]:
        if any(
            abs(actual - expected) > _ISOCENTER_TOLERANCE_MM
            for actual, expected in zip(value, first)
        ):
            raise Ct2PhitsDatfilesError(
                "referenced RTPLAN beams do not share one IsocenterPosition"
            )
    return tuple(value / 10.0 for value in first)


def _iec_shift(
    ct_origin_dicom_cm: Sequence[float],
    rtplan_isocenter_dicom_cm: Sequence[float],
) -> tuple[float, float, float]:
    dicom_shift = tuple(
        origin - isocenter
        for origin, isocenter in zip(
            ct_origin_dicom_cm,
            rtplan_isocenter_dicom_cm,
        )
    )
    return (-dicom_shift[0], dicom_shift[2], dicom_shift[1])


def _updated_ctusrparam(
    source: Path,
    *,
    shift_iec_cm: Sequence[float],
) -> str:
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    replacements = {91: shift_iec_cm[0], 92: shift_iec_cm[1], 93: shift_iec_cm[2]}
    counts = {91: 0, 92: 0, 93: 0}
    output: list[str] = []
    for line in lines:
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        if body.endswith("\r"):
            body = body[:-1]
        match = _PARAMETER_PATTERN.match(body)
        if match is None:
            output.append(body + newline)
            continue
        number = int(match.group("number"))
        counts[number] += 1
        output.append(
            f"{match.group('prefix')}{replacements[number]:.5f}"
            f"{match.group('suffix')}{newline}"
        )
    invalid = [f"c{number}={count}" for number, count in counts.items() if count != 1]
    if invalid:
        raise Ct2PhitsDatfilesError(
            "CTusrparam.dat must define c91, c92, and c93 exactly once; got "
            + ", ".join(invalid)
        )
    return "".join(output)


def _cttrans_text() -> str:
    return (
        "$ Transform system according to DICOM header\n"
        "$ DICOM HFS -> IEC 61217 Fixed coordinate transformation\n"
        "tr500 c91 c92 c93\n"
        "       -1.00000   0.00000   0.00000\n"
        "        0.00000   0.00000   1.00000\n"
        "        0.00000   1.00000   0.00000\n"
        "     1\n"
    )


def prepare_ct2phits_assets(
    *,
    raw_datfiles_root: Path,
    ct_reference_dicom: Path,
    rtplan_path: Path,
    output_root: Path,
    confirmed_non_patient_phantom: bool,
) -> PreparedCt2PhitsSet:
    raw = validate_raw_ct2phits_datfiles(
        raw_datfiles_root,
        confirmed_non_patient_phantom=confirmed_non_patient_phantom,
    )
    ct_origin, frame_uid, series_uid, slice_count = _ct_series_origin(
        ct_reference_dicom
    )
    isocenter = _rtplan_isocenter(
        rtplan_path,
        expected_frame_uid=frame_uid,
    )
    shift = _iec_shift(ct_origin, isocenter)

    output = output_root.resolve()
    if output.exists():
        raise Ct2PhitsDatfilesError(
            f"prepared CT asset output already exists: {output}"
        )
    output.mkdir(parents=True)
    (output / "CTusrparam.dat").write_text(
        _updated_ctusrparam(raw.files["CTusrparam.dat"], shift_iec_cm=shift),
        encoding="utf-8",
        newline="\n",
    )
    (output / "CTtrans.inp").write_text(
        _cttrans_text(),
        encoding="utf-8",
        newline="\n",
    )
    shutil.copyfile(raw.files["CTsurf.dat"], output / "CTsurf.dat")
    shutil.copyfile(raw.files["CTmaterial.dat"], output / "CTmaterial.dat")
    shutil.copyfile(raw.files["CTuniverse.dat"], output / "CTuniverse.inp")
    shutil.copyfile(raw.files["CTvoxel.dat"], output / "CTvoxel.inp")

    assets = validate_ct_assets(
        output,
        confirmed_non_patient_phantom=True,
    )
    return PreparedCt2PhitsSet(
        assets=assets,
        raw_sha256=raw.sha256,
        ct_origin_dicom_cm=ct_origin,
        rtplan_isocenter_dicom_cm=isocenter,
        ct_shift_iec_cm=shift,
        frame_of_reference_uid=frame_uid,
        ct_series_instance_uid=series_uid,
        ct_slice_count=slice_count,
    )
