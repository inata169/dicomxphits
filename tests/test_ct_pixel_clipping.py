"""Synthetic source-index and preview tests; no external scientific tools."""

from pathlib import Path
from types import SimpleNamespace
import time
import tkinter as tk

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset

from dicomxphits.ct_pixel_clipping import ClipBounds, ClipError, PlaneTransform, VolumeShape, coarse_coverage
from dicomxphits.ct_preview import CtPreviewDialog, PreviewError, _preview_stride, load_preview
from dicomxphits.run_ct2phits import SelectedCtSeries


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


def test_coarse_coverage_reports_exact_high_end_loss() -> None:
    coverage = coarse_coverage(ClipBounds(9, 25, 5, 21, 2, 6), (8, 8, 2))
    assert coverage.voxel_counts == (2, 2, 2)
    assert coverage.discarded_high == (1, 1, 1)
    assert coverage.effective == ClipBounds(9, 24, 5, 20, 2, 5)
    assert coverage.has_discarded_source
    assert "X 1, Y 1, Z 1" in coverage.warning()
    with pytest.raises(ClipError, match="smaller than one coarse voxel"):
        coarse_coverage(ClipBounds(1, 7, 1, 8, 1, 2), (8, 8, 2))


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


def test_large_ct_preview_uses_bounded_sampling_without_changing_source_indices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _preview_stride(512, 512, 300) == 2
    assert _preview_stride(512, 512, 600) == 3
    assert _preview_stride(512, 512, 1000) == 4
    root = tmp_path / "ct"
    _pixel_series(root)
    # A synthetic small budget forces the same sampled path without creating
    # hundreds of large DICOM files in the test suite.
    budget = 24 * 1024 * 1024 + 8 * 5 * 7 + 145
    monkeypatch.setattr("dicomxphits.ct_preview.PREVIEW_MEMORY_LIMIT", budget)
    volume = load_preview(root, None)
    assert volume.sample_stride == 2
    assert volume.shape == VolumeShape(7, 5, 3, 1.0, 2.0, 3.0)
    assert volume.pixels.shape == (3, 3, 4)
    assert volume.sampled_rows.tolist() == [0, 2, 4]
    assert volume.sampled_columns.tolist() == [0, 2, 4, 6]
    assert volume.plane("Axial", 2)[1, 2] == 118 * 2 - 100
    assert volume.displayed_plane_index("Coronal", 2) == 1
    assert volume.displayed_plane_index("Coronal", 3) == 3
    assert ClipBounds.full(volume.shape) == ClipBounds(1, 7, 1, 5, 1, 3)


def test_six_hundred_slice_preview_keeps_every_axial_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = tuple(tmp_path / f"{z}.dcm" for z in range(600))
    selected = SelectedCtSeries(tmp_path, "synthetic-series", "synthetic-frame",
                                files, 512, 512, (1.0, 1.0))
    source_pixels = np.zeros((512, 512), dtype=np.int16)
    monkeypatch.setattr("dicomxphits.ct_preview.select_ct_series", lambda *_args, **_kwargs: selected)
    monkeypatch.setattr("dicomxphits.ct_preview._hash_file", lambda _path: "synthetic-hash")

    def synthetic_slice(path: str, **_kwargs: object) -> SimpleNamespace:
        z = int(Path(path).stem)
        source_pixels.fill(z)
        return SimpleNamespace(
            PhotometricInterpretation="MONOCHROME2", SamplesPerPixel=1,
            NumberOfFrames=1, BitsAllocated=16, pixel_array=source_pixels,
            RescaleSlope=1, RescaleIntercept=0,
            ImagePositionPatient=(0.0, 0.0, float(z)),
        )

    monkeypatch.setattr("dicomxphits.ct_preview.pydicom.dcmread", synthetic_slice)
    progress: list[tuple[int, int]] = []
    volume = load_preview(tmp_path, None, progress=lambda done, total: progress.append((done, total)))
    assert volume.sample_stride == 3
    assert volume.pixels.shape == (600, 171, 171)
    assert volume.shape == VolumeShape(512, 512, 600, 1.0, 1.0, 1.0)
    assert progress[-1] == (600, 600)
    for index in (1, 300, 600):
        assert volume.displayed_plane_index("Axial", index) == index
        assert volume.plane("Axial", index)[0, 0] == index - 1
    assert volume.plane("Coronal", 256).shape == (600, 171)
    assert volume.plane("Sagittal", 256).shape == (600, 171)
    assert ClipBounds.full(volume.shape) == ClipBounds(1, 512, 1, 512, 1, 600)


