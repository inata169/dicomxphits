# Tasks

## 1. Approval and detailed design

- [ ] 1.1 Obtain explicit human approval of this proposal before runtime work.
- [x] 1.2 Define collision-safe workspace-local recovery history for
  conflicting downstream artifacts without weakening fresh-output validation.
- [ ] 1.3 Inventory every summary path field consumed by PHITS, Sumtally, and
  RTDOSE recovery and classify it as workspace-internal or external.

## 2. Portable evidence inspection

- [ ] 2.1 Add a read-only relocated-workspace inspector that maps only paths
  below the recorded root to the same relative path below the selected root.
- [ ] 2.2 Revalidate required existence, manifest identity, stage provenance,
  and a recorded matching SHA-256 for every active PHITS segment output
  without searching outside the selected workspace.
- [ ] 2.3 Record current, historical-recoverable, and invalid evidence states
  with controlled reasons.

## 3. Safe downstream recovery

- [ ] 3.1 Permit relocated PHITS segment outputs to seed a fresh Sumtally
  Generate stage without rerunning PHITS only when every active output has a
  recorded matching SHA-256.
- [ ] 3.2 Move conflicting historical downstream artifacts into a new
  workspace-local recovery-history directory, record their relative paths and
  SHA-256 values, and keep new-or-byte-changed validation authoritative.
- [ ] 3.3 Generate current-root Sumtally and RTDOSE summaries and revalidate the
  existing PLAN-dose provenance and final coordinate-corrected output.
- [ ] 3.4 Reject missing, changed, external, or ambiguously rebound evidence
  before dependent external execution.

## 4. Guided GUI recovery

- [ ] 4.1 Provide an explicit existing-workspace selection path distinct from
  new-workspace Browse behavior.
- [ ] 4.2 Display verified, recovery-needed, and invalid states with the first
  safe next action and without relying on color alone.
- [ ] 4.3 Require explicit non-persistent permission before replacing downstream
  summaries or preserving conflicting outputs for recovery.
- [ ] 4.4 Revalidate the current final RTDOSE artifact before displaying
  Completed.

## 5. Synthetic validation and documentation

- [ ] 5.1 Add synthetic tests for root relocation, safe relative rebinding,
  external-path rejection, missing artifacts, missing active-segment digest
  evidence, and digest mismatch.
- [ ] 5.2 Add fake-runner tests proving PHITS is not rerun and stale unchanged
  Sumtally or RTDOSE output is not accepted.
- [ ] 5.3 Add GUI tests for explicit existing-workspace selection, historical
  summary handling, recovery guidance, and final-output disappearance.
- [ ] 5.4 Document the supported Windows transfer and recovery workflow without
  machine-specific paths or clinical claims.

## 6. Completion

- [ ] 6.1 Run focused synthetic checks and all public validation required by
  `AGENTS.md`.
- [ ] 6.2 Complete only an explicitly approved external non-patient manual
  check, or record it accurately as unverified.
- [ ] 6.3 Promote accepted deltas, archive the completed change, and validate
  the resulting OpenSpec tree before completion reporting.
