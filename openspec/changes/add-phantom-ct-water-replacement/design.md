# Design: Non-Patient Phantom CT Water Replacement

## Context

The requested Lung and Bone workflows both replace a physical two-centimetre
layer containing a CC13 with a water-equivalent representation. The density
replacement ROI and Monaco's `Chamber_active` measurement ROI serve different
purposes. The derivation tool consumes only the former and a separate clean
water reference ROI.

The source RTSTRUCT remains tied to the source CT SOP Instance UIDs. Changing
Pixel Data while keeping those UIDs would falsely present a modified object as
the original instance. Conversely, automatically rewriting RTSTRUCT and RTPLAN
references would create a substantially larger DICOM transformation boundary.
This first version therefore creates only a new CT series and makes that
reference boundary conspicuous in its report and documentation.

## Goals

- Create a deterministic, auditable chamber-free derived phantom CT.
- Change only samples selected by the explicit target ROI.
- Derive replacement HU from the actual clean water reference ROI.
- Handle per-slice rescale and parallel oblique CT geometry correctly.
- Preserve input files and fail closed before unsafe or ambiguous output.
- Provide enough QC evidence for a human to inspect the replacement.

## Non-Goals

- Patient CT processing, clinical commissioning, patient QA, or vendor
  certification.
- Automatic chamber detection, body segmentation, target-name guessing, or
  RTSTRUCT discovery.
- RTSTRUCT, RTPLAN, or RTDOSE rewriting.
- Changing CT2PHITS geometry eligibility, PHITS transport, beam apertures,
  absolute-dose factors, or Monaco structures/plans.
- Running CT2PHITS, PHITS, Monaco, or GPR automatically.
- Supporting compressed, encapsulated, multi-frame, color, or floating-point
  Pixel Data in the initial version.

## Decisions

### 1. Keep the helper independent and explicitly gated

The public interface will be available both as
`dicomxphits-replace-ct-layer-with-water` and as the thin repository script
`tools/replace_ct_layer_with_water.py`. The required arguments are:

```text
--ct-dir
--rtstruct
--target-roi
--reference-roi
--output-dir
--confirm-non-patient-phantom
```

An optional `--ct-series-instance-uid` resolves multiple CT series. The command
never discovers an RTSTRUCT. It refuses an output directory equal to, inside,
or containing the input CT directory, and refuses an existing output path.

Structural errors always stop. Suspicious-but-reviewable QC findings stop by
default and may be acknowledged only with `--accept-qc-warnings`; the findings
remain in both reports. This is not a clinical acceptance mechanism.

### 2. Select and validate one conventional CT series

The helper reads regular, non-link DICOM files directly below the selected CT
directory. It selects exactly one CT Series Instance UID unless the optional
UID is supplied. Each slice must be single-frame monochrome native Pixel Data
with 8- or 16-bit allocation, valid `BitsStored`, `HighBit`, and
`PixelRepresentation`, and a finite nonzero rescale slope.

All slices must share dimensions, pixel spacing, orientation, frame UID, and a
parallel regularly spaced stack. Slice order is the projection of
`ImagePositionPatient` onto the normalized cross product of the two
`ImageOrientationPatient` direction cosines. The helper preserves every source
geometry attribute rather than normalizing it.

Native uncompressed transfer syntaxes are required so that the implementation
can edit the target sample bits in a copy of the original `PixelData` byte
buffer. Encapsulated input fails with an actionable message rather than being
silently decompressed and re-encoded.

### 3. Bind RTSTRUCT contours to the selected CT explicitly

The RTSTRUCT frame UID and referenced CT series must match the selected CT.
The target and reference ROI names must each occur exactly once and must map to
exactly one ROI contour. Every used contour must be `CLOSED_PLANAR`, carry a
`ContourImageSequence` reference to exactly one selected CT SOP Instance UID,
and lie on that referenced image plane within 0.1 mm.

For a slice with patient-space origin `P`, row direction `X`, column direction
`Y`, row spacing `dr`, and column spacing `dc`, pixel centre `(r, c)` is:

```text
P + X * c * dc + Y * r * dr
```

Contour points are projected into that basis and evaluated at pixel centres.
An even-odd fill rule combines multiple closed contours so that nested contours
represent holes without depending on winding direction. Non-finite,
degenerate, open, off-plane, unreferenced, or multiply referenced contours
fail closed.

### 4. Use reference-water median HU with explicit fallback

The helper converts stored samples to HU independently for each slice:

```text
HU = stored_value * RescaleSlope + RescaleIntercept
```

It computes the global reference median from all reference-mask voxels. A
slice with reference voxels uses its own median; a slice with no reference
voxels uses the global median and is listed as a fallback. Mean, standard
deviation, median, count, and robust percentile information are reported but
the median alone supplies replacement HU.

Initial QC defaults are deliberately review-oriented rather than claims about
water calibration:

- fewer than 1,000 global reference voxels is a QC warning;
- a reference median outside -200 to +200 HU, standard deviation above 100 HU,
  or 5th/95th percentile outside -200 to +200 HU is a QC warning;
