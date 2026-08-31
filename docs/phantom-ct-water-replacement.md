# Non-Patient Phantom CT Water Replacement

This helper creates a calculation-only derived CT series in which one explicit
phantom layer is replaced with the median HU of a separate clean-water ROI. It
is limited to education and research with a confirmed non-patient phantom. It
is not a patient-data tool, clinical commissioning procedure, patient QA
method, or substitute for CT/TPS verification.

## Intended Lung and Bone transformations

The same operation supports these generic physical-stack intentions:

```text
Lung: Water 1 cm / Lung 7 cm / Water + CC13 2 cm / Water 8 cm
   -> Water 1 cm / Lung 7 cm / Water 2 cm / Water 8 cm

Bone: Water 7 cm / Bone 1 cm / Water + CC13 2 cm / Water 8 cm
   -> Water 7 cm / Bone 1 cm / Water 2 cm / Water 8 cm
```

Only the RTSTRUCT target mask determines which voxels change. The command does
not recognize those stacks, locate a chamber, or infer a layer from CT values.

## Required structures

Prepare two separate structures in an RTSTRUCT that explicitly references the
source CT series:

- `Water_CC13_2cm` is the complete calculation-density replacement region. It
  should include the entire intended two-centimetre phantom layer, including
  chamber body, cavity, wall, electrode, cable, and image artefact within the
  phantom, while excluding external air. It must have a closed planar contour
  on every CT slice that will be replaced; an internal missing contour slice
  is rejected rather than interpolated.
- `Water_reference` contains only representative clean water away from the
  chamber, cable, lung/bone insert, gaps, exterior air, and artefact. It may be
  absent on individual target slices because those slices use the global
  reference median and are reported as fallbacks.

ROI names are exact and must each occur once. The two masks must not overlap.
Every contour must identify exactly one source CT SOP Instance UID through its
`ContourImageSequence`. The helper does not guess a slice from contour Z.

Monaco's measurement structure `Chamber_active` remains separate from the
density-replacement ROI. For the documented local research setup it is a
0.13 cm3 active volume positioned at 9 cm depth in both Lung and Bone cases.
The helper does not create, move, or validate that ROI; after TPS
reassociation, verify that it lies inside the water-replaced region.

## Command

Install the package in the supported Python 3.12 environment, then use either
the installed entry point or the thin repository script:

```powershell
dicomxphits-replace-ct-layer-with-water `
  --ct-dir "C:\outside-repo\phantom\source-ct" `
  --rtstruct "C:\outside-repo\phantom\RTSTRUCT.dcm" `
  --target-roi "Water_CC13_2cm" `
  --reference-roi "Water_reference" `
  --output-dir "C:\outside-repo\phantom\derived-water-ct" `
  --confirm-non-patient-phantom
```

If the CT folder contains more than one series, add the explicitly reviewed
`--ct-series-instance-uid`. The output path must not exist and must not equal,
contain, or be inside the source CT directory. Source CT and RTSTRUCT files are
hashed and rechecked; they are never overwritten.

The command stops by default when it finds a QC warning. Review the warning,
the source contours, and its implication first. Only for a consciously accepted
non-patient research derivation, repeat the command with a different new output
path and:

```text
--accept-qc-warnings
```

That flag records acknowledgement; it does not declare the phantom, scanner,
ROI, or result clinically acceptable.

## Replacement and DICOM behavior

For each slice containing the target ROI:

```text
HU = stored value * RescaleSlope + RescaleIntercept
```

The helper uses the median HU inside `Water_reference` on that slice. If the
slice has no reference voxels, it uses the median across the complete reference
ROI and records that fallback. The chosen HU is converted back through that
target slice's slope and intercept, rounded to the nearest integer with
ties-to-even, and range-checked.

The initial implementation supports native, uncompressed, single-frame,
monochrome conventional CT Image Storage with 8- or 16-bit allocated samples.
Signed/unsigned representation, `BitsStored`, and `HighBit` are honored.
Compressed or encapsulated CT is rejected because decompressing and
re-encoding it cannot satisfy the contract that every outside-target allocated
sample byte remains unchanged.

The output retains study UID, frame UID, positions, orientations, spacing,
matrix, and ordering. It receives a new Series Instance UID and every slice
receives a new SOP Instance UID synchronized with file meta. `ImageType`,
series description, derivation description, creation times, and source-image
references identify the result as derived. The source SOP UIDs are never reused
for rewritten Pixel Data.

Axial and parallel oblique RTSTRUCT contours are projected in DICOM patient
coordinates. Supporting oblique rasterization here does not expand the
existing CT2PHITS frontend: that downstream frontend still accepts only its
documented axial HFS CT geometry.

## QC gates and output

Structural errors always stop. The initial review-oriented QC defaults warn
and require explicit acknowledgement for:

- fewer than 1,000 global reference voxels;
- reference median or 5th/95th percentile outside -200 to +200 HU;
- reference standard deviation above 100 HU;
- target contact with the image matrix boundary;
- target intersection with same-slice boundary-connected pixels below
  -500 HU; or
- the shortest patient-coordinate principal-axis extent of the occupied target
  outside 15 to 25 mm. The CT stack-normal extent is reported separately and
  is not assumed to be the layer thickness; or
- other than exactly one principal extent in the 15 to 25 mm range. A whole
  layer should be thin on one axis and extend across the phantom on the other
  two; a roughly 2 cm x 2 cm rod therefore stops as a QC warning.

These are preprocessing review gates, not treatment tolerances or scanner
commissioning limits.

A completed output contains:

- one derived `CT.####.dcm` file per source slice;
- `qc-report.json` with geometry, UIDs, ROI statistics, volume, per-slice
  replacement HU/stored values, fallback slices, warnings, and integrity
  checks;
- `qc-report.txt` with a concise human-readable summary; and
- `qc-comparison.png`, a representative 2 x 2 montage of before, after,
  absolute HU difference, and target/reference masks. Target boundaries are
  red and reference boundaries are green; CT display uses centre 0 HU and
  width 500 HU.

Reports do not read or emit patient demographic tags. If output creation fails
after its directory is created, `INCOMPLETE.txt` remains and that directory
must not be used or overwritten.

## Monaco and CT2PHITS handoff

The original RTSTRUCT still references the source CT SOP instances. This first
version intentionally does not rewrite RTSTRUCT or RTPLAN. Do not mix the
original RT objects with the derived series on the assumption that matching
geometry makes their references interchangeable.

For each Lung or Bone research case:

1. Review `qc-report.txt`, `qc-report.json`, and `qc-comparison.png`.
2. Import the derived CT as a new series in Monaco.
3. Create, copy, or reassociate structures and the plan according to the local
   research workflow.
4. Independently verify frame, registration, slice geometry, target layer,
   body/external-air boundary, insert location, isocentre, and plan association.
5. Verify `Chamber_active` separately inside the replaced water-equivalent
   layer.
6. Supply the derived CT explicitly to CT2PHITS only if the existing CT2PHITS
   geometry checks also pass.

Changing the chamber-containing target layer can intentionally change the
calculated density and dose within and downstream of that region. This tool
does not claim dose equivalence to the source CT and does not change beam-model
or absolute-dose calibration behavior.
