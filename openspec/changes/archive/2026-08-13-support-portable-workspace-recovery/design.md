# Design: Existing Workspace Recovery

## Observed failure

The diagnostic workspace was produced on one Windows computer and transferred
to another. Its summaries retained successful stage values and absolute paths
under the former workspace root. On the receiving computer:

- both Sumtally summaries were readable and reported success;
- both RTDOSE summaries were readable and reported success;
- the recorded coordinate-corrected RTDOSE path resolved under the former
  computer's workspace;
- that output did not exist at the recorded path or anywhere in the selected
  current workspace; and
- the GUI surfaced repeated existing-summary errors without explaining that
  the evidence was historical or how to recover it.

No patient data, DICOM identifiers, machine-specific path, calculation output,
or licensed distribution content is recorded in this change.

The same-computer restart failure additionally showed that a missing internal
Sumtally summary was rendered as a raw `Errno 2` path and that Workspace Prepare
remained available after PHITS completion. The recovery design treats those as
workflow-state problems. The user is not expected to understand summary file
names or reconstruct three frozen-handoff paths.

## Explicit import rather than implicit path repair

Recovery begins only after the user explicitly selects an existing workspace.
It is not part of CT2PHITS new-workspace creation, does not search the computer,
and does not silently rewrite JSON.

The recovery inspector compares the recorded workspace root with the selected
current root. A recorded absolute path is eligible for relocation only when it
is demonstrably below the recorded root. Its candidate is the same relative
path below the current root. Paths outside the recorded root are external and
remain unresolved until the user supplies the applicable current-computer
setting through an existing validated input.

This prevents a copied summary from redirecting validation to an unrelated
local file and prevents basename-only or drive-wide discovery.

For a standard local tool profile, the GUI may derive exactly one CT2PHITS
handoff candidate from the selected 3D-CRT workspace name: a terminal
`-3dcrt` suffix maps to `-ct2phits` below the validated RT-PHITS `work`
directory. The candidate is accepted only when its completion summary and the
documented `RTPLAN.dcm`, `CT/CT000001.dcm`, and `DATfiles` artifacts validate.
This is a deterministic bounded derivation, not a directory search. If it does
not validate, recovery reports that one CT2PHITS workspace selection is still
required; it never guesses three independent paths.

## Evidence classes

Inspection classifies evidence rather than treating all `success` strings as
current success:

- **Current and verified**: the required artifact exists below the current
  workspace, every digest required by its evidence class is recorded and
  matches, and its stage-specific provenance remains valid.
- **Historical and recoverable**: the summary records a prior success, but a
  current path binding or downstream artifact is missing; verified upstream
  evidence is sufficient to regenerate the affected stage.
- **Invalid or incomplete**: a required artifact is missing, has a digest
  mismatch, escapes the workspace boundary, or lacks the evidence required to
  establish safe recovery.

Legacy evidence that predates a required digest is not upgraded by inference.
It follows the existing stage-specific reconstruction gate when one exists or
is rejected with a controlled explanation.

## Recovery boundary

Verified PHITS segment outputs are expensive immutable inputs for this
workflow. Recovery may start at Sumtally Generate only when the manifest and
complete active-output set validate at their relocated in-workspace paths and
a recorded SHA-256 for every active segment output matches its current bytes.
Missing digest evidence for any active segment output fails closed; it is not
reconstructed or accepted from path existence alone. Once those gates pass,
recovery MUST NOT require PHITS execution merely because the workspace root
changed.

Copied Sumtally and RTDOSE summaries remain historical. Fresh downstream
execution must keep the existing new-or-byte-changed output requirements. If a
conflicting downstream summary or artifact would prevent a fresh result from
being proved, an explicitly confirmed recovery action moves it to
`recovery_history/<unique-recovery-id>/` below the selected current workspace.
The history directory must be new, collision-safe, preserve each moved item's
workspace-relative layout, and contain a manifest with the original relative
path, preserved relative path, size, and SHA-256. Recovery fails without
starting an external tool if any required move or manifest write fails. It
must not delete evidence, overwrite an existing history directory, move PHITS
segment outputs, or accept unchanged bytes as a fresh result.

Local PHITS and RT-PHITS installation paths are not portable provenance. The
receiving computer uses its separately validated GUI tool profile. Changing
those executable paths does not change the segment physics evidence, but every
external execution still uses and records the current validated executable
role.

## GUI model

The existing-workspace path must be distinct from fields whose Browse behavior
constructs a proposed new workspace. After inspection, the GUI displays the
highest verified stage, the first stage needing recovery, a concise reason,
and one safe next action. Historical success is not rendered as current
Completed state.

When the inspector proves that PHITS segment results are reusable, the primary
RTDOSE action is `Create DICOM RT Dose`. The GUI runs only the required suffix
of this sequence: Sumtally Generate, Sumtally Run, RTDOSE Prepare, and RTDOSE
Run. It stops on the first failed adapter and keeps the existing adapter gates
authoritative. Workspace Prepare and PHITS Segment Execution are disabled in
this mode. A completed conversion displays the accepted `.fixed.dcm` path and
labels it as DICOM patient coordinates.

Recovery copy uses a contextual confirmation that states which downstream
artifacts will be preserved and that PHITS results will not be changed. This
confirmation is the non-persistent recovery permission; users do not need to
discover a global overwrite checkbox. Error dialogs have a short outcome,
safety statement, and next action. Raw exception details remain available in
the activity log but are not the only message in a modal dialog.

The existing non-persistent downstream overwrite permission remains explicit,
but the user is not expected to infer recovery solely from a red
`stage output already exists` message. Invalid evidence keeps dependent actions
disabled. Before permission is accepted, the GUI identifies that only
historical Sumtally and RTDOSE material will move into workspace-local recovery
history and that PHITS segment outputs will remain unchanged.

## Safety and validation

Implementation must not alter PHITS physics, segment output bytes, public dose
factors, MU, normalization, DICOM geometry, coordinate correction, or PLAN
semantics. It must not add external paths or real results to the repository.
Automated validation uses copied temporary synthetic workspaces, changed root
paths, fake runners, and synthetic DICOM only.

Real transferred-workspace execution remains a separate human-authorized
manual validation after implementation approval. It is not required to approve
this proposal and is not authorized by this document.
