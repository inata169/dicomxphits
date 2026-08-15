# Tasks

## 1. Confirm and Approve Scope

- [x] 1.1 Confirm repository, branch, remote, tags, target commit ancestry, and
  clean working tree after fetching current remote-tracking refs.
- [x] 1.2 Confirm through the GitHub plugin that PR #37 is merged and closed,
  PR #38 is open and draft at `ecf474a`, and exact-head CI run #344 succeeded.
- [x] 1.3 Inspect the exact `af87da3` and `85a8d78` runtime, GUI, OpenSpec, and
  test diffs and compare them with current PR #37 and PR #38 content.
- [x] 1.4 Create this proposal, design, task checklist, and requirement deltas
  without changing runtime code or current specifications.
- [x] 1.5 Obtain explicit human approval of this proposal and its deltas before
  runtime implementation. Approved by the primary user on 2026-08-15.

## 2. Restore and Integrate Accepted Specifications

- [x] 2.1 Restore the accepted
  `2026-08-13-strengthen-6mv-safety-and-gui-clarity` archive verbatim from
  `af87da3` without importing old runtime files through Git history operations.
- [x] 2.2 Restore the accepted current
  `fixed-6mv-beam-model-safety` specification.
- [x] 2.3 Promote the accepted and newly approved guided GUI requirements into
  the current recovery-aware `guided-gui-workflow` specification without
  deleting or rewriting PR #37 requirements.

## 3. Port the Fixed 6 MV Guard

- [x] 3.1 Add one package-owned fixed Elekta Precise nominal 6 MV photon model
  identity reused by validation, evidence, and GUI display.
- [x] 3.2 Add common included-treatment-beam validation before manifest or
  PHITS input output, including first-control-point presence and later DICOM
  inheritance.
- [x] 3.3 Reject unsupported radiation types, energies, missing or malformed
  values, mixed beams, and within-beam changes with controlled beam identity.
- [x] 3.4 Add backward-compatible `public_beam_model` evidence to the segment
  manifest and workspace-preparation summary.
- [x] 3.5 Preserve current gantry contract binding, public spectrum bytes,
  aperture gate, physics, normalization, dose, and coordinate behavior.

## 4. Integrate Help and Minimum-Window GUI Behavior

- [x] 4.1 Display the shared fixed model and `Nominal energy: 6 MV (fixed)` on
  all five workflow pages without an energy selector.
- [x] 4.2 Add `Help -> Web site` as an explicit-click exact-URL browser action
  with controlled local failure handling and no startup network action.
- [x] 4.3 Add `Help -> About` displaying the current package version and
  `Hiroki Inata (inata169)` without changing version metadata.
- [x] 4.4 Put only workflow page content in a vertically scrollable viewport,
  retain the separate Activity log, and reset the viewport on page changes.
- [x] 4.5 Keep primary actions reachable on CT2PHITS, Workspace, PHITS,
  Sumtally, and RTDOSE at `1120 x 720` while preserving their current callback
  and gating bindings.

## 5. Add Synthetic Regression Coverage

- [x] 5.1 Add supported 6 MV, multiple-beam, inherited-energy, 10 MV, mixed,
  changing, missing, invalid, and non-photon synthetic beam-model tests.
- [x] 5.2 Verify fail-closed timing before PHITS input output and matching
  additive manifest and workspace-summary evidence.
- [x] 5.3 Verify fixed model text, absence of an energy selector, Help labels,
  mocked exact-URL dispatch, About contents, and no startup browser action.
- [x] 5.4 Verify the common page viewport, separate Activity log, scroll reset,
  and all five pages' primary action areas.
- [x] 5.5 Run current GUI state, RTDOSE course-dose, recovery, gantry geometry,
  and offline installer regression suites to prove their gates remain intact.

## 6. Validate the Repository

- [x] 6.1 Run focused synthetic GUI, beam-model, workspace, gantry, fraction
  dose, recovery, stage-gating, and offline installer tests.
- [x] 6.2 Run `python -m compileall src`.
- [x] 6.3 Run `python -m pytest -q -p no:cacheprovider`. The Windows run used
  a repository-external dedicated pytest base directory so directory-lock
  tests could exercise their intended host behavior: 799 passed, 11 skipped.
- [x] 6.4 Run `python tools/verify_public_tree.py`.
- [x] 6.5 Run strict OpenSpec validation on the active change and full tree.
- [x] 6.6 Run `git diff --check`, `git diff --stat`, and `git status --short`.
- [x] 6.7 Confirm no protected data, external-tool output, local absolute path,
  version metadata change, tag change, or unapproved coordinate-output-choice
  proposal entered the diff.

## 7. Build and Accept the Offline Artifact

- [x] 7.1 Build the Windows offline ZIP from one exact validated integration
  HEAD and verify its manifest records that HEAD and all payload hashes.
- [x] 7.2 Extract to a new empty directory and run repository-safe offline
  bundle checks without reusing or overwriting the prior installed folder.
- [x] 7.3 Obtain human Windows 11 acceptance for the fixed 6 MV identity, Help
  menu, Web site action, `Hiroki Inata (inata169)`, package version, minimum-
  window scrolling, and all five pages' action reachability.
- [x] 7.4 Record any explicitly deferred non-blocking external installation
  evidence accurately; do not run real PHITS-related tools or real DICOM.
  The primary user reported successful Windows installation and GUI acceptance,
  and separately reported no abnormal dose distribution or absolute dose in
  their external-tool workflow. The agent did not execute or inspect PHITS,
  Sumtally, phits2dicom, GPR, real DICOM, or calculation results.
- [x] 7.5 Treat the acceptance-time attempt to save GUI settings below the
  protected `ProgramData` source snapshot as a merge-blocking integration
  defect rather than weakening the protected runtime permissions.
- [x] 7.6 Move the Windows default to the per-user `LOCALAPPDATA` settings path
  while preserving the explicit environment override, atomic replacement,
  persisted-field allowlist, and non-persistent safety state.
- [x] 7.7 Add Windows-path, explicit-override, actual-save, GUI, and offline
  installer regression coverage for the settings correction.

## 8. Complete OpenSpec Cleanup

- [x] 8.1 Confirm every approved acceptance criterion and required check is
  complete before closing this change.
- [x] 8.2 Update this checklist accurately, promote accepted deltas, archive
  this change under the completion date, and strictly validate the resulting
  current specification tree and archive.
