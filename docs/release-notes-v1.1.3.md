# dicomxphits v1.1.3 Release Notes

Status: source candidate prepared on 2026-10-27. The maintainer publishes
the GitHub Release after candidate checks pass; this document does not
assert that publication has already occurred.

This is experimental education and research software for authorized
non-patient phantom evaluation. It is not clinical commissioning, patient
QA, vendor certification, or a claim of physical dose accuracy.

## Changes since v1.1.2

- PR #102 adds a separate CLI and GUI review of eligible saved PHITS results
  when exactly one active segment failed solely for geometry recoveries.
  Acceptance does not recalculate PHITS. The operator reviews diagnostics
  and region-pair counts, enters a reason and explicitly confirms research use.
- Lost and unrecovered counts must be zero. Any positive recovering count
  is eligible only when the full recorded distribution agrees, the final
  batch equals prepared `maxbch`, return code is zero, and provenance and
  artifact hashes validate. This is an operator research decision, not a
  declaration of physical safety based on the PHITS lost-particle limit.
- A portable v2 receipt records the decision. Preview/digest validation,
  invocation-bound staging, an execution lease and new-only publication
  preserve original failed records byte-for-byte. The segment stays failed.
- Sumtally Generate/Run and RTDOSE Prepare/Run independently revalidate the
  receipt and propagate its SHA-256 and segment ID in `research_exception`.
  The GUI shows a research warning and provides explicit re-reading.
  Ordinary failure gates and DICOM attributes remain unchanged.
- The CT clipping, bounded CT preview and independent ROI statistics GUI
  introduced in v1.1.2 remain included. Package metadata and GUI About report
  version 1.1.3.

## Verification and limits

Candidate verification is recorded in the release-preparation pull request.
It uses Python 3.12, synthetic fixtures and fake external-tool runners.
Hidden Tk tests use their own interpreter and temporary settings; they do
not control an already running user GUI. No real PHITS, Sumtally,
CT2PHITS, phits2dicom or GPR execution is part of this release verification.
Automated checks cannot establish end-to-end real-tool operation, dose
accuracy, convergence or clinical suitability.

The nonzero diagnostic-table grammar comes from an operator-supplied example,
not an independently verified original output. Unknown layouts fail closed.
Prototype receipts, edited historical output and runs without prospective
staging bindings are ineligible. Existing workspaces are not migrated or
reaccepted automatically. No physics or physical tolerance was changed.

Strict validation passes for the new research geometry recovery capability
and its archived deltas. Whole-tree strict validation retains the existing
baseline of 19 specifications with 96 requirement-length warnings, plus one
unrelated historical archive with an incomplete task. Those are not repaired
by this release preparation.

Source archives only: no custom Windows offline ZIP or licensed external
tools are included. Preserve original inputs and results, and evaluate the
release in a separate non-patient workspace. See the
[implementation report](../openspec/changes/archive/2026-10-27-add-research-geometry-recovery-acceptance/completion-report.md)
and [PR #102](https://github.com/inata169/dicomxphits/pull/102).
