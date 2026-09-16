# Tasks

## 1. Proposal and approval

- [x] 1.1 Inspect the accepted Structure-relative-error, workspace-output,
  Sumtally evidence, and RTDOSE preservation boundaries.
- [x] 1.2 Define a no-external-execution, no-summary-rewrite recovery design.
- [x] 1.3 Create the proposal, design, tasks, and requirement deltas without
  runtime or external-workspace changes.
- [x] 1.4 Strictly validate the complete proposal.
- [ ] 1.5 Obtain explicit human approval of the complete proposal before
  runtime implementation.

## 2. Read-only recovery preview

- [ ] 2.1 Implement explicit selection of one unchanged workspace and one
  preserved Sumtally staging directory without scanning or inference.
- [ ] 2.2 Validate guarded paths, canonical manifest, original summaries,
  wrapper/includes, retained and official dose identity, retained error,
  geometry, semantics, and all required digests.
- [ ] 2.3 Produce a canonical `recovery_plan_sha256` that binds the complete
  preview and expected destination state.

## 3. Confirmation-bound recovery apply

- [ ] 3.1 Recompute the confirmed plan under the workspace execution lease and
  guarded directory handles before mutation.
- [ ] 3.2 Publish the official combined-error output and fixed supplemental
  recovery receipt atomically and new-only without external-tool execution.
- [ ] 3.3 Support only the specified byte-identical partial-publication resume;
  reject every conflicting output or receipt without mutation.
- [ ] 3.4 Preserve the generation and execution summaries, combined dose,
  RTDOSE evidence, and retained staging tree byte-for-byte.

## 4. Supplemental authority and presentation

- [ ] 4.1 Validate the exact supplemental receipt and current official
  dose/error pair as optional Structure-evaluator evidence.
- [ ] 4.2 Keep invalid, stale, ambiguous, direct-evidence-conflicting, or
  unsupported recovery evidence unavailable without fallback.
- [ ] 4.3 Enable only the existing explicit post-completion Structure section;
  do not add automatic evaluation or downstream authority.

## 5. Synthetic validation and documentation

- [ ] 5.1 Add synthetic success tests for preview, apply, receipt consumption,
  and exact interrupted-publication resume.
- [ ] 5.2 Add fail-closed tests for links/reparse points, ambiguous selection,
  changed summaries or artifacts, mismatched dose, malformed error, invalid
  semantics, conflicting targets, stale plan, and existing invalid receipt.
- [ ] 5.3 Prove with fake or mock runners that PHITS, Sumtally, and phits2dicom
  never start during preview or apply.
- [ ] 5.4 Document the bounded recovery workflow and its non-clinical,
  no-cleanup, and separate real-workspace approval boundaries.

## 6. Completion

- [ ] 6.1 Run focused checks and every public check required by `AGENTS.md`.
- [ ] 6.2 Promote accepted deltas, archive the completed change, and strictly
  validate the resulting OpenSpec tree.
- [ ] 6.3 Request separate exact approval before any real external-workspace
  preview or recovery apply.
