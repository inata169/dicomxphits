# Tasks

## 1. Proposal and approval

- [x] 1.1 Record the requested non-patient phantom CT derivation capability as
  an OpenSpec proposal without inspecting real DICOM or changing runtime.
- [x] 1.2 Obtain human approval for the tool boundary, ROI semantics, derived
  DICOM identity, QC gates/defaults, and no-RTSTRUCT-rewrite decision before
  implementation. Approved by the primary user on 2026-08-31.

## 2. CT, RTSTRUCT, and pixel transformation

- [x] 2.1 Implement strict single-series CT selection and native Pixel Data
  validation without changing the existing CT2PHITS selector.
- [x] 2.2 Implement explicit RTSTRUCT reference/ROI validation and patient-
  coordinate closed-planar rasterization for axial and parallel oblique CT.
- [x] 2.3 Implement global/per-slice reference-water statistics, fallback, QC
  warning gates, inverse rescale, and signed/unsigned stored-bit updates.
- [x] 2.4 Prove samples outside the target mask remain byte-identical and
  source files remain unchanged.

## 3. Derived DICOM and evidence

- [x] 3.1 Implement fail-closed output creation with new series and SOP UIDs,
  synchronized file meta, preserved geometry, and derivation metadata.
- [x] 3.2 Implement post-write reread verification and incomplete-output
  marking.
- [x] 3.3 Produce identity-safe JSON/text QC reports and a representative
  before/after/difference/mask/contour PNG.

## 4. Public interface and documentation

- [x] 4.1 Add the console entry point and thin tool script with explicit
  non-patient and QC-warning acknowledgement flags.
- [x] 4.2 Document Lung/Bone usage generically, ROI construction, source versus
  derived RTSTRUCT references, Monaco reassociation, Chamber_active separation,
  and existing CT2PHITS geometry limits without committing real paths or data.

## 5. Synthetic validation and completion

- [x] 5.1 Add synthetic DICOM tests for the requested transformation, geometry,
  UID, representation, preservation, fallback, output, and safety cases.
- [x] 5.2 Run focused checks and all public checks required by `AGENTS.md`.
  The repository Python 3.12 environment passed 19 focused synthetic tests and
  the full suite passed with 938 tests and ten skips; compilation, public-tree,
  OpenSpec, Ruff, and diff checks also passed.
- [ ] 5.3 With separate human approval and explicit RTSTRUCT paths, run bounded
  local validation on the supplied non-patient Lung and Bone CT inputs and
  record results outside the repository; otherwise record it as unverified.
  A bounded read-only preflight confirmed consistent conventional geometry,
  matching CT/RTSTRUCT references, and valid required ROI names for both
  supplied exports. The clean-water references passed their HU-statistic gates,
  but both target ROIs were approximately two-centimetre-square rods rather
  than whole thin layers. The new dimensionality QC stopped both cases; target
  redraw, mask/QC revalidation, and derivation remain incomplete. No output was
  created.
- [ ] 5.4 Promote the accepted delta, archive the completed change, and strictly
  validate the resulting OpenSpec tree.
