# Design: Integrate Safety UI into the Current Workflow

## Base and Port Strategy

The integration branch starts at PR #38 exact HEAD
`ecf474a05f3b37850b70c921de4d4c40e1c17a4d`. It will not merge, rebase, or
cherry-pick `feat/safety-ui-energy-guard` or
`fix/safety-ui-minimum-window-scroll`. Each accepted behavior will instead be
ported as a small current-tree edit after comparing its original parent diff.

This keeps PR #38's installer corrections in the exact tree used for later ZIP
validation while leaving PR #38 itself open, draft, and unchanged. The new
branch must not modify `install_offline.cmd`, either installer PowerShell
helper, or their tests unless a separately observed regression in the current
integration diff requires an approved decision.

## OpenSpec Record Integration

The earlier accepted archive
`2026-08-13-strengthen-6mv-safety-and-gui-clarity` will be restored verbatim as
historical evidence. Its accepted fixed-6-MV current specification will be
restored as the new `fixed-6mv-beam-model-safety` capability.

The current `guided-gui-workflow` specification contains newer PR #37 recovery
requirements that were added after the old branch split. The integration will
append the accepted fixed-model and log requirements and the newly approved
Help and minimum-page-access requirements to the current specification. It
must not replace the file with the older branch version.

This active change will remain active until implementation, automated checks,
required Windows GUI acceptance, and exact-HEAD offline artifact verification
are complete. At completion its accepted deltas will be promoted, its tasks
will be updated accurately, and it will be archived under the completion date.

## Fixed Public Beam-Model Guard

One package-owned identity will define the Elekta Precise public research
model as photon, nominal 6 MV, and fixed. The common workspace export path will
validate every beam that contributes an active treatment segment before
`write_outputs` creates the manifest or PHITS input path.

The validator will require `RadiationType` `PHOTON`, an explicit finite
positive 6 MV value at the first control point, and only normal DICOM
inheritance for omitted later values. Any explicit value change or unsupported
value fails closed. Successful evidence is additive in the segment manifest
and workspace-preparation summary.

The port in `prepare_3dcrt_workspace.py` must preserve both existing calls to
`bind_current_gantry_geometry_contract` and the current gantry-contract field
in the generation summary. It must not change geometry rendering, spectrum
bytes, or the order and meaning of current physics gates.

## Shared Model and Help Presentation

The fixed beam-model display and fixed nominal-energy statement will remain in
a common read-only header visible from CT2PHITS, Workspace, PHITS, Sumtally,
and RTDOSE.

The root window will have one `Help` menu with:

- `Web site`, which on an explicit user click requests the operating system's
  default browser for exactly `https://github.com/inata169/dicomxphits`;
- `About`, which displays the current package `__version__`, author
  `Hiroki Inata`, and account `inata169` in a local dialog.

GUI startup, page navigation, and opening About must not open a browser,
perform an update check, or make a network request. A browser-open failure will
produce a controlled local error rather than changing workflow state. Version
text will be derived from package metadata already owned by the package; this
change will not alter version metadata or tags.

## Minimum-Window Page Viewport

Only the page-content region between the common page heading and Activity log
will be placed inside a `tk.Canvas` with a vertical `ttk.Scrollbar`. The page
container will be the Canvas window; its width will follow the viewport, and
its scrollregion will follow page-content size. Selecting another page will
return that viewport to its top after layout settles.

The Activity log remains outside the Canvas and retains its own scrollbar and
latest-entry auto-scroll. Its height may increase from two to three text rows
as previously approved.

At `1120 x 720`, vertical scrolling and normal keyboard traversal must reach:

- CT2PHITS: `Run CT2PHITS` and the existing-case entry action;
- Workspace: `Prepare workspace`;
- PHITS: `Run PHITS segments`;
- Sumtally: `Generate Sumtally` and `Run Sumtally`;
- RTDOSE: `Create DICOM RT Dose`, `Prepare RTDOSE`, and `Run RTDOSE` according
  to the applicable mode and state.

Reachability is independent of enablement. A reachable disabled action stays
disabled until all current safety and provenance gates pass.

## Stage-Gating Boundary

The integration must not change the semantics of:

- `StageExecutionGuard` and mutual exclusion while a stage runs;
- tool-profile readiness for each stage;
- `rtdose_action_enabled` and current Prepare/Run evidence;
- non-persistent overwrite permission;
- existing-case mode disabling CT2PHITS, Workspace Prepare, PHITS, and other
  inappropriate individual actions;
- recovery inspection, downstream-only suffix execution, and the protected
  `Create DICOM RT Dose` action.

GUI layout code will only change widget parenting, viewport sizing, common
presentation, and page-navigation scroll position. Existing action callbacks
and action-button dictionary keys will remain bound to the current logic.

## Validation Strategy

Automated validation will cover:

- supported and rejected synthetic beam-model matrices;
- validation before PHITS input output and additive evidence;
- fixed model text with no energy selector;
- Help menu labels, exact URL dispatch through a mocked browser opener, About
  content, and absence of startup browser invocation;
- one common scrollable page viewport, Activity log separation, page-top
  reset, and all five pages' action areas being descendants of that viewport;
- unchanged stage-gating and recovery behavior;
- unchanged IEC gantry anchors, PLAN fraction factor, recovery evidence, and
  PR #38 offline installer regressions.

Because pixel rendering and display scaling are environment-dependent, a
Windows 11 manual acceptance at `1120 x 720` remains required after automated
checks. It will navigate and scroll all five pages and inspect focus and action
reachability without launching external scientific tools.

## Offline Artifact Order

The offline ZIP will be rebuilt only after focused tests, the full public
checks, strict OpenSpec validation, and diff review pass on one exact
integration commit. The manifest must record that exact HEAD. Acceptance uses
a new empty extraction directory and must not overwrite the prior successful
installation folder. Any UAC installation and visual inspection remain
human-operated.

## Unchanged Boundaries

This change does not add 10 MV, an energy selector, FFF validation,
`PrimaryFluenceModeSequence` interpretation, IMRT, dynamic MLC, VMAT, clinical
claims, new dose semantics, or new coordinate behavior. It does not run or
inspect protected real data or external scientific outputs.
