"""Read-only, bounded CT pixel preview for the guided Tk workflow."""

from __future__ import annotations

import hashlib
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Callable

import numpy as np
import pydicom

from dicomxphits.ct_pixel_clipping import ClipBounds, ClipError, PlaneTransform, VolumeShape
from dicomxphits.run_ct2phits import SelectedCtSeries, select_ct_series


# Budget for the preview stack, one full decoded source slice, and display
# temporaries. Source dimensions and clipping coordinates are never reduced.
PREVIEW_MEMORY_LIMIT = 128 * 1024 * 1024
_PREVIEW_DISPLAY_RESERVE = 24 * 1024 * 1024


class PreviewError(ValueError):
    """The source cannot safely be displayed."""


@dataclass(frozen=True)
class PreviewVolume:
    series: SelectedCtSeries
    shape: VolumeShape
    pixels: np.ndarray
    slopes: tuple[float, ...]
    intercepts: tuple[float, ...]
    hashes: tuple[str, ...]
    sample_stride: int
    sampled_rows: np.ndarray
    sampled_columns: np.ndarray

    def displayed_plane_index(self, name: str, index: int) -> int:
        if name == "Axial":
            return index
        if name not in ("Coronal", "Sagittal"):
            raise PreviewError("unknown preview plane")
        samples = self.sampled_rows if name == "Coronal" else self.sampled_columns
        return int(samples[_nearest_sample(samples, index - 1)]) + 1

    def plane(self, name: str, index: int) -> np.ndarray:
        if name == "Axial":
            return self.pixels[index - 1].astype(np.float32) * self.slopes[index - 1] + self.intercepts[index - 1]
        if name == "Coronal":
            raw = self.pixels[::-1, _nearest_sample(self.sampled_rows, index - 1), :]
        elif name == "Sagittal":
            raw = self.pixels[::-1, :, _nearest_sample(self.sampled_columns, index - 1)]
        else:
            raise PreviewError("unknown preview plane")
        slopes = np.asarray(self.slopes[::-1], dtype=np.float32)[:, None]
        intercepts = np.asarray(self.intercepts[::-1], dtype=np.float32)[:, None]
        return raw.astype(np.float32) * slopes + intercepts

    def still_current(self) -> bool:
        try:
            selected = select_ct_series(
                self.series.source_root,
                series_instance_uid=self.series.series_instance_uid,
            )
            return selected == self.series and tuple(
                _hash_file(path) for path in selected.files
            ) == self.hashes
        except (OSError, ValueError):
            return False


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _nearest_sample(samples: np.ndarray, source_index: int) -> int:
    position = int(np.searchsorted(samples, source_index))
    if position >= len(samples):
        return len(samples) - 1
    if position and source_index - samples[position - 1] <= samples[position] - source_index:
        return position - 1
    return position


def _sampled_indices(length: int, stride: int) -> np.ndarray:
    count = (length + stride - 1) // stride
    return np.rint(np.linspace(0, length - 1, count)).astype(np.intp)


def _preview_stride(rows: int, columns: int, slices: int) -> int:
    # PixelData and the decoded full source slice can coexist during pydicom
    # decoding. Keep those plus display arrays within the same bounded budget.
    fixed_bytes = _PREVIEW_DISPLAY_RESERVE + 8 * rows * columns
    for stride in range(1, max(rows, columns) + 1):
        sampled_rows = (rows + stride - 1) // stride
        sampled_columns = (columns + stride - 1) // stride
        stack_bytes = 4 * slices * sampled_rows * sampled_columns
        if fixed_bytes + stack_bytes <= PREVIEW_MEMORY_LIMIT:
            return stride
    raise PreviewError("CT preview exceeds the 128 MiB memory budget")


