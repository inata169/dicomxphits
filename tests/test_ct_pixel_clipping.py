"""Synthetic source-index and preview tests; no external scientific tools."""

from pathlib import Path
from types import SimpleNamespace
import time
import tkinter as tk

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset

from dicomxphits.ct_pixel_clipping import ClipBounds, ClipError, PlaneTransform, VolumeShape
from dicomxphits.ct_preview import CtPreviewDialog, PreviewError, load_preview


def test_three_plane_corner_mapping_and_display_inverse() -> None:
    shape = VolumeShape(7, 5, 4, 1.25, 2.5, 4.0)
    original = ClipBounds.full(shape)
    axial = original.with_corners("Axial", (6, 4), (2, 2))
    assert axial == ClipBounds(2, 6, 2, 4, 1, 4)
    coronal = axial.with_corners("Coronal", (5, 4), (3, 2))
    assert coronal == ClipBounds(3, 5, 2, 4, 2, 4)
    sagittal = coronal.with_corners("Sagittal", (3, 3), (2, 1))
    assert sagittal == ClipBounds(3, 5, 2, 3, 1, 3)
    for plane in ("Axial", "Coronal", "Sagittal"):
        transform = PlaneTransform(plane, shape, 317, 191)
        left, top, width, height = transform.frame
        assert transform.canvas_to_source(left - 0.01, top) is None
        assert transform.canvas_to_source(left + width, top) is None
        count_x, count_y, *_ = transform.axes
        assert transform.canvas_to_source(left, top) == (
            1, count_y if plane != "Axial" else 1
        )
        assert transform.canvas_to_source(left + width - 0.001, top + height - 0.001) == (
            count_x, 1 if plane != "Axial" else count_y
        )
        x0, y0, x1, y1 = transform.source_rectangle(sagittal)
        assert transform.canvas_to_source((x0 + x1) / 2, (y0 + y1) / 2) is not None
    assert not sagittal.contains_plane("Coronal", 5)
    assert sagittal.contains_plane("Coronal", 3)


@pytest.mark.parametrize("values", [
    ("0", "7", "1", "5", "1", "4"),
    ("2", "1", "1", "5", "1", "4"),
    ("1.5", "7", "1", "5", "1", "4"),
    ("1", "7", "1", "5", "2", "1"),
    ("1", "7", "1", "5", "1", "5"),
])
def test_invalid_numeric_bounds_are_rejected(values: tuple[str, ...]) -> None:
    with pytest.raises(ClipError):
        ClipBounds.parse(values, VolumeShape(7, 5, 4, 1, 1, 2))


def _pixel_series(root: Path, *, count: int = 3) -> None:
    root.mkdir()
    uid = pydicom.uid.generate_uid()
    frame = pydicom.uid.generate_uid()
    for z in reversed(range(count)):
        path = root / f"CT.{count-z}.dcm"
        meta = Dataset()
        meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
        meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
        ds.SOPClassUID = meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.Modality = "CT"
        ds.SeriesInstanceUID = uid
        ds.FrameOfReferenceUID = frame
        ds.PatientPosition = "HFS"
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [12.0, -17.0, -8.0 + 3.0 * z]
        ds.PixelSpacing = [2.0, 1.0]
        ds.Rows = 5
        ds.Columns = 7
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1
        ds.RescaleSlope = z + 1
        ds.RescaleIntercept = -100 * z
        pixels = (z * 100 + np.arange(35).reshape(5, 7)).astype("<i2")
        ds.PixelData = pixels.tobytes()
        ds.save_as(str(path))


def test_synthetic_pixels_are_sorted_and_rescaled_per_slice(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    _pixel_series(root)
    progress = []
    volume = load_preview(root, None, progress=lambda done, total: progress.append((done, total)))
    assert progress == [(1, 3), (2, 3), (3, 3)]
    assert volume.shape == VolumeShape(7, 5, 3, 1.0, 2.0, 3.0)
    assert volume.pixels[0, 2, 3] == 17
    assert volume.pixels[2, 2, 3] == 217
    assert volume.plane("Axial", 2)[2, 3] == 117 * 2 - 100
    assert volume.plane("Coronal", 3)[0, 3] == 217 * 3 - 200
    assert volume.plane("Sagittal", 4)[2, 2] == 17
    assert volume.still_current()
    first = next(root.iterdir())
    first.write_bytes(first.read_bytes() + b"changed")
    assert not volume.still_current()


def test_single_slice_and_bounded_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "ct"
    _pixel_series(root, count=1)
    volume = load_preview(root, None)
    assert volume.shape.z_mm is None
    with pytest.raises(ClipError, match="unavailable"):
        PlaneTransform("Coronal", volume.shape, 200, 200).axes
    with pytest.raises(PreviewError, match="cancelled"):
        load_preview(root, None, cancelled=lambda: True)
    monkeypatch.setattr("dicomxphits.ct_preview.PREVIEW_MEMORY_LIMIT", 1)
    with pytest.raises(PreviewError, match="128 MiB"):
        load_preview(root, None)


def test_synthetic_tk_corner_selection_and_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root_path = tmp_path / "ct"
    _pixel_series(root_path)
    volume = load_preview(root_path, None)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    monkeypatch.setattr("dicomxphits.ct_preview.load_preview", lambda *_args, **_kwargs: volume)
    applied = []
    try:
        dialog = CtPreviewDialog(root, root_path, None, None,
                                 lambda _volume, bounds: applied.append(bounds))
        for _ in range(100):
            root.update()
            if dialog.volume is not None:
                break
            time.sleep(0.01)
        assert dialog.volume is volume
        canvas = dialog.canvases["Axial"]
        transform = PlaneTransform("Axial", volume.shape,
                                   canvas.winfo_width(), canvas.winfo_height())
        def event_for(x: int, y: int) -> SimpleNamespace:
            left, top, width, height = transform.frame
            return SimpleNamespace(x=left + (x - 0.5) * width / volume.shape.columns,
                                   y=top + (y - 0.5) * height / volume.shape.rows)
        dialog._click("Axial", event_for(6, 4))
        dialog._click("Axial", event_for(2, 2))
        assert tuple(field.get() for field in dialog.fields) == ("2", "6", "2", "4", "1", "3")
        dialog._reset()
        assert tuple(field.get() for field in dialog.fields) == ("1", "7", "1", "5", "1", "3")
        dialog._click("Axial", event_for(6, 4))
        dialog._click("Axial", event_for(2, 2))
        dialog._set_crosshair("Axial", event_for(7, 5))
        dialog.nav["Coronal"].set(5)
        dialog._navigate("Coronal")
        dialog.center.set(30)
        dialog._draw_all()
        assert dialog.crosshair is not None
        assert tuple(field.get() for field in dialog.fields) == ("2", "6", "2", "4", "1", "3")
        dialog._apply()
        assert applied == [ClipBounds(2, 6, 2, 4, 1, 3)]
    finally:
        root.destroy()
