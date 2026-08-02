# Guided CT2PHITS GUI Design

## Context

The current Tkinter GUI exposes six downstream commands and accepts manually
prepared CT2PHITS DATfiles. Pull request 3 added a separate Windows-only,
fail-closed CT2PHITS frontend that selects and snapshots CT and RT Plan inputs,
runs `RTphits_win.bat`, validates nine generated files, and prepares a frozen
handoff. The GUI should orchestrate that accepted adapter rather than reproduce
its logic or ask users to maintain two incompatible procedures.

The current local GUI defaults file is already ignored by Git and supports
flat string values. It can be extended compatibly for stable settings and
field-specific dialog history without tracking personal paths.

## Goals and Non-Goals

### Goals

- Make the accepted CT2PHITS frontend the first visible stage.
- Reduce repeated path entry while keeping every external path user-controlled.
- Make the frozen handoff visible and automatic after a successful frontend run.
- Keep each external stage separately gated and auditable.
- Improve hierarchy, readability, status feedback, keyboard use, and error
  recovery with the Python standard-library GUI stack.

### Non-Goals

- Discover DICOM datasets or external installations without a user-selected
  starting location.
- Run the complete workflow with one click or bypass per-stage safety gates.
- Persist the non-patient confirmation or overwrite permission.
- Add IMRT, VMAT, dynamic MLC, clinical claims, physics changes, or new DICOM
  interpretation.
- Add a cancel implementation that bypasses the accepted CT2PHITS timeout and
  process-tree evidence behavior.
- Add copyrighted faction logos, emblems, or other third-party visual assets.

## Decisions

### Reuse the Existing CLI Boundary

The GUI SHALL invoke `dicomxphits-run-ct2phits` as a subprocess with
`shell=False`. It SHALL pass the user-selected CT root, source RT Plan,
RT-PHITS root, new CT2PHITS workspace, optional series UID, timeout, and the
explicit non-patient confirmation. The GUI does not call
`ct2phits_win.exe`, inspect the RT-PHITS distribution, or duplicate frontend
validation.

### Distinguish the Two Workspaces

The interface will name the external workspace `CT2PHITS workspace` and the
downstream workspace `3D-CRT workspace`. The two paths have distinct state,
validation, and Browse history. This prevents the current ambiguous
`Workspace root` label from mixing the external and public-preparation stages.

### Safe Suggestions, Not Discovery

Selecting an RT Plan may populate an empty CT DICOM root with the selected
file's parent directory. When the RT-PHITS root or a remembered 3D-CRT
workspace parent is available, the GUI may propose new workspace names derived
from a filesystem-safe RT Plan filename stem. It does not recursively scan the
filesystem, read unrelated DICOM, or discover installed tools. Every suggested
path remains visible and editable before execution.

### Frozen Handoff

After the CT2PHITS execution summary reports completion, the GUI sets the
downstream RT Plan to `<ct2phits-workspace>/RTPLAN.dcm`, the CT reference to
`<ct2phits-workspace>/CT/CT000001.dcm`, and the DATfiles root to
`<ct2phits-workspace>/DATfiles`. It reuses those documented paths and does not
infer alternative outputs. Manual handoff controls remain available under an
advanced section for an already validated external workspace.

### Local Settings and Browse History

The ignored local GUI JSON retains backward-compatible flat path keys and adds
a versioned `browse_directories` object keyed by field name. Stable tool paths,
the RT-PHITS root, template path, optional machine configuration, and workspace
parents may be restored on launch. Dialog initial directories are resolved per
field. Writes use a temporary sibling file followed by replacement. Invalid or
unreadable settings fail safely to public defaults.

Case input values may update their field-specific Browse history, but explicit
confirmation and overwrite state always start false. The repository contains
only an example without populated absolute paths; personal paths remain in the
ignored local file.

### Workflow-Oriented Visual Hierarchy

The GUI will use themed `ttk` widgets and a restrained palette: deep navy base,
Federation-inspired blue primary actions, cyan focus accents, off-white text,
and distinct success, warning, and error colors with adequate contrast. The
layout groups case inputs, local tool settings, CT2PHITS handoff, stage actions,
and evidence rather than presenting one undifferentiated form. Advanced fields
are collapsed by default. No copyrighted insignia or image asset is required.

### Responsive Stage Feedback

External commands run off the Tk main loop so the window remains responsive.
While one stage is active, other stage actions are disabled and the active
stage shows a busy state. Completion, validation failure, return code, summary
path, and stderr are rendered with stage context. The GUI does not implement a
new external-process cancellation contract in this change.

## Risks and Mitigations

- Automatic path suggestions could look authoritative. Mark them as suggested,
  keep them editable, and run the existing validators before execution.
- Remembered personal paths could enter Git. Store them only in the existing
  ignored local file and keep tracked examples empty.
- Background execution could permit overlapping stages. Use a single active
  stage state and disable all stage actions until it resolves.
- Styling could reduce readability. Use semantic status colors, visible focus,
  keyboard traversal, scalable spacing, and tests of nonvisual state logic.
- The integrated flow could weaken the explicit execution gate. Keep the
  confirmation unchecked on every launch and invoke only the accepted CLI.

## Validation Strategy

- Unit-test path suggestions, settings migration and persistence, independent
  Browse histories, CT2PHITS command construction, frozen handoff, busy state,
  and error presentation with temporary paths and fake runners.
- Keep automated validation synthetic/mock only.
- Render the GUI locally with synthetic placeholder paths for visual inspection;
  do not run external tools or open real DICOM during ordinary development.
- Run the repository's focused and full public checks before completion.

## Migration Plan

Existing flat local defaults continue to load. New fields begin empty or use
safe public defaults. The advanced manual handoff preserves the accepted
downstream workflow for users with an already validated CT2PHITS workspace.
At approved completion, promote this delta to
`openspec/specs/guided-gui-workflow/spec.md` and archive the change.