- any target-mask contact with the image matrix boundary, or target overlap
  with boundary-connected pixels below -500 HU, is a QC warning; and
- the shortest patient-coordinate principal-axis extent of the occupied target,
  including voxel support, outside 15 to 25 mm is a QC warning. The separate
  stack-normal extent is reported but is not assumed to be layer thickness;
  and
- a target with other than exactly one principal extent in the 15 to 25 mm
  range is a QC warning because it is not shaped as one whole thin layer.

The numeric values are recorded in the report and public documentation. They
are preprocessing review gates, not treatment tolerances or scanner
commissioning criteria.

### 5. Preserve native sample representation

For each target sample the desired stored value is computed by the inverse
relationship and rounded to the nearest integer using ties-to-even:

```text
stored_value = round((replacement_HU - RescaleIntercept) / RescaleSlope)
```

The result must fit the signed or unsigned `BitsStored` range. The helper
updates only the stored-value bit field defined by `BitsStored` and `HighBit`;
unused allocated bits are preserved. Samples outside the target mask retain
their exact original allocated bytes. A post-write pydicom reread verifies
Pixel Data, geometry, UIDs, and target values before the series is declared
complete.

### 6. Publish a distinct derived series

The source CT directory and RTSTRUCT are opened read-only and source file
hashes are checked again after output. The output directory is created only
after preflight succeeds and is guarded by the repository's workspace output
boundary. It must not already exist. An incomplete marker is written first;
on failure, partial output remains visibly incomplete and is never overwritten
by a retry. Successful verification removes the marker and writes completion
reports.

The derived series preserves `StudyInstanceUID`, `FrameOfReferenceUID`, image
position/orientation, spacing, dimensions, and instance ordering. It receives
one new `SeriesInstanceUID`; every slice receives a new `SOPInstanceUID`, and
`file_meta.MediaStorageSOPInstanceUID` matches it. `ImageType` identifies a
derived secondary image, `SeriesDescription`, `DerivationDescription`, and
creation timestamps describe the transformation, and `SourceImageSequence`
references the source instance.

### 7. Make QC artefacts identity-safe and reviewable

The output contains `qc-report.json`, `qc-report.txt`, and a representative
PNG montage showing windowed before, after, absolute HU difference, target
mask, and target/reference contour boundaries. PNG encoding uses the standard
library and NumPy, so no runtime dependency is added. The representative slice
is the target slice with the largest target-mask area.

Reports include source/output paths, non-identifying UIDs, geometry, ROI names,
voxel counts and volume, reference and target statistics, per-slice replacement
HU, fallback slices, UID checks, warnings, and source-integrity checks. They do
not read or emit `PatientName`, `PatientID`, birth date, accession number, or
other patient-demographic fields.

### 8. Keep downstream use explicit

The report states that the original RTSTRUCT still references the source CT.
The user must import the derived CT as a new series in Monaco, create/copy and
reassociate structures and plans according to local research practice, verify
registration and geometry, and ensure the independently defined
`Chamber_active` volume is located in the replaced water-equivalent region.
The helper neither verifies Monaco nor changes that measurement ROI.

The derived series may be supplied explicitly to the existing CT2PHITS
frontend only if it independently satisfies that frontend's documented axial
HFS constraints. Oblique support in the rasterizer does not override those
constraints.

## Validation Strategy

Synthetic DICOM tests will cover median replacement, target-only modification,
outside-target byte identity, signed and unsigned sample formats,
BitsStored/HighBit handling, per-slice rescale, global fallback, UID updates,
file-meta synchronization, pydicom reread, oblique geometry, source hash
preservation, output refusal, acknowledgement gates, warning gates, RTSTRUCT
reference failures, and inverse-rescale overflow.

Repository automation will not open supplied phantom data or execute licensed
scientific tools. After implementation and separate authorization, a local
read-only preflight followed by derived output to a new location can be run for
one Lung and one Bone phantom. CT2PHITS and Monaco checks remain separate steps.

## Risks and Mitigations

- **Wrong contour-to-pixel mapping:** use patient-coordinate projection,
  explicit SOP references, off-plane rejection, oblique synthetic tests, and
  visible contour evidence.
- **Reference ROI contamination:** report robust statistics and stop on QC
  warnings unless explicitly acknowledged.
- **Outside-air replacement:** detect matrix-boundary contact and
  boundary-connected air-like pixels; preserve the warning in all evidence.
- **Pixel representation corruption:** edit raw native sample bits, validate
  representable range, and reread every derived slice.
- **DICOM identity collision:** generate new series/instance UIDs and verify
  file-meta synchronization.
- **Source/derived reference mixing:** do not rewrite RT objects and state the
  reassociation boundary in the command output, reports, and documentation.
- **Partial output mistaken for complete output:** create a visible incomplete
  marker and remove it only after full verification.

## Rollback

Before implementation approval, rollback is deletion of this active proposal.
After implementation, rollback removes the independent CLI/module, tests, and
documentation together. Source DICOM never requires rollback because it is not
modified.
