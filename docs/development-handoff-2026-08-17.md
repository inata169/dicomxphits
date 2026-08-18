# Development handoff - 2026-08-17 MLCX correction closeout

This handoff supplements the
[v1.0.2 release closeout](development-handoff-2026-08-15-v1.0.2.md). It records
post-release corrections and the stopping boundary for 2026-08-17. The
software remains education and research software for the documented
fixed-field 3D-CRT workflow; this record does not establish clinical validity,
commissioning, patient QA, or vendor certification.

The calculation-in-progress and planned-validation sections below intentionally
preserve the 2026-08-17 stopping point. The later human-reported completion,
collimator-direction correction, and repository closeout are recorded in the
[2026-08-18 development handoff](development-handoff-2026-08-18.md).

## Repository and GitHub baseline

Before this handoff branch was created, local `main` was clean and matched
`origin/main` at `0c0079edc5e739b8bad060a3ad55159f8d1f76a6`.

- Pull request #44, **Fix MLCX patient-axis reflection**, is merged and closed.
  Its final reviewed exact HEAD was
  `81454b700515b50dce47ba05846e3af552ec49ae`, its merge commit was
  `14b2d266c308f399c6ab87def72866c66928bd7d`, and CI run #401 succeeded.
- Pull request #45, **Document public companion comparison repository**, is
  merged and closed. Its reviewed exact HEAD was
  `c6ec6fd067ca1515f27873b340a398bdff5879e0`, its merge commit was
  `0c0079edc5e739b8bad060a3ad55159f8d1f76a6`, and CI run #404 succeeded.
- The merged feature branches for pull requests #44 and #45 were deleted.
- Tags `v1.0.2`, `v1.0.1`, and `v1.0.0` were not changed.
- The published `v1.0.2` tag and offline ZIP remain based on
  `efb0dace568fbcb12019f3d320a468dcfb446e34`. The post-release MLCX
  correction in pull request #44 is therefore present on `main`, but is not
  part of the `v1.0.2` tag or its published offline ZIP.

## Completed MLCX correction

Pull request #44 corrected the patient-axis reflection of DICOM IEC MLCX
positions. Each DICOM MLCX interval `[a, b]` is now converted to the PHITS
local interval `[-b, -a]`, while the leaf-pair Y ordering is preserved.
Prepared-workspace provenance advanced from
`dicomxphits_iec_gantry_direction_v2` to
`dicomxphits_iec_gantry_mlcx_geometry_v3`.

Reuse of old v2 transport is restricted to workspaces whose active segments
explicitly have gantry angle zero and whose MLCX apertures are invariant under
the reflection. Stale asymmetric v2 transport is rejected. Existing
fail-closed behavior for noncurrent, nonzero-gantry transport remains in
effect under the public portable-workspace recovery specification.

The `@codex` review loop found and resolved two merge-blocking provenance
issues: asymmetric stale-v2 reuse, then overly broad v2 reuse when MLC was
absent or reflection-invariant at nonzero gantry. The final reviewed revision
had no remaining major issue.

Independent synthetic patient-LPS collimator anchor tests cover 0, 30, 90,
180, and 270 degrees. These tests verify the established collimator transform;
the runtime collimator-angle implementation itself was not changed by this
correction. The correction did not change dose, MU, normalization, DICOM
output placement, spectrum, public physics, effective aperture semantics, or
the supported treatment scope. It restored the already documented coordinate
behavior, so no new OpenSpec change was required.

## Companion comparison documentation

Pull request #45 added a README reference to the public companion comparison
repository. The wording preserves the non-patient education-and-research
scope and explicitly states that comparison output does not establish
clinical validity.

## Validation completed for merged work

The final pull request #44 revision passed 275 focused tests with 1 skipped,
the full public suite with 855 passed and 10 skipped, source compilation, the
public-tree audit, diff checks, and CI run #401. Pull request #45 passed the
full suite with 855 passed and 10 skipped, source compilation, the public-tree
audit, diff checks, and CI run #404.

## Human-operated external calculation in progress

The human operator reported starting fresh per-field PHITS calculations for
fields f1 through f4 from a newly prepared workspace after the MLCX correction.
Completion was expected on the morning of 2026-08-18. The calculation is in an
operator-managed external workspace. The agent did not execute or inspect
PHITS, Sumtally, phits2dicom, GPR, DICOM, or calculation results. The local
path, dataset identifiers, generated files, numerical results, and images are
intentionally not recorded in Git.

After the operator confirms that all four field calculations completed without
error, the human validation sequence is:

1. Confirm that the fresh prepared workspace records v3 MLCX geometry
   provenance.
2. Generate new per-field RTDOSE files through the normal human-operated
   workflow.
3. Compare TPS reference and PHITS evaluation distributions outside this
   repository, assessing aperture orientation and shape before interpreting
   gamma results affected by statistical uncertainty.
4. Recheck all fields, with particular attention to the previously obvious
   f3 and f4 shape disagreement.
5. After MLC shape agreement is established, perform the planned human
   empirical collimator-angle test using fixed gantry geometry and an
   asymmetric aperture.

These are external human validation steps, not authorization for an agent to
run or read the real tools, DICOM, or calculation results.

## OpenSpec and known historical item

There is no active OpenSpec change. The accepted v1.0.2 changes remain
promoted and archived. The unrelated archive
`2026-08-07-add-windows-offline-installer` still contains one known unchecked
historical task; it must not be edited merely to make aggregate archive status
look complete. The withdrawn `add-rtdose-coordinate-output-choice` proposal
must not be recreated.

## Restart and stopping boundary

At the next session, first read the repository instructions, this handoff, the
v1.0.2 release closeout, and `project-status.md`; then confirm root, branch,
HEAD, clean status, remote, history, and tags. Confirm the human-reported
external calculation outcome without importing protected data into the
repository. No required repository implementation remains at this stopping
point. Do not create a feature, OpenSpec change, branch, pull request, Issue,
release, or tag until the human identifies the next purpose.
