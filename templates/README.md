# Public RTDOSE Templates

This directory contains public-safe DICOM templates for local `phits2dicom`
validation.

## phits2dicom_rtdose_template.dcm

`phits2dicom_rtdose_template.dcm` is a sanitized RTDOSE template for the public
`dicomxphits` preparation workflow.

It is not a PHITS or RTphits official distribution file. It is derived from a
project-authored 10x10 validation RTDOSE file, then sanitized for public export:

- patient, institution, operator, and device identifiers are dummy values
- Study, Series, SOP, and Frame of Reference UIDs use a synthetic public UID
  root
- PixelData is zeroed so no calculated dose result is carried forward
- the RTDOSE overwrite tags required by `phits2dicom` are retained

Use it as the `--template-dicom` input when a local RTDOSE template is not
available:

```bash
dicomxphits-prepare-rtdose \
  --workspace-root "$WORKSPACE" \
  --template-dicom public_release/dicomxphits/templates/phits2dicom_rtdose_template.dcm \
  --ct-reference-dicom "$CT_REFERENCE_DICOM" \
  --phits-out "$WORKSPACE/sumtally/phits.out"
```

Do not place real patient DICOM, real clinical RTDOSE exports, PHITS execution
results, or official PHITS/RTphits sample files in this directory.
