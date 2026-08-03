# Repair RTDOSE GUI Reprepare Recovery

## Why

The human maintainer approved the guided RTDOSE Prepare/Run state behavior on
2026-08-03, and pull request #16 implemented it, but the required OpenSpec
change record was omitted before that pull request was merged. A delayed Codex
review identified both that process defect and a recovery defect: after a
successful RTDOSE Prepare, rerunning upstream Sumtally can invalidate the
preparation evidence, while the GUI still disables Prepare and prevents the
user from following the adapter's instruction to prepare again.

## What Changes

- Record the already approved Not run, Prepared, and Completed RTDOSE GUI
  states and their button behavior in the guided GUI contract.
- Keep unreadable or unsuccessful summaries from claiming a successful state.
- When RTDOSE is Prepared, let the user's explicit, non-persistent overwrite
  selection re-enable Prepare so stale upstream evidence can be recovered by
  rerunning preparation.
- Refresh the action buttons immediately when overwrite permission changes.
- Add synthetic tests and align the public guidance and durable status record.

## Impact

- Affected capability: `guided-gui-workflow`
- Affected runtime: `src/dicomxphits/gui.py`
- Affected tests: `tests/test_gui.py`
- Affected documentation: RTDOSE GUI guidance and project status
- Unchanged boundaries: PHITS physics, calculated dose, MU, normalization,
  machine model, DICOM semantics, fixed-field 3D-CRT scope, and external-tool
  execution

## Approval History

The human maintainer explicitly approved implementation of the RTDOSE GUI
guidance before pull request #16. This change records that accepted behavior
after the missing OpenSpec record was identified. The recovery correction is a
minimal bug fix that restores the adapter's existing documented requirement to
rerun RTDOSE Prepare when its upstream binding has changed.

## Completion

The accepted requirement was promoted into the current guided GUI
specification and this change was archived on 2026-08-03. Focused and full
synthetic/mock validation passed, no external tool or real DICOM was executed,
and the delayed pull request #16 review threads received corrective commit and
validation evidence.
