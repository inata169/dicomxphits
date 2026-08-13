# Support Existing Workspace Recovery

## Why

A human-operated Windows end-to-end diagnostic on 2026-08-04 selected a
completed non-patient research workspace that had been calculated on another
computer and transferred through external storage. The copied Sumtally and
RTDOSE summaries still reported success, but their recorded absolute paths
pointed to the original computer. The guided GUI rejected attempts to
regenerate existing stages as red validation failures, while the RTDOSE state
could still appear completed even though the recorded coordinate-corrected
output did not exist on the current computer.

Moving a long-running Monte Carlo workspace between computers is a legitimate
research workflow. The current public contract does not define how to rebind
portable in-workspace evidence, distinguish historical success from current
availability, or recover downstream stages without rerunning verified PHITS
segment calculations.

A second human-operated diagnostic on 2026-08-13 reproduced the same usability
failure after restarting the GUI on the original computer. Case paths and the
frozen CT2PHITS handoff had to be entered again, a missing internal
`sumtally_generation_summary.json` was exposed as a raw operating-system error,
and the GUI offered only an OK button. The user could also select Workspace
Prepare after the expensive PHITS stage, even though that is not a recovery
action. Existing-workspace recovery therefore needs to be the normal restart
path, not a relocation-only advanced feature.

## What Changes

- Add an explicit existing-workspace inspection and recovery path for both
  same-computer restart and bounded relocation. It remains separate from new
  CT2PHITS and new workspace preparation.
- Let the user select one existing 3D-CRT workspace and automatically restore a
  validated frozen CT2PHITS handoff when its deterministic standard-profile
  workspace is available. Never search the drive or accept an unvalidated
  candidate.
- Rebind only paths that were recorded below the former workspace root to the
  same relative locations below the explicitly selected current workspace.
- Revalidate relocated artifacts using the manifest, recorded SHA-256 evidence,
  current file existence, and stage-specific provenance before accepting them.
- Never guess, search for, or automatically rebind paths that were outside the
  former workspace, including licensed tool installations.
- Allow verified PHITS segment outputs to support fresh Sumtally and RTDOSE
  evidence on the current computer without rerunning PHITS.
- Before fresh downstream execution, move conflicting historical Sumtally and
  RTDOSE summaries and artifacts into a new collision-safe workspace-local
  recovery-history directory, record their relative paths and SHA-256 values,
  and never delete or overwrite them silently.
- Treat copied downstream summaries as historical evidence until their current
  artifacts and bindings are validated; do not show RTDOSE as Completed solely
  because a copied summary contains a success value.
- Present a guided recovery state and one safe next action instead of requiring
  the user to interpret repeated existing-output validation errors.
- When verified PHITS outputs are reusable, provide one primary action to
  regenerate only the required Sumtally and RTDOSE stages and create the final
  coordinate-corrected DICOM RT Dose. Do not rerun Workspace Prepare or PHITS.
- Disable new-case preparation and PHITS actions while a verified existing case
  is open. Keep individual stage replacement in a clearly subordinate advanced
  path.
- Replace raw exception/path-only dialogs with a plain-language explanation of
  what is missing, what expensive evidence remains safe, and the next safe
  action. Present the final DICOM patient-coordinate output path on completion.
- Preserve fail-closed freshness, digest, DICOM semantic, geometry, dose, MU,
  normalization, and fixed-field 3D-CRT boundaries.

## Impact

- New capability: `portable-workspace-recovery`
- Affected capabilities: `guided-gui-workflow`, `rtdose-dicom-semantics`
- Likely affected runtime: GUI workspace selection and stage-state logic,
  workspace path/evidence resolution, Sumtally recovery, and RTDOSE evidence
  restoration
- Likely affected tests: synthetic relocated-workspace, GUI state, Sumtally
  provenance, and RTDOSE provenance tests
- Affected documentation: Windows GUI workflow and workspace transfer guidance
- Unchanged boundaries: PHITS physics and segment results, public machine
  model, dose factor, MU and normalization semantics, DICOM coordinate meaning,
  supported fixed-field 3D-CRT scope, and clinical claims

## Approval Status

The primary user explicitly approved this expanded proposal on 2026-08-13.
Repository implementation with synthetic data and fake runners is approved.
Real external-tool execution remains limited to the separately requested
human-operated non-patient GUI test; the agent does not execute or inspect that
external dataset.