def load_preview(
    root: Path,
    series_uid: str | None,
    *,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int, int], None] = lambda _done, _total: None,
) -> PreviewVolume:
    selected = select_ct_series(root, series_instance_uid=series_uid)
    count = len(selected.files)
    stride = _preview_stride(selected.rows, selected.columns, count)
    if cancelled():
        raise PreviewError("preview loading cancelled")
    sampled_rows = _sampled_indices(selected.rows, stride)
    sampled_columns = _sampled_indices(selected.columns, stride)
    pixels = np.empty((count, len(sampled_rows), len(sampled_columns)), dtype=np.int32)
    slopes: list[float] = []
    intercepts: list[float] = []
    hashes: list[str] = []
    z_positions: list[float] = []
    for number, path in enumerate(selected.files):
        if cancelled():
            raise PreviewError("preview loading cancelled")
        before = _hash_file(path)
        try:
            dataset = pydicom.dcmread(str(path), force=False)
            if (str(getattr(dataset, "PhotometricInterpretation", "")) != "MONOCHROME2"
                or int(getattr(dataset, "SamplesPerPixel", 0)) != 1
                or int(getattr(dataset, "NumberOfFrames", 1)) != 1
                or int(getattr(dataset, "BitsAllocated", 0)) not in (8, 16)):
                raise PreviewError("preview requires single-frame 8/16-bit MONOCHROME2 CT pixels")
            decoded = dataset.pixel_array
            if decoded.shape != (selected.rows, selected.columns) or decoded.dtype.kind not in "iu":
                raise PreviewError("decoded CT pixels do not match validated source dimensions")
            slope = float(getattr(dataset, "RescaleSlope", 1))
            intercept = float(getattr(dataset, "RescaleIntercept", 0))
            if not np.isfinite(slope) or not np.isfinite(intercept):
                raise PreviewError("CT rescale values must be finite")
            pixels[number] = decoded[np.ix_(sampled_rows, sampled_columns)]
            slopes.append(slope)
            intercepts.append(intercept)
            z_positions.append(float(dataset.ImagePositionPatient[2]))
        except PreviewError:
            raise
        except (Exception,) as exc:
            raise PreviewError(f"could not decode CT preview slice {number + 1}: {exc}") from exc
        if _hash_file(path) != before:
            raise PreviewError("CT source changed while loading preview")
        hashes.append(before)
        progress(number + 1, count)
    if select_ct_series(root, series_instance_uid=selected.series_instance_uid) != selected:
        raise PreviewError("CT series changed while loading preview")
    if tuple(_hash_file(path) for path in selected.files) != tuple(hashes):
        raise PreviewError("CT source changed while loading preview")
    z_mm = z_positions[1] - z_positions[0] if count > 1 else None
    shape = VolumeShape(selected.columns, selected.rows, count,
                        selected.pixel_spacing_mm[1], selected.pixel_spacing_mm[0], z_mm)
    return PreviewVolume(selected, shape, pixels, tuple(slopes), tuple(intercepts),
                         tuple(hashes), stride, sampled_rows, sampled_columns)


