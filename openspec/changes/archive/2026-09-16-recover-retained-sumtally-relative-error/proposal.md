# Change: Recover retained Sumtally relative-error evidence

## Why

On supported Windows systems, guarded cleanup intentionally preserves a
Sumtally staging tree when deleting it would require releasing the directory
identity that was held during execution. A completed non-clinical workflow
demonstrated that such a preserved tree can contain the combined dose/error
pair even when the error file was not promoted because the then-current parser
rejected a supported output representation. The parser now validates that
retained pair, but the public workflow has no contract for adopting it.

Rerunning Sumtally is not an acceptable recovery substitute. It can replace
the current combined output and make already accepted RTDOSE evidence stale,
and an unchanged deterministic output can fail the existing fresh-output
gate. Manually copying the error file or editing the terminal execution summary
would bypass provenance and stale-evidence checks. A bounded recovery contract
is therefore required before any workspace mutation.

## What Changes

- Add an explicit read-only recovery preview for one user-selected current
  workspace and one explicitly selected preserved Sumtally staging directory.
- Prohibit directory scanning, implicit candidate selection, historical
  fallback, and PHITS, Sumtally, or phits2dicom execution during recovery.
- Require the retained wrapper, includes, dose, and error to bind exactly to
  the canonical manifest, successful generation and execution evidence,
  current official combined dose, mesh geometry, supported semantics, and
  immutable digests.
- Bind the mutation step to a canonical preview digest and revalidate it under
  the workspace execution lease immediately before any write.
- Publish only the missing official combined-error output and one fixed-path,
  versioned supplemental recovery receipt. Both outputs are new-only; the
  original generation and execution summaries, combined dose, RTDOSE evidence,
  and preserved staging tree remain unchanged.
- Permit a bounded resume when the error output was published but receipt
  publication did not complete, only when its bytes exactly match the
  revalidated retained error.
- Allow the existing post-completion Structure evaluator to use the exact
  supplemental receipt only after independently revalidating the official
  dose/error pair and all current bindings. Recovery grants no PHITS,
  Sumtally, RTDOSE, clinical, convergence, or downstream authority.
- Use only synthetic workspaces and fake or mock external-tool artifacts for
  automated development and validation.

## Impact

- New capability: `sumtally-relative-error-recovery`
- Affected capabilities: `post-completion-structure-relative-error` and
  `workspace-output-security`
- Likely affected runtime: a dedicated recovery inspector/apply adapter,
  Sumtally evidence binding, and visibility of the existing post-completion
  Structure section
- Likely affected tests: synthetic retained-staging provenance, path security,
  partial-publication resume, stale receipt, and GUI eligibility tests
- Unchanged boundaries: PHITS physics, histories, tally settings, dose,
  geometry, DICOM meaning, MU, normalization, RTDOSE bytes and evidence,
  fixed-field 3D-CRT scope, and clinical claims

This proposal phase changes OpenSpec documents only. It does not authorize
runtime implementation, external workspace mutation, real-data adoption,
external-tool execution, staging cleanup, release, or publication.

## Approval and completion boundary

Runtime implementation requires explicit human approval of this complete
proposal. After an approved implementation is merged, applying recovery to any
real external workspace remains a separate exact human decision based on a
read-only preview. The active change MUST remain unarchived until implementation,
required validation, delta promotion, and archive validation are complete.
