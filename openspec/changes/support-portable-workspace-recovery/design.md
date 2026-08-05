# Design: Portable Workspace Recovery

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

## Explicit import rather than implicit path repair

Relocation recovery begins only after the user explicitly selects an existing
workspace. It is not part of CT2PHITS new-workspace creation, does not search
the computer, and does not silently rewrite JSON.

The recovery inspector compares the recorded workspace root with the selected
current root. A recorded absolute path is eligible for relocation only when it
is demonstrably below the recorded root. Its candidate is the same relative
path below the current root. Paths outside the recorded root are external and
remain unresolved until the user supplies the applicable current-computer
setting through an existing validated input.

This prevents a copied summary from redirecting validation to an unrelated
local file and prevents basename-only or drive-wide discovery.

## Evidence classes

Inspection classifies evidence rather than treating all `success` strings as
current success:

- **Current and verified**: the required artifact exists below the current
  workspace, its recorded digest matches when digest evidence exists, and its
  stage-specific provenance remains valid.
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
workflow. When the manifest, complete active-output set, and available digest
evidence validate at their relocated in-workspace paths, recovery may start at
Sumtally Generate and MUST NOT require PHITS execution merely because the
workspace root changed.

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
