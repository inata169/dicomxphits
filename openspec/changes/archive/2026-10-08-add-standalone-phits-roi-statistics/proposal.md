# Add standalone PHITS ROI statistics

## Why

Users need to inspect existing combined PHITS dose and statistical-error
outputs from workspaces produced by dicomxphits v1.0.3 and v1.1.1 without
starting the GUI, converting RTDOSE, or rerunning an external tool. The
existing GUI Structure evaluator has a different population, presentation,
and evidence contract and does not provide these standalone dose summaries.

The requested sphere example distinguishes radius 0.25 cm, 81 points on a
centre-anchored 1 mm sampling lattice, and sampling volume 0.081 cm3 from
the analytic sphere volume, approximately 0.06544985 cm3. The user approved
this distinction. The user approved this implementation proposal on
2026-10-08, including its statistical and input contracts.

## What Changes

- Add one independently runnable Python 3.12 script, using NumPy and the
  standard library, for explicitly selected combined dose/error pairs in
  directories or ZIP archives. It will not require an installed dicomxphits
  package or a particular GUI version.
- Support a sphere in PHITS isocenter-relative coordinates and a named,
  externally supplied Boolean Structure mask on the same PHITS grid.
- Report analytic sphere volume, sampling points and volume, native grid
  points and volume, native-grid dose summaries, and voxel r.err summaries.
- Label Total Dose as a voxel-dose sum, define Standard dev as spatial
  population standard deviation, and avoid claiming an exact statistical
  uncertainty for an ROI mean from voxel errors alone.
- Read and validate saved normalization evidence before reporting cGy.
  Preserve the input one-fraction dose basis without multiplying MU,
  calibration factors, or planned fractions again.
- Provide console output and explicit new-only CSV/JSON reports, including
  source digests, statistical definitions, counts, and diagnostic statuses.
- Provide focused synthetic tests and usage documentation. A batch input
  manifest will allow one selected sphere or Structure mask per case and
  multiple explicitly listed cases in one invocation.

## Impact

- New capability: `standalone-phits-roi-statistics`.
- Planned implementation files: `tools/phits_roi_stats.py`,
  `tests/test_phits_roi_stats.py`, and `docs/phits-roi-statistics.md`.
- Existing GUI, execution, recovery, RTDOSE, physics, normalization, and
  Structure-evaluation contracts remain unchanged. The new report has no
  authority over completion, recovery, stopping, or downstream eligibility.
- No DICOM input is needed or read. A Structure name alone is insufficient:
  a coordinate-bound mask is required, and generating it from DICOM is
  outside this proposal.
- Compatibility is limited to explicitly validated output formats, initially
  PHITS 3.35 T-Deposit xyz/xy combined output with `isumtally=2`. GUI version
  labels are not a substitute for format validation.
- Only synthetic fixtures and anonymized examples may enter the public
  tree. Local calculations, institution data, identifiers, and personal
  paths remain outside it.

## Approval and completion

Status: implementation approved on 2026-10-08. The standalone script and
synthetic validation were completed on the same feature branch.

After approval, implementation must pass the acceptance scenarios and all
repository checks before accepted deltas are promoted and this change is
archived. Real-output checks require explicitly selected inputs and an
authorized report destination; they must not invoke PHITS or Sumtally.
Unresolved input identity or a missing Structure mask must be reported,
not silently replaced with another dataset or a sphere.