def _photo(plane: np.ndarray, width: int, height: int, low: float, high: float) -> tk.PhotoImage:
    y = np.minimum(plane.shape[0] - 1, np.arange(height) * plane.shape[0] // height)
    x = np.minimum(plane.shape[1] - 1, np.arange(width) * plane.shape[1] // width)
    sampled = plane[np.ix_(y, x)]
    gray = np.clip((sampled - low) * (255.0 / max(high - low, 1.0)), 0, 255).astype(np.uint8)
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    return tk.PhotoImage(data=f"P6\n{width} {height}\n255\n".encode("ascii") + rgb.tobytes(), format="PPM")


class CtPreviewDialog:
    """A case-bound draft editor. It does not run CT2PHITS."""

    def __init__(self, parent: tk.Misc, root: Path, series_uid: str | None,
                 applied: ClipBounds | None, on_apply: Callable[[PreviewVolume, ClipBounds], None],
                 is_current: Callable[[], bool] = lambda: True) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title("CT images / Clipping range")
        self.window.geometry("1120x760")
        self.window.minsize(1120, 640)
        self.window.configure(background="#071A2B")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.root = root
        self.series_uid = series_uid
        self.on_apply = on_apply
        self.is_current = is_current
        self.applied = applied
        self.volume: PreviewVolume | None = None
        self.cancel_event = threading.Event()
        self.results: queue.Queue[tuple[str, object]] = queue.Queue()
        self.fields: list[tk.StringVar] = []
        self.nav: dict[str, tk.DoubleVar] = {}
        self.scales: dict[str, ttk.Scale] = {}
        self.frames: dict[str, ttk.LabelFrame] = {}
        self.position_labels: dict[str, tk.StringVar] = {}
        self.canvases: dict[str, tk.Canvas] = {}
        self.images: dict[str, tk.PhotoImage] = {}
        self.pending: tuple[str, tuple[int, int]] | None = None
        self.crosshair: tuple[int, int, int] | None = None
        self.updating_fields = False
        self.selection_mode = tk.BooleanVar(value=False)
        self.focused_plane: str | None = None
        self.status = tk.StringVar(value="Loading validated non-patient CT pixels…")
        self.pointer = tk.StringVar(value="Pointer: —")
        self.retained = tk.StringVar(value="Retained source voxels: —")
        self.center = tk.DoubleVar(value=0)
        self.width = tk.DoubleVar(value=400)
        self._build()
        threading.Thread(target=self._load, daemon=True).start()
        self.window.after(80, self._poll)

    def _build(self) -> None:
        outer = ttk.Frame(self.window, style="App.TFrame", padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        ttk.Label(outer, textvariable=self.status, style="CTPreview.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, textvariable=self.pointer, style="CTPreview.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(outer, textvariable=self.retained, style="CTPreview.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(
            outer,
            text="Green outline = retained box; shaded area = excluded. Browse with left click; "
                 "turn on corner selection to edit the box. Right click always moves the crosshair.",
            wraplength=1050,
            style="CTPreview.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(4, 0))
        view_tools = ttk.Frame(outer, style="App.TFrame")
        view_tools.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            view_tools, text="Select two corners (left click)",
            variable=self.selection_mode, command=self._set_selection_mode,
            style="CTPreview.TCheckbutton",
        ).pack(side="left")
        ttk.Button(view_tools, text="Show all three views", command=lambda: self._focus(None)).pack(
            side="right"
        )
        views = ttk.Frame(outer, style="App.TFrame")
        views.grid(row=5, column=0, sticky="nsew", pady=8)
        views.rowconfigure(0, weight=1)
        self.views = views
        for column, name in enumerate(("Axial", "Coronal", "Sagittal")):
            frame = ttk.LabelFrame(views, text=name, padding=5,
                                   style="CTPreview.TLabelframe")
            frame.grid(row=0, column=column, sticky="nsew", padx=3)
            views.columnconfigure(column, weight=1)
            self.frames[name] = frame
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            controls = ttk.Frame(frame, style="Surface.TFrame")
            controls.grid(row=0, column=0, sticky="ew", pady=(0, 4))
            ttk.Button(controls, text="−", width=3,
                       command=lambda n=name: self._step(n, -1)).pack(side="left")
            position = tk.StringVar(value="—")
            self.position_labels[name] = position
            ttk.Label(controls, textvariable=position, width=17, anchor="center",
                      style="Surface.TLabel").pack(side="left")
            ttk.Button(controls, text="+", width=3,
                       command=lambda n=name: self._step(n, 1)).pack(side="left")
            ttk.Button(controls, text="Expand", command=lambda n=name: self._focus(n)).pack(side="right")
            canvas = tk.Canvas(frame, width=340, height=340, bg="#151d28", highlightthickness=0)
            canvas.grid(row=1, column=0, sticky="nsew")
            canvas.bind("<Configure>", lambda _e, n=name: self._draw(n))
            canvas.bind("<Motion>", lambda e, n=name: self._motion(n, e))
            canvas.bind("<Button-1>", lambda e, n=name: self._click(n, e))
            canvas.bind("<Button-3>", lambda e, n=name: self._set_crosshair(n, e))
            canvas.bind("<MouseWheel>", lambda e, n=name: self._wheel(n, e))
            self.canvases[name] = canvas
            index = tk.DoubleVar(value=1)
            self.nav[name] = index
            scale = ttk.Scale(frame, from_=1, to=1, variable=index,
                              command=lambda _v, n=name: self._navigate(n))
            scale.grid(row=2, column=0, sticky="ew")
            self.scales[name] = scale
            ttk.Label(frame, text={"Axial": "X →  Y ↓", "Coronal": "X →  Z ↑", "Sagittal": "Y →  Z ↑"}[name],
                      style="Surface.TLabel").grid(row=3, column=0)
        fields = ttk.Frame(outer, style="App.TFrame")
        fields.grid(row=6, column=0, sticky="ew", pady=5)
        for i, label in enumerate(("Nx min", "Nx max", "Ny min", "Ny max", "First slice", "Last slice")):
            ttk.Label(fields, text=label, style="CTPreview.TLabel").grid(row=0, column=i)
            var = tk.StringVar()
            var.trace_add("write", lambda *_: self._numeric_changed())
            self.fields.append(var)
            ttk.Entry(fields, textvariable=var, width=12).grid(row=1, column=i, padx=3)
        contrast = ttk.Frame(outer, style="App.TFrame")
        contrast.grid(row=7, column=0, sticky="ew")
        ttk.Label(contrast, text="Display centre", style="CTPreview.TLabel").pack(side="left")
        ttk.Entry(contrast, textvariable=self.center, width=9).pack(side="left", padx=6)
        ttk.Label(contrast, text="Width", style="CTPreview.TLabel").pack(side="left")
        ttk.Entry(contrast, textvariable=self.width, width=9).pack(side="left", padx=6)
        ttk.Button(contrast, text="Refresh contrast", command=self._draw_all).pack(side="left")
        actions = ttk.Frame(outer, style="App.TFrame")
        actions.grid(row=8, column=0, sticky="ew", pady=10)
        ttk.Button(actions, text="Reset to full volume", command=self._reset).pack(side="left")
        ttk.Button(actions, text="Cancel", command=self.close).pack(side="right")
        ttk.Button(actions, text="Apply", style="Primary.TButton",
                   command=self._apply).pack(side="right", padx=8)

    def _load(self) -> None:
        try:
            result = load_preview(self.root, self.series_uid,
                                  cancelled=self.cancel_event.is_set,
                                  progress=lambda done, total: self.results.put(("progress", (done, total))))
            self.results.put(("loaded", result))
        except MemoryError:
            self.results.put(("error", "not enough memory for CT preview"))
        except Exception as exc:
            self.results.put(("error", str(exc)))

    def _poll(self) -> None:
        if not self.window.winfo_exists():
            return
        if not self.is_current():
            self.cancel_event.set()
            self.volume = None
            self.images.clear()
            for canvas in self.canvases.values():
                canvas.delete("all")
            self.status.set("CT selection changed; close and reopen the preview")
            return
        try:
            while True:
                kind, value = self.results.get_nowait()
                if kind == "progress":
                    done, total = value
                    self.status.set(f"Loading slice {done}/{total}…")
                elif kind == "error":
                    self.status.set(f"Preview unavailable: {value}")
                else:
                    self.volume = value
                    shape = value.shape
                    self._set_bounds(self.applied or ClipBounds.full(shape))
                    for name, limit in (("Axial", shape.slices), ("Coronal", shape.rows), ("Sagittal", shape.columns)):
                        self.scales[name].configure(to=limit)
                        self.nav[name].set((limit + 1) // 2)
                    self.crosshair = ((shape.columns + 1) // 2,
                                      (shape.rows + 1) // 2,
                                      (shape.slices + 1) // 2)
                    self.status.set("Two clicks in one image set its two axes. Review the retained bounds and coarse-graining warning before conversion.")
                    self._draw_all()
        except queue.Empty:
            pass
        self.window.after(80, self._poll)

    def _set_bounds(self, bounds: ClipBounds) -> None:
        self.updating_fields = True
        try:
            for field, value in zip(self.fields, bounds.__dict__.values()):
                field.set(str(value))
        finally:
            self.updating_fields = False
        self._draw_all()

    def _bounds(self) -> ClipBounds:
        if self.volume is None:
            raise ClipError("preview has not loaded")
        return ClipBounds.parse(tuple(field.get() for field in self.fields), self.volume.shape)

    def _numeric_changed(self) -> None:
        if self.volume is not None and not self.updating_fields:
            self.pending = None
            try:
                self._bounds()
                self.status.set("Numeric source bounds are valid. Apply commits this draft selection.")
            except ClipError as exc:
                self.status.set(str(exc))
            self._draw_all()

    def _set_selection_mode(self) -> None:
        if not self.selection_mode.get():
            self.pending = None
        for canvas in self.canvases.values():
            canvas.configure(cursor="crosshair" if self.selection_mode.get() else "arrow")
        self.status.set(
            "Select two corners in one image. The other axis remains unchanged."
            if self.selection_mode.get() else
            "Browse mode: left click moves the linked crosshair without editing the box."
        )
        self._draw_all()

    def _focus(self, name: str | None) -> None:
        self.focused_plane = name
        if self.pending is not None and self.pending[0] != name:
            self.pending = None
        for frame in self.frames.values():
            frame.grid_forget()
        if name is None:
            for column, plane in enumerate(("Axial", "Coronal", "Sagittal")):
                self.views.columnconfigure(column, weight=1)
                self.frames[plane].grid(row=0, column=column, sticky="nsew", padx=3)
        else:
            for column in range(3):
                self.views.columnconfigure(column, weight=1 if column == 0 else 0)
            self.frames[name].grid(row=0, column=0, columnspan=3, sticky="nsew", padx=3)
        self.window.update_idletasks()
        self._draw_all()

    def _step(self, name: str, delta: int) -> None:
        if self.volume is None:
            return
        shape = self.volume.shape
        limit = {"Axial": shape.slices, "Coronal": shape.rows, "Sagittal": shape.columns}[name]
        self.nav[name].set(max(1, min(limit, round(self.nav[name].get()) + delta)))
        self._navigate(name)

    def _wheel(self, name: str, event: tk.Event) -> str:
        if event.delta:
            self._step(name, -1 if event.delta > 0 else 1)
        return "break"

    def _navigate(self, name: str) -> None:
        if self.volume is None:
            return
        if self.pending is not None and self.pending[0] != name:
            self.pending = None
        if self.crosshair is not None:
            x, y, z = self.crosshair
            position = self.volume.displayed_plane_index(name, round(self.nav[name].get()))
            self.crosshair = ((x, y, position) if name == "Axial" else
                              (x, position, z) if name == "Coronal" else
                              (position, y, z))
        self._draw_all()

    def _draw_all(self) -> None:
        if self.volume is not None:
            try:
                bounds = self._bounds()
                self.retained.set(
                    f"Retained source voxels: Nx {bounds.nx_max - bounds.nx_min + 1}, "
                    f"Ny {bounds.ny_max - bounds.ny_min + 1}, "
                    f"slices {bounds.last - bounds.first + 1}"
                )
            except ClipError:
                self.retained.set("Retained source voxels: invalid bounds")
            if self.volume.sample_stride > 1:
                self.retained.set(
                    self.retained.get()
                    + f" | Display samples X/Y about 1 in {self.volume.sample_stride}; bounds use source indices"
                )
        for name in self.canvases:
            self._draw(name)

    def _draw(self, name: str) -> None:
        canvas = self.canvases[name]
        canvas.delete("all")
        if self.volume is None:
            return
        shape = self.volume.shape
        if name != "Axial" and shape.slices == 1:
            canvas.create_text(canvas.winfo_width() / 2, canvas.winfo_height() / 2,
                               text="Unavailable: one source slice", fill="white")
            return
        limit = {"Axial": shape.slices, "Coronal": shape.rows, "Sagittal": shape.columns}[name]
        index = max(1, min(limit, round(self.nav[name].get())))
        displayed = self.volume.displayed_plane_index(name, index)
        self.position_labels[name].set(
            f"{index} / {limit}" if displayed == index else f"{index}/{limit} (shown {displayed})"
        )
        transform = PlaneTransform(name, shape, max(1, canvas.winfo_width()), max(1, canvas.winfo_height()))
        left, top, width, height = transform.frame
        try:
            centre, window = float(self.center.get()), float(self.width.get())
            if not np.isfinite(centre) or not np.isfinite(window) or window <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            self.status.set("Contrast centre must be finite and width positive")
            return
        photo = _photo(self.volume.plane(name, displayed), max(1, round(width)),
                       max(1, round(height)), centre - window / 2, centre + window / 2)
        self.images[name] = photo
        canvas.create_image(left, top, image=photo, anchor="nw")
        try:
            bounds = self._bounds()
        except ClipError:
            return
        x0, y0, x1, y1 = transform.source_rectangle(bounds)
        color = "#28e9a6" if bounds.contains_plane(name, displayed) else "#ffba67"
        if bounds.contains_plane(name, displayed):
            for region in ((left, top, left + width, y0),
                           (left, y1, left + width, top + height),
                           (left, y0, x0, y1),
                           (x1, y0, left + width, y1)):
                canvas.create_rectangle(*region, fill="#101820", stipple="gray25", outline="")
        canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=2)
        if self.crosshair is not None:
            x, y, z = self.crosshair
            point = ClipBounds(x, x, y, y, z, z)
            px0, py0, px1, py1 = transform.source_rectangle(point)
            middle_x, middle_y = (px0 + px1) / 2, (py0 + py1) / 2
            canvas.create_line(middle_x, top, middle_x, top + height, fill="#85caff", dash=(3, 3))
            canvas.create_line(left, middle_y, left + width, middle_y, fill="#85caff", dash=(3, 3))
        if not bounds.contains_plane(name, displayed):
            canvas.create_text(left + 8, top + 8, anchor="nw", text="Outside selected volume", fill=color)
        if self.pending is not None and self.pending[0] == name:
            point = self.pending[1]
            pair = bounds.with_corners(name, point, point)
            x0, y0, x1, y1 = transform.source_rectangle(pair)
            canvas.create_oval((x0+x1)/2-4, (y0+y1)/2-4, (x0+x1)/2+4, (y0+y1)/2+4,
                               fill="#ffba67", outline="")

    def _source_point(self, name: str, event: tk.Event) -> tuple[int, int] | None:
        if self.volume is None or (name != "Axial" and self.volume.shape.slices == 1):
            return None
        canvas = self.canvases[name]
        transform = PlaneTransform(name, self.volume.shape, canvas.winfo_width(), canvas.winfo_height())
        return transform.canvas_to_source(event.x, event.y)

    def _motion(self, name: str, event: tk.Event) -> None:
        point = self._source_point(name, event)
        if point is None:
            self.pointer.set(f"Pointer: {name} outside image")
            return
        fixed = self.volume.displayed_plane_index(name, round(self.nav[name].get()))
        xyz = ((point[0], point[1], fixed) if name == "Axial" else
               (point[0], fixed, point[1]) if name == "Coronal" else
               (fixed, point[0], point[1]))
        self.pointer.set(f"Pointer: Nx {xyz[0]}, Ny {xyz[1]}, slice {xyz[2]}")

    def _set_crosshair(self, name: str, event: tk.Event) -> None:
        point = self._source_point(name, event)
        if point is None or self.volume is None:
            return
        fixed = self.volume.displayed_plane_index(name, round(self.nav[name].get()))
        self.crosshair = ((point[0], point[1], fixed) if name == "Axial" else
                          (point[0], fixed, point[1]) if name == "Coronal" else
                          (fixed, point[0], point[1]))
        x, y, z = self.crosshair
        for plane, index in (("Axial", z), ("Coronal", y), ("Sagittal", x)):
            self.nav[plane].set(index)
        self._draw_all()

    def _click(self, name: str, event: tk.Event) -> None:
        if not self.selection_mode.get():
            self._set_crosshair(name, event)
            return
        point = self._source_point(name, event)
        if point is None:
            return
        if self.pending is None or self.pending[0] != name:
            self.pending = (name, point)
            self.status.set(f"{name}: first corner {point}; click the opposite corner")
        else:
            try:
                bounds = self._bounds().with_corners(name, self.pending[1], point)
                bounds.validate(self.volume.shape)
                self._set_bounds(bounds)
                self.status.set(f"{name}: selected corners {self.pending[1]} and {point}")
                self.selection_mode.set(False)
            except ClipError as exc:
                self.status.set(str(exc))
            self.pending = None
            for canvas in self.canvases.values():
                canvas.configure(cursor="arrow" if not self.selection_mode.get() else "crosshair")
        self._draw_all()

    def _reset(self) -> None:
        if self.volume is not None:
            self.pending = None
            self.selection_mode.set(False)
            for canvas in self.canvases.values():
                canvas.configure(cursor="arrow")
            self._set_bounds(ClipBounds.full(self.volume.shape))

    def _apply(self) -> None:
        if self.pending is not None:
            self.status.set("Complete the two-corner selection before applying")
            return
        try:
            bounds = self._bounds()
            if not self.volume.still_current():
                raise ClipError("CT source changed; reopen the preview")
            self.on_apply(self.volume, bounds)
        except ClipError as exc:
            self.status.set(str(exc))
            return
        self.close()

    def close(self) -> None:
        self.cancel_event.set()
        self.window.destroy()
