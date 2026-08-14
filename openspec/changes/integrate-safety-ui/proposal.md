# Integrate Safety UI into the Current Workflow

## Why

The installed offline GUI correctly represents source HEAD `00352a7`, but that
source does not contain the separately retained fixed-6-MV safety/UI work at
`af87da3` or the minimum-window scrolling fix at `85a8d78`. Those commits are
based on the older `ac043ca` tree, while current `main` includes the accepted
PR #37 gantry geometry, PLAN course-dose, RTDOSE recovery, GUI state, tests,
and OpenSpec contracts. Merging either old branch or cherry-picking it without
review would make those current contracts difficult to preserve and audit.

The earlier approved 6 MV OpenSpec records are also absent from the current
specification tree. In addition, the requested Help menu and package-version
display were not implemented by `af87da3`: that commit used static header text
and explicitly prohibited browser launch and version-display changes. The
current integration therefore needs a reviewed specification for the exact
Help and minimum-window behavior before runtime work begins.

## What Changes

- Manually port the previously approved fixed Elekta Precise nominal 6 MV
  photon compatibility guard into the current public workspace-preparation
  path without merging or cherry-picking either old GUI branch.
- Restore the accepted fixed-6-MV OpenSpec archive and current capability
  specification, and integrate its accepted GUI requirements into the current
  recovery-aware guided GUI specification without replacing newer content.
- Keep the fixed beam-model identity visible in the shared GUI while adding a
  `Help` menu whose explicit `Web site` action opens only the exact public
  repository URL and whose `About` action displays the current package version
  and `Hiroki Inata (inata169)`.
- Add no startup network access, update check, background browser launch, or
  selectable energy/model control.
- Put only the current workflow page region in a vertically scrollable
  viewport. Keep the shared Activity log outside that viewport, reset a newly
  selected page to its top, and make the primary action area of all five pages
  reachable at the documented `1120 x 720` minimum window.
- Preserve the current busy-state, tool-readiness, overwrite, RTDOSE state,
  existing-case recovery, and upstream-locking gates exactly; reachability
  MUST NOT enable an action that current safety state disables.
- Add synthetic and source-structural regression coverage, then require a
  Windows manual layout check without running real PHITS-related tools or
  loading real DICOM.
- Rebuild the offline ZIP only after focused and full repository validation
  succeeds, and bind its manifest to the exact integration HEAD.

## Impact

- Affected runtime:
  - `src/dicomxphits/gui.py`
  - `src/dicomxphits/prepare_3dcrt_workspace.py`
  - new package-owned project and beam-model identity modules
  - additive constants in `src/dicomxphits/public_spectrum.py`
- Affected tests:
  - GUI, workspace preparation, public beam-model, and rectangular-geometry
    synthetic tests
  - focused current gantry, course-dose, recovery, stage-gating, and offline
    installer regression suites
- Affected capabilities:
  - new `fixed-6mv-beam-model-safety`
  - existing `guided-gui-workflow`
- The integration branch is based on PR #38 exact HEAD `ecf474a`; PR #38 and
  its installer files remain unchanged by this change.
- PR #37 IEC gantry geometry, DICOM voxel mapping, PLAN fraction scaling,
  RTDOSE recovery, evidence contracts, and stage gating remain authoritative.
- Spectrum bytes, source and accelerator physics, aperture limits, dose
  factors, MU and Sumtally normalization, DICOM coordinates and meaning,
  package version metadata, tags, and clinical claims are unchanged.
- Automated work uses only synthetic inputs and fake or mock runners. Real
  PHITS, Sumtally, phits2dicom, GPR, real DICOM, and protected results remain
  outside this change.

## Approval Status

The fixed-6-MV guard and its original shared presentation were approved and
implemented on the retained branch on 2026-08-13, but were never integrated
into current `main`. The primary user approved this proposal and its delta
specifications on 2026-08-15 before runtime implementation.
