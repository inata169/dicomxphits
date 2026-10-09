# dicomxphits v1.1.2 Release Notes

Status: published on 2026-10-09 as an experimental source release for
education and research evaluation.
Release: [v1.1.2](https://github.com/inata169/dicomxphits/releases/tag/v1.1.2).
This release is for education and research with authorized non-patient
phantom data. It is not clinical commissioning, patient QA, vendor
certification, or a claim of physical dose accuracy.

## Changes since v1.1.1

- The independent PHITS ROI statistics GUI (`run_phits_roi_stats_gui.bat`)
  provides a separate interface for inspecting a completed Sumtally dose and
  error pair. It does not change the guided calculation workflow.
- The guided CT2PHITS page offers linked Axial, Coronal, and Sagittal previews.
  Users can select an axis-aligned CT box manually by two corners or by source
  pixel and slice indices. The source DICOM series is not overwritten.
- CT2PHITS coarse graining accepts equal positive X/Y factors and a Z factor
  from 1 through 4; the default remains `8 8 2`. The GUI warns about any
  incomplete high-end groups before conversion. The retained bounds are
  recorded, and generated grid dimensions and every material assignment are
  checked against the frozen CT and conversion table before downstream use.
- The preview samples large CT volumes within a bounded display memory budget
  so that a typical several-hundred-slice series can be inspected. The
  conversion still reads the selected full-resolution CT data.
- English user documentation covers CT clipping and the independent ROI GUI.
  Package metadata and Help → About report version 1.1.2.

Clipping keeps one axis-aligned box. Objects inside that box are retained; it
does not perform automatic segmentation. Coarse graining averages source HU
detail and may change representation of boundaries. The user must inspect the
retained region and intended structures before conversion. CT2PHITS and PHITS
are separately licensed, user-supplied external tools; they are not included
in the source release.

## Verification and release boundary

The integrated Windows / Python 3.12 candidate passed the full public suite
on 2026-10-09: **1565 passed, 15 skipped**. The focused version, installation,
CT clipping, and GUI suite passed **234 tests with 2 skips** before the review
correction; the focused review regression group then passed **18 tests**.
Source compilation, the public-tree audit (459 tracked files), and whitespace
checks passed.
The skips and a duplicate ZIP-member warning are not successful executions.
This validation uses synthetic and mock data, not patient data or real
external-tool execution of this release. A separately authorized non-patient
case produced geometry-only plots that the user reviewed, while PHITS transport
remained in progress. This does not establish completed end-to-end execution,
dose accuracy, convergence, or clinical suitability. Retain and evaluate the
case results only after the external calculation and downstream checks finish.

No custom Windows offline bundle is planned. Existing workspaces remain
subject to their recorded provenance and freshness checks. Use a separate
workspace for evaluation and retain the original inputs and results.