def test_sampled_plane_overlay_and_pointer_use_the_shown_source_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ct"
    _pixel_series(root)
    monkeypatch.setattr("dicomxphits.ct_preview.PREVIEW_MEMORY_LIMIT",
                        24 * 1024 * 1024 + 8 * 5 * 7 + 145)
    volume = load_preview(root, None)
    assert volume.sample_stride == 2

    class Variable:
        def __init__(self, value: object) -> None:
            self.value = value

        def get(self) -> object:
            return self.value

        def set(self, value: object) -> None:
            self.value = value

    class Canvas:
        def __init__(self) -> None:
            self.texts: list[str] = []

        def delete(self, *_args: object) -> None:
            self.texts.clear()

        def winfo_width(self) -> int:
            return 340

        def winfo_height(self) -> int:
            return 340

        def create_image(self, *_args: object, **_kwargs: object) -> None:
            pass

        def create_rectangle(self, *_args: object, **_kwargs: object) -> None:
            pass

        def create_line(self, *_args: object, **_kwargs: object) -> None:
            pass

        def create_text(self, *_args: object, **kwargs: object) -> None:
            self.texts.append(str(kwargs["text"]))

    dialog = object.__new__(CtPreviewDialog)
    dialog.volume = volume
    dialog.canvases = {"Coronal": Canvas(), "Sagittal": Canvas()}
    dialog.images = {}
    dialog.nav = {name: Variable(2) for name in ("Axial", "Coronal", "Sagittal")}
    dialog.position_labels = {name: Variable("") for name in dialog.canvases}
    dialog.fields = [Variable(value) for value in (2, 6, 2, 4, 1, 3)]
    dialog.center = Variable(0)
    dialog.width = Variable(400)
    dialog.status = Variable("")
    dialog.pointer = Variable("")
    dialog.pending = None
    dialog.crosshair = (3, 2, 2)
    monkeypatch.setattr("dicomxphits.ct_preview._photo", lambda *_args: object())

    for name in ("Coronal", "Sagittal"):
        dialog._draw(name)
        assert dialog.position_labels[name].get().endswith("(shown 1)")
        assert "Outside selected volume" in dialog.canvases[name].texts

    monkeypatch.setattr(dialog, "_source_point", lambda *_args: (4, 3))
    monkeypatch.setattr(dialog, "_draw_all", lambda: None)
    dialog._motion("Coronal", SimpleNamespace())
    assert "Ny 1" in dialog.pointer.get()
    dialog._navigate("Coronal")
    assert dialog.crosshair == (3, 1, 2)
    dialog._set_crosshair("Coronal", SimpleNamespace())
    assert dialog.crosshair == (4, 1, 3)


def test_synthetic_tk_corner_selection_and_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root_path = tmp_path / "ct"
    _pixel_series(root_path)
    monkeypatch.setattr("dicomxphits.ct_preview.PREVIEW_MEMORY_LIMIT",
                        24 * 1024 * 1024 + 8 * 5 * 7 + 145)
    volume = load_preview(root_path, None)
    assert volume.sample_stride == 2
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
        assert set(dialog.images) == {"Axial", "Coronal", "Sagittal"}
        assert "bounds use source indices" in dialog.retained.get()
        canvas = dialog.canvases["Axial"]
        transform = PlaneTransform("Axial", volume.shape,
                                   canvas.winfo_width(), canvas.winfo_height())
        def event_for(x: int, y: int) -> SimpleNamespace:
            left, top, width, height = transform.frame
            return SimpleNamespace(x=left + (x - 0.5) * width / volume.shape.columns,
                                   y=top + (y - 0.5) * height / volume.shape.rows)
        dialog._click("Axial", event_for(6, 4))
        assert dialog.crosshair[:2] == (6, 4)
        assert tuple(field.get() for field in dialog.fields) == ("1", "7", "1", "5", "1", "3")
        initial_width = canvas.winfo_width()
        dialog._focus("Axial")
        root.update()
        assert dialog.focused_plane == "Axial"
        assert canvas.winfo_width() >= initial_width
        transform = PlaneTransform("Axial", volume.shape,
                                   canvas.winfo_width(), canvas.winfo_height())
        dialog.selection_mode.set(True)
        dialog._set_selection_mode()
        dialog._click("Axial", event_for(6, 4))
        dialog._click("Axial", event_for(2, 2))
        assert tuple(field.get() for field in dialog.fields) == ("2", "6", "2", "4", "1", "3")
        assert not dialog.selection_mode.get()
        dialog._reset()
        assert tuple(field.get() for field in dialog.fields) == ("1", "7", "1", "5", "1", "3")
        dialog.selection_mode.set(True)
        dialog._set_selection_mode()
        dialog._click("Axial", event_for(6, 4))
        dialog._click("Axial", event_for(2, 2))
        dialog._focus(None)
        assert dialog.focused_plane is None
        transform = PlaneTransform("Axial", volume.shape,
                                   canvas.winfo_width(), canvas.winfo_height())
        dialog._set_crosshair("Axial", event_for(7, 5))
        previous = round(dialog.nav["Coronal"].get())
        dialog._step("Coronal", -1)
        assert round(dialog.nav["Coronal"].get()) == previous - 1
        dialog._wheel("Coronal", SimpleNamespace(delta=-120))
        assert round(dialog.nav["Coronal"].get()) == previous
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
