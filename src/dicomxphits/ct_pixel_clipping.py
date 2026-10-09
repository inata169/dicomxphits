"""Source-index clipping and reversible orthogonal preview coordinates.

Preview coordinates are display-only. Coarse coverage reports complete source
groups for supplied factors; it does not infer anatomy or authorize factors
outside the frontend's supported input contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re


class ClipError(ValueError):
    """Invalid source-index clipping selection."""


@dataclass(frozen=True)
class VolumeShape:
    columns: int
    rows: int
    slices: int
    column_mm: float
    row_mm: float
    z_mm: float | None

    def __post_init__(self) -> None:
        if min(self.columns, self.rows, self.slices) < 1:
            raise ClipError("source dimensions must be positive")
        for value in (self.column_mm, self.row_mm):
            if not math.isfinite(value) or value <= 0:
                raise ClipError("source pixel spacing must be positive and finite")
        if self.z_mm is not None and (not math.isfinite(self.z_mm) or self.z_mm <= 0):
            raise ClipError("adjacent Z spacing must be positive and finite")


@dataclass(frozen=True)
class ClipBounds:
    nx_min: int
    nx_max: int
    ny_min: int
    ny_max: int
    first: int
    last: int

    @classmethod
    def full(cls, shape: VolumeShape) -> ClipBounds:
        return cls(1, shape.columns, 1, shape.rows, 1, shape.slices)

    @classmethod
    def parse(cls, values: tuple[object, ...], shape: VolumeShape) -> ClipBounds:
        if len(values) != 6:
            raise ClipError("six source-index bounds are required")
        parsed = []
        for value in values:
            if isinstance(value, bool) or re.fullmatch(r"[0-9]+", str(value).strip()) is None:
                raise ClipError("bounds must be positive integer source indices")
            parsed.append(int(str(value).strip()))
        bounds = cls(*parsed)
        bounds.validate(shape)
        return bounds

    def validate(self, shape: VolumeShape) -> None:
        if not (
            1 <= self.nx_min <= self.nx_max <= shape.columns
            and 1 <= self.ny_min <= self.ny_max <= shape.rows
            and 1 <= self.first <= self.last <= shape.slices
        ):
            raise ClipError("clipping bounds are reversed or outside the source CT")

    def is_full(self, shape: VolumeShape) -> bool:
        return self == self.full(shape)

    def with_corners(
        self, plane: str, first: tuple[int, int], second: tuple[int, int]
    ) -> ClipBounds:
        a, b = sorted((first[0], second[0]))
        c, d = sorted((first[1], second[1]))
        if plane == "Axial":
            return ClipBounds(a, b, c, d, self.first, self.last)
        if plane == "Coronal":
            return ClipBounds(a, b, self.ny_min, self.ny_max, c, d)
        if plane == "Sagittal":
            return ClipBounds(self.nx_min, self.nx_max, a, b, c, d)
        raise ClipError("unknown preview plane")

    def axes(self, plane: str) -> tuple[int, int, int, int]:
        if plane == "Axial":
            return self.nx_min, self.nx_max, self.ny_min, self.ny_max
        if plane == "Coronal":
            return self.nx_min, self.nx_max, self.first, self.last
        if plane == "Sagittal":
            return self.ny_min, self.ny_max, self.first, self.last
        raise ClipError("unknown preview plane")

    def contains_plane(self, plane: str, index: int) -> bool:
        if plane == "Axial":
            return self.first <= index <= self.last
        if plane == "Coronal":
            return self.ny_min <= index <= self.ny_max
        if plane == "Sagittal":
            return self.nx_min <= index <= self.nx_max
        raise ClipError("unknown preview plane")


@dataclass(frozen=True)
class CoarseCoverage:
    """Source indices represented by complete CT2PHITS coarse groups."""

    effective: ClipBounds
    discarded_high: tuple[int, int, int]
    voxel_counts: tuple[int, int, int]

    @property
    def has_discarded_source(self) -> bool:
        return any(self.discarded_high)

    def warning(self) -> str:
        x, y, z = self.discarded_high
        return (
            "CT2PHITS coarse graining will discard source pixels at the high end "
            f"of the selected box: X {x}, Y {y}, Z {z}. "
            f"Retained source bounds: X {self.effective.nx_min}-{self.effective.nx_max}, "
            f"Y {self.effective.ny_min}-{self.effective.ny_max}, "
            f"slices {self.effective.first}-{self.effective.last}. "
            "Review that the retained box contains the intended anatomy and PTV. "
            "Coarse graining also averages source detail."
        )


def coarse_coverage(bounds: ClipBounds, factors: tuple[int, int, int]) -> CoarseCoverage:
    if len(factors) != 3 or any(factor < 1 for factor in factors):
        raise ClipError("coarse graining factors must be positive")
    widths = (
        bounds.nx_max - bounds.nx_min + 1,
        bounds.ny_max - bounds.ny_min + 1,
        bounds.last - bounds.first + 1,
    )
    counts = tuple(width // factor for width, factor in zip(widths, factors))
    if any(count == 0 for count in counts):
        raise ClipError("selected CT box is smaller than one coarse voxel")
    discarded = tuple(width % factor for width, factor in zip(widths, factors))
    effective = ClipBounds(
        bounds.nx_min, bounds.nx_max - discarded[0],
        bounds.ny_min, bounds.ny_max - discarded[1],
        bounds.first, bounds.last - discarded[2],
    )
    return CoarseCoverage(effective, discarded, counts)


@dataclass(frozen=True)
class PlaneTransform:
    plane: str
    shape: VolumeShape
    canvas_width: int
    canvas_height: int

    @property
    def axes(self) -> tuple[int, int, float, float]:
        if self.plane == "Axial":
            return self.shape.columns, self.shape.rows, self.shape.column_mm, self.shape.row_mm
        if self.shape.z_mm is None:
            raise ClipError("orthogonal views are unavailable for one slice")
        if self.plane == "Coronal":
            return self.shape.columns, self.shape.slices, self.shape.column_mm, self.shape.z_mm
        if self.plane == "Sagittal":
            return self.shape.rows, self.shape.slices, self.shape.row_mm, self.shape.z_mm
        raise ClipError("unknown preview plane")

    @property
    def frame(self) -> tuple[float, float, float, float]:
        width, height, dx, dy = self.axes
        scale = min(self.canvas_width / (width * dx), self.canvas_height / (height * dy))
        drawn_width = max(1, min(self.canvas_width, round(width * dx * scale)))
        drawn_height = max(1, min(self.canvas_height, round(height * dy * scale)))
        return ((self.canvas_width - drawn_width) / 2,
                (self.canvas_height - drawn_height) / 2, drawn_width, drawn_height)

    def canvas_to_source(self, x: float, y: float) -> tuple[int, int] | None:
        left, top, width, height = self.frame
        if not (left <= x < left + width and top <= y < top + height):
            return None
        count_x, count_y, _dx, _dy = self.axes
        source_x = min(count_x, int((x - left) * count_x / width) + 1)
        display_y = min(count_y, int((y - top) * count_y / height) + 1)
        source_y = count_y + 1 - display_y if self.plane != "Axial" else display_y
        return source_x, source_y

    def source_rectangle(self, bounds: ClipBounds) -> tuple[float, float, float, float]:
        left, top, width, height = self.frame
        count_x, count_y, _dx, _dy = self.axes
        x0, x1, y0, y1 = bounds.axes(self.plane)
        if self.plane != "Axial":
            y0, y1 = count_y + 1 - y1, count_y + 1 - y0
        return (left + (x0 - 1) * width / count_x,
                top + (y0 - 1) * height / count_y,
                left + x1 * width / count_x,
                top + y1 * height / count_y)
