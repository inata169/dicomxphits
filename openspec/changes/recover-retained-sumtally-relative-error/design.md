# Design: retained Sumtally relative-error recovery

## Context

The existing Sumtally runner executes in a freshly created guarded staging
directory. On success it promotes the combined dose before attempting to
validate and promote the paired statistical-relative-error output. On Windows,
the safe output guard can intentionally retain that staging directory because
recursive deletion would otherwise release validated directory handles before
path-based removal.

The accepted post-completion evaluator requires an official combined dose/error
pair and terminal evidence. A historical execution summary that records
terminal success but no combined-error evidence remains insufficient even when
a retained pair now passes the corrected parser. The recovery design must add
the missing authority without rewriting the historical execution record or
invalidating the existing RTDOSE chain.

## Goals

- Recover only a supported error output produced by the same completed
  Sumtally invocation as the current official combined dose.
- Preserve original summaries, combined dose, RTDOSE artifacts, and staging.
- Require explicit selection, preview, confirmation, and exact revalidation.
- Fail closed for path replacement, ambiguity, changed evidence, unsupported
  semantics, or a conflicting destination.
- Make interrupted publication safe to resume without overwriting evidence.

## Non-goals

- Rerunning PHITS, Sumtally, phits2dicom, or another external tool.
- Repairing a failed external execution or accepting a different dose result.
- Searching for staging directories or choosing among candidates.
- Editing or replacing the original generation or execution summary.
- Cleaning retained staging, relocating a workspace, or repairing arbitrary
  legacy output formats.
- Changing Structure statistics, RTDOSE eligibility, clinical meaning, or any
  physics, geometry, MU, normalization, or DICOM contract.

## Decisions

### One explicitly selected same-workspace source

Recovery accepts exactly one workspace root and one staging-directory path.
The staging directory must be an ordinary, non-reparse directory directly
below that unchanged workspace root, have the expected private staging-name
shape, and contain only the exact files needed by the plan. Version 1 does not
normalize a relocated root or scan the workspace for candidates. A preserved
tree remains non-authoritative unless the complete recovery contract succeeds.

### Read-only preview followed by digest-bound apply

Preview performs no writes. It validates the current canonical manifest,
successful Sumtally generation and execution summaries, generated wrapper and
includes, current official combined dose, expected missing error destination,
retained wrapper and includes, retained combined dose/error pair, mesh,
supported semantics, and every required digest. The retained dose must be
byte-identical to both the official dose and its recorded terminal digest.

Preview produces a canonical `recovery_plan_sha256` over the schema version,
workspace-relative paths, all authority-bearing evidence digests, expected
destination state, and intended receipt. Apply requires the exact confirmed
plan digest, acquires the existing workspace execution lease, and recomputes
the plan under guarded path handles before writing. Any change fails before
mutation.

### Supplemental evidence instead of historical-summary rewrite

Recovery does not edit `sumtally_generation_summary.json` or
`sumtally_execution_summary.json`. It publishes the official error output at
the path deterministically paired with the current official combined dose and
publishes one versioned receipt at
`analysis/sumtally_relative_error_recovery_summary.json`.

The receipt records only workspace-relative artifact identities, original
summary digests, manifest and input digests, official dose/error digests,
validated geometry and semantics, the confirmed plan digest, and recovery
contract metadata. It contains no raw grid, DICOM content, patient identifier,
machine-specific absolute path, or clinical conclusion.

The existing Structure evaluator may combine the immutable historical
execution summary with this exact supplemental receipt only when the execution
was terminally successful, its direct combined-error evidence is absent, and
all current official files and bindings independently revalidate. The receipt
does not alter RTDOSE state or become authority for any other stage.

### New-only publication and bounded resume

The error file is created atomically and new-only before the receipt. The
receipt is also atomic and new-only. Until the receipt exists and validates,
an error file alone grants no evaluation authority.

If publication is interrupted after the error file is created, a later preview
may classify only an exact byte-identical official error with no receipt as a
resumable partial publication. Apply then revalidates the full source and plan
before creating the receipt. A different existing error, any existing invalid
receipt, or any conflicting path fails closed without overwrite, rename,
deletion, or fallback.

### Preserved staging is never execution staging

Recovery opens the selected retained tree only as guarded evidence. It never
uses it as the working directory for an external process, never mutates or
deletes it, and never changes the rule that a later execution attempt must use
a fresh exclusively created staging directory.

### Existing GUI section, no automatic evaluation

No new automatic Structure evaluation is introduced. Once the fixed receipt
and official dose/error pair validate, the existing distinct
`Post-completion Structure r.err` section may become eligible under its current
explicit RT Structure Set and `ROINumber` controls. Invalid or stale recovery
evidence keeps that section unavailable.

## Failure and rollback model

- Failure before error publication changes nothing.
- Failure after error publication but before receipt publication leaves a
  non-authoritative exact error that can be resumed only under the bounded
  rule above.
- Published files are never overwritten or deleted automatically. An invalid
  published receipt requires a human decision outside this recovery contract.
- Original summaries, combined dose, RTDOSE outputs, and retained staging are
  always preserved, so the pre-recovery evidence remains inspectable.

## Security and validation

All existing workspace-output guards and the workspace execution lease remain
mandatory. Preview and apply must reject symbolic links, junctions, reparse
points, unsafe regular-file replacements, out-of-root paths, and evidence
changes between validation passes. Automated tests use only temporary
synthetic workspaces, synthetic tally text, and fake or mock runners. Real
external outputs are never committed or used in automated tests.

## Staged delivery

1. Strictly validate this proposal and obtain explicit human approval.
2. Implement preview, apply, supplemental binding, and GUI eligibility using
   synthetic fixtures only.
3. Run focused and full public validation and review the change.
4. Promote accepted deltas and archive the completed OpenSpec change.
5. Request a separate exact approval before previewing or applying recovery to
   any real external workspace.
