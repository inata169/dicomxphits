# Prevent CT and Accelerator Geometry Overlap

## Why

The public fixed-field renderer currently creates the CT voxel-phantom wrapper
and the accelerator envelope as independent PHITS cells. A sufficiently large
or displaced CT volume can therefore extend into the transformed accelerator
head. PHITS can attempt geometry recovery and still leave the process with a
nominally successful return code and a dose output. That makes an invalid
overlap capable of appearing as a completed calculation and can change the
transported field shape.

This is not an SSD-versus-SAD setup error and cannot be solved safely by
assuming a maximum CT FOV. Whether an overlap occurs depends on the complete CT
volume, isocentre placement, and gantry transform. The geometry must be composed
from the actual transformed regions.

## What Changes

- Make the CT wrapper and transformed accelerator envelope mutually exclusive
  in every generated segment, with accelerator geometry taking precedence only
  inside its own envelope.
- Preserve the complete CT voxel phantom outside that envelope. Do not crop the
  CT, impose a fixed FOV limit, narrow the source cone, or change DICOM, SAD,
  SSD, jaw, MLC, material, transport, tally, MU, or normalization semantics as
  a substitute for the fix.
- Require PHITS segment completion evidence to contain an unambiguous,
  geometry-clean diagnostic summary. A nonzero `Number of lost particles`,
  `Number of geometry recovering`, or `Number of unrecovered errors` count is
  a failed segment even when PHITS returns zero and creates the expected tally.
- Advance the combined transport-geometry provenance contract from v4 to v5.
  Existing v4 or older PHITS results cannot be reused under v5, including
  cases whose recorded field or gantry values appear unaffected.
- Bind the approved absolute-dose factor to the renderer/transport-topology
  contract as well as the machine configuration and spectrum. The existing
  numerical factor may be reaccepted without a new full calibration only after
  reviewed evidence shows that the calibration geometry was non-overlapping
  and the old and corrected topology are transport-equivalent for that case.
  Until that evidence is accepted, absolute-dose preparation fails closed
  rather than silently carrying the factor into v5.
- Add synthetic tests spanning compact and large CT bounds, displaced
  isocentres, and nonzero gantry/collimator angles. Real DICOM and external
  scientific-tool comparison remain separately authorized work.

## Impact

- Affected capabilities: new `ct-accelerator-geometry-safety` capability and
  existing `iec-gantry-geometry`, `phits-segment-runtime`,
  `portable-workspace-recovery`, and `fixed-6mv-beam-model-safety`
  capabilities.
- Expected implementation areas after approval:
  `src/dicomxphits/prepare_ct_calibration.py`, the shared rectangular PHITS
  renderer, `src/dicomxphits/run_segments.py`, geometry provenance and recovery
  gates, and `src/dicomxphits/public_dose_contract.py`.
- Expected tests after approval: rendered-cell composition, transformed-volume
  geometry, PHITS diagnostic parsing and failure behavior, stale v4 recovery,
  and absolute-dose calibration binding, using synthetic data and fake or mock
  runners.
- Expected dose effect: overlapping cases are intentionally corrected and may
  change field shape and dose. Proven non-overlapping cases are expected to be
  transport-equivalent, but that expectation must be demonstrated before the
  existing absolute-dose factor is reaccepted.
- External execution: not authorized by this proposal. Running PHITS,
  RT-PHITS, Sumtally, phits2dicom, GPR, or real DICOM requires a separate
  explicit human approval.
- This change is proposal-only at this stage. No runtime, public physics, dose,
  DICOM, or calibration artifact is changed before implementation approval.
