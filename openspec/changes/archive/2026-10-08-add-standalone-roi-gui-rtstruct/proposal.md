# Add a standalone ROI selection GUI with RT Structure mapping

## Why

The independent PHITS ROI statistics script currently requires explicit
command-line selectors and a same-grid NPZ mask for Structure statistics.
Users need a visual way to select completed cases and regions. A Structure
name in an RT Structure Set does not by itself locate that Structure on the
PHITS mesh: the accepted coordinate chain also requires an RT Plan isocenter,
the matching CT series, and validated mesh geometry.

The existing GUI's post-completion Structure r.err evaluator uses a different
population and workflow-authority contract. The standalone report must stay
separate from that evaluator.

## What Changes

- Add a separate desktop GUI for the independent statistics tool. It presents
  explicit file/member selectors for a case directory or ZIP, official
  combined dose, paired combined `_err.out`, any retained co-located dose,
  generation/execution summaries, and canonical segment manifest. It can
  show several explicitly added cases in one table without auto-selecting an
  ambiguous candidate.
- Retain the existing sphere analysis, with centre `(0, 0, 0)` cm and radius
  `0.25 cm` as editable defaults. Show sampling Points, analytic sphere
  volume, native Grid Points, and grid volume as separate values.
- Add an explicit RT Structure path: select one RT Structure Set, one RT Plan,
  and the matching CT series/reference for the case. Require the user to
  select a unique ROINumber; display its ROIName, such as `Chamber`, only as a
  label. Validate identities and coordinate geometry before deriving a
  transient Boolean mask on the exact PHITS grid. No contour is inferred from
  a name or from PHITS output alone.
- Use the existing standalone one-fraction dose/r.err definitions for both
  sphere and Structure populations. In the GUI, show mean dose prominently
  and label the existing Total Dose scalar as `sum of selected cell doses
  (cGy)` with a grid-dependence explanation. Do not relabel it a Structure
  dose, energy integral, point dose, or course dose.
- Keep reports optional, explicit, outside source cases and the repository,
  new-only, and free of automatic DICOM identifiers and absolute source paths.
  Only synthetic DICOM/PHITS fixtures enter tests or the public tree.

## Impact

- New capability: `standalone-roi-gui-rtstruct`.
- Expected implementation: a separate `tools/` GUI entry point and bounded
  RT Structure-to-PHITS-grid adapter with focused synthetic tests and usage
  documentation. The exact file split is an implementation detail.
- This expands the previously approved standalone tool's input contract to
  explicitly selected DICOM geometry. It does not change the existing GUI,
  PHITS/Sumtally execution, RTDOSE conversion, physics, dose normalization,
  or clinical claims.
- Real RT Structure inspection and any subsequent local validation remain
  read-only and outside the public repository. PHITS and other external
  calculation tools are never launched by this GUI.

## Approval

Status: approved by the primary user on 2026-10-08 for implementation of this
proposal and its coordinate contract. The earlier standalone change remains
active until its own PR decision and completion cleanup are resolved.
