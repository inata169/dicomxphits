# Tasks

## 1. Confirm and Approve Scope

- [x] 1.1 Reproduce the deterministic protected-runtime ID from the reported
  extraction path without reading protected runtime contents, real DICOM, or
  calculation results.
- [x] 1.2 Distinguish the existing-runtime identity collision from the earlier
  Windows bundle-file sharing error.
- [x] 1.3 Create this proposal, design, task checklist, and delta specification
  without changing installer runtime behavior.
- [x] 1.4 Obtain approval to expand the proposal with a verified uninstall
  lifecycle after demonstrating the manual administrator-only cleanup burden.
- [x] 1.5 Obtain explicit human approval of this completed revised proposal and
  delta before runtime implementation. Approved by the primary user on
  2026-08-15.

## 2. Bind Runtime Identity to Verified Bundle Content

- [x] 2.1 Carry the already verified manifest SHA-256 from the bootstrap into
  the verified non-elevated and elevated installer stages.
- [x] 2.2 Derive the protected runtime ID from a versioned encoding of the
  normalized absolute bundle root and verified manifest SHA-256.
- [x] 2.3 Reject missing, malformed, or inconsistent identity inputs before
  protected runtime construction or Python execution.
- [x] 2.4 Preserve exact-repeat collision rejection and never reuse, repair,
  replace, or automatically delete existing protected content.

## 3. Report Elevated Failures Safely

- [x] 3.1 Write a bounded nonce-bound failure diagnostic with the protected
  runtime-control ACL when the elevated child fails after protected storage is
  available.
- [x] 3.2 Validate the diagnostic in the parent and show its controlled reason
  without allowing it to affect verification or execution decisions.
- [x] 3.3 Fall back to the generic nonzero-exit report when the diagnostic is
  absent, malformed, untrusted, or unavailable.

## 4. Add Synthetic Regression Coverage

- [x] 4.1 Test deterministic IDs for equal content, distinct IDs for changed
  manifests, and Windows path case normalization.
- [x] 4.2 Test missing and malformed identity state, exact-repeat failure, and
  preservation of an older protected target.
- [x] 4.3 Test protected diagnostic success and generic fallback without
  trusting diagnostic content for execution.
- [x] 4.4 Run the existing Windows bundle-lock, runtime-source, ACL, inventory,
  host-Python exclusion, no-index, and import regression suites.

## 5. Add Verified Offline Uninstallation

- [x] 5.1 Add authenticated uninstall entry-point and helper payloads to the
  producer bundle, manifest, checksum inventory, and required-file checks.
- [x] 5.2 Resolve the exact installation receipt from normalized bundle root
  and verified manifest identity without enumerating or guessing runtimes.
- [x] 5.3 Validate receipt identity, owner, ACL, target ancestry, complete root
  inventory, generated-path allowlist, and absence of reparse points before
  deletion.
- [x] 5.4 Refuse every deletion while a process associated with the selected
  GUI, `.venv`, protected runtime, installer, or scientific execution remains
  active.
- [x] 5.5 Stage only authenticated cleanup logic and an exact nonce-bound target
  description below the protected product boundary before UAC cleanup.
- [x] 5.6 Remove only the exact extraction root, protected runtime, receipt,
  MSI log, and cleanup staging; verify their absence and report exact remnants
  on a partial failure.
- [x] 5.7 Preserve other runtime IDs, sibling paths, cases, external tools, and
  per-user GUI settings.
- [x] 5.8 Wait for only the direct elevated staging process so its detached
  finalizer cannot deadlock against the verified bootstrap's read locks.
- [x] 5.9 Acquire and retain delete-sharing preflight handles for every existing
  exact target before mutation, refusing all deletion if any target is held.

## 6. Add Synthetic Uninstall Regression Coverage

- [x] 6.1 Test exact root-and-manifest receipt binding and rejection of another
  bundle root, runtime ID, user SID, or identity schema.
- [x] 6.2 Test refusal before mutation for active processes, unknown or modified
  files, reparse points, malformed receipts, and untrusted cleanup staging.
- [x] 6.3 Test a successful synthetic cleanup and prove that sibling runtimes,
  sibling directories, case-like paths, external-tool-like paths, and user
  settings remain byte-for-byte unchanged.
- [x] 6.4 Test bounded partial-failure reporting and confirm it never widens or
  guesses the cleanup target set.
- [x] 6.5 Reproduce the descendant-wait regression synthetically and prove the
  parent uses direct-process `WaitForExit()` without `Start-Process -Wait`.
- [x] 6.6 Reproduce a Windows directory delete-sharing conflict and prove that
  every exact target remains until the conflicting handle closes.

## 7. Update Offline Documentation

- [x] 7.1 Document in English and Japanese that an updated ZIP may reuse an
  earlier absolute path only after a fresh empty extraction.
- [x] 7.2 Preserve the prohibition on overwriting populated installation trees
  and the explicit-administrator cleanup boundary for retained runtimes.
- [x] 7.3 Document verified uninstallation, its refusal conditions, the exact
  installation-owned cleanup boundary, partial-failure reporting, and the
  separately optional retained per-user settings path.
- [x] 7.4 Document that uninstall must start outside the extraction folder and
  that an in-use exact target is rejected before deletion.

## 8. Validate and Accept

- [x] 8.1 Run focused synthetic offline-installer and uninstaller tests.
- [x] 8.2 Run `python -m compileall src`.
- [x] 8.3 Run `python -m pytest -q -p no:cacheprovider`.
- [x] 8.4 Run `python tools/verify_public_tree.py`.
- [x] 8.5 Run strict OpenSpec validation on this change and the complete tree.
- [x] 8.6 Run `git diff --check`, `git diff --stat`, and
  `git status --short`.
- [x] 8.7 Confirm no protected data, external-tool output, personal absolute
  path, physics behavior, DICOM meaning, version metadata, or tag change
  entered the diff.
- [x] 8.8 Build and verify a new exact-HEAD offline ZIP only after all required
  repository checks pass.
- [ ] 8.9 Obtain human Windows 11 installation, uninstallation, and GUI
  acceptance without
  agent execution of real external tools or real data.

## 9. Complete OpenSpec Cleanup

- [ ] 9.1 Confirm every approved acceptance criterion and required check is
  complete before closing this change.
- [ ] 9.2 Promote the accepted delta into the current specification, archive
  this change under the completion date, and strictly validate the resulting
  specification tree and archive.
