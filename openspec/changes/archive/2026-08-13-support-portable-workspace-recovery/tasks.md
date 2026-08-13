# Tasks

## 1. Approval and detailed design

- [x] 1.1 Obtain explicit human approval of this proposal before runtime work
  (approved 2026-08-13, including same-computer restart recovery).
- [x] 1.2 Define collision-safe workspace-local recovery history for
  conflicting downstream artifacts without weakening fresh-output validation.
- [x] 1.3 Inventory every summary path field consumed by PHITS, Sumtally, and
  RTDOSE recovery and classify it as workspace-internal or external.

## 2. Portable evidence inspection

- [x] 2.1 Add a read-only relocated-workspace inspector that maps only paths
  below the recorded root to the same relative path below the selected root.
- [x] 2.2 Revalidate required existence, manifest identity, stage provenance,
  and a recorded matching SHA-256 for every active PHITS segment output
  without searching outside the selected workspace.
- [x] 2.3 Record current, historical-recoverable, and invalid evidence states
  with controlled reasons.

## 3. Safe downstream recovery

- [x] 3.1 Permit relocated PHITS segment outputs to seed a fresh Sumtally
  Generate stage without rerunning PHITS only when every active output has a
  recorded matching SHA-256.
- [x] 3.2 Move conflicting historical downstream artifacts into a new
  workspace-local recovery-history directory, record their relative paths and
  SHA-256 values, and keep new-or-byte-changed validation authoritative.
- [x] 3.3 Generate current-root Sumtally and RTDOSE summaries and revalidate the
  existing PLAN-dose provenance and final coordinate-corrected output.
- [x] 3.4 Reject missing, changed, external, or ambiguously rebound evidence
  before dependent external execution.

## 4. Guided GUI recovery

- [x] 4.1 Provide an explicit existing-workspace selection path distinct from
  new-workspace Browse behavior.
- [x] 4.2 Display verified, recovery-needed, and invalid states with the first
  safe next action and without relying on color alone.
- [x] 4.3 Require explicit non-persistent permission before replacing downstream
  summaries or preserving conflicting outputs for recovery.
- [x] 4.4 Revalidate the current final RTDOSE artifact before displaying
  Completed.
- [x] 4.5 Restore the standard frozen CT2PHITS handoff from one bounded,
  deterministic candidate and otherwise request one handoff workspace.
- [x] 4.6 Provide one primary Create DICOM RT Dose action that runs only the
  required downstream suffix and keeps Workspace Prepare and PHITS disabled.
- [x] 4.7 Replace raw missing-summary dialogs with controlled recovery guidance
  and display the final DICOM patient-coordinate output path.

## 5. Synthetic validation and documentation

- [x] 5.1 Add synthetic tests for root relocation, safe relative rebinding,
  external-path rejection, missing artifacts, missing active-segment digest
  evidence, and digest mismatch.
- [x] 5.2 Add fake-runner tests proving PHITS is not rerun and stale unchanged
  Sumtally or RTDOSE output is not accepted.
- [x] 5.3 Add GUI tests for explicit existing-workspace selection, historical
  summary handling, recovery guidance, and final-output disappearance.
- [x] 5.4 Document the supported Windows transfer and recovery workflow without
  machine-specific paths or clinical claims.

## 6. Completion

- [x] 6.1 Run focused synthetic checks and all public validation required by
  `AGENTS.md`.
- [x] 6.2 Record the explicitly requested external non-patient Windows GUI
  check as not run by the agent and awaiting the human operator after restart.
- [x] 6.3 Promote accepted deltas, archive the completed change, and validate
  the resulting OpenSpec tree before completion reporting.
