# Project status

This document records the durable, human-managed development status of the
public repository. It is not an automatically expanding backlog. Update it only
when a human approves a new goal or when a completed pull request materially
changes the status described here.

For the detailed same-day record covering the merged CT2PHITS GUI baseline,
the demonstrated non-patient Windows workflow, and the completed PR #8 RTDOSE
provenance review cycle, see
[`development-progress-2026-08-02.md`](development-progress-2026-08-02.md).
For the later Dev Container cross-check of every squash commit from pull
request #1 through pull request #9, see
[`dev-container-validation-2026-08-03.md`](dev-container-validation-2026-08-03.md).
For the v1.0.1 release completion and next-session restart boundary, see the
[`2026-08-05 development handoff`](development-handoff-2026-08-05.md).

## Current baseline

- Public release: [`v1.0.1`](https://github.com/inata169/dicomxphits/releases/tag/v1.0.1)
- Previous public release: `v1.0.0`
- Public workflow scope: documented fixed-field 3D-CRT
- Release tag and commit: `v1.0.1` at
  `7db473b12d570026600c03947690d0f6c1fb60f5`
  (2026-08-05)
- Latest completed runtime work: fail-closed RTDOSE isocenter translation and
  final coordinate-placement validation
- Runtime completion pull request:
  [#19](https://github.com/inata169/dicomxphits/pull/19)
- Latest completed repository update: Windows Code **Download ZIP** launcher
  correction and durable documentation alignment
- Release preparation pull request:
  [#24](https://github.com/inata169/dicomxphits/pull/24)
- Release merge commit: `7db473b12d570026600c03947690d0f6c1fb60f5`
- Release CI: pull-request run #181, main push run #182, and tag push run #183
  completed successfully
- Release closeout pull request:
  [#25](https://github.com/inata169/dicomxphits/pull/25)
- Latest repository update pull request:
  [#27](https://github.com/inata169/dicomxphits/pull/27)
- Current main baseline: merge commit
  `857e61bc0cecfce882c3b0949119d4868824fe6f`
- Current-baseline main push CI run #198 completed successfully
- Dev Container baseline validated through pull request
  [#9](https://github.com/inata169/dicomxphits/pull/9), squash commit
  `ebcd53529e7ff37e4edc66f4500a73ed8edf7e09`
- Status last reviewed: 2026-08-06

The GitHub Release publishes the source distribution and wheel built from the
`v1.0.1` tag. Their SHA-256 digests are
`1afbbf75d7d8baaf9914c0263ce15a3073581fc7df0681b83e1ac5eff7e3cc3e`
for `dicomxphits-1.0.1.tar.gz` and
`da46087c3d4dc0944fc3561055b4b6fcc312b156bfdb376892bc209b6e2bb55a`
for `dicomxphits-1.0.1-py3-none-any.whl`. A fresh public download reproduced
both digests, passed `twine check`, installed into an isolated Python 3.12
environment with matching package and runtime version `1.0.1`, and returned
success for `--help` on all eleven console entry points without executing
external tools. The release is not published to PyPI.

The RTDOSE provenance correction is complete. It binds PLAN-dose acceptance to
the frozen RT Plan, complete treatment delivery, canonical segment manifest,
generated Sumtally inputs and dependencies, produced dose output, and every
file consumed by `phits2dicom`. Sumtally and RTDOSE conversion now require a
new output or changed SHA-256; timestamp-only changes to stale output fail
closed. Pull request #18 additionally sets `sumfactor` to the active
treatment-segment MU sum, excludes validated skipped non-treatment beams from
treatment dose, keeps phits2dicom factor `1.0`, and binds GUI state to the
current Sumtally-to-Prepare-to-Run digest chain. The accepted contract is in
[`openspec/specs/rtdose-dicom-semantics/spec.md`](../openspec/specs/rtdose-dicom-semantics/spec.md).

The guided CT2PHITS GUI integration is complete. It made the accepted frontend
the first guided stage, applies only a verified frozen handoff to downstream
preparation, remembers stable local tool paths and independent Browse history,
keeps safety confirmation non-persistent, and presents responsive, separately
gated workflow stages. Review corrections also bound completed handoffs to the
executed workspace, launched CT2PHITS from an existing RT-PHITS directory,
required an explicit manual or verified handoff before preparation, and made
local-settings failure handling fail safely. The accepted GUI contract is in
[`openspec/specs/guided-gui-workflow/spec.md`](../openspec/specs/guided-gui-workflow/spec.md).

The standard Windows PHITS 3.35 profile now selects the OpenMP segment runtime,
lets the user set the positive `$OMP`, `maxcas`, and `maxbch` values applied to
prepared segment inputs, and keeps Sumtally execution compatible with the
OpenMP runtime. The accepted runtime contract is in
[`openspec/specs/phits-segment-runtime/spec.md`](../openspec/specs/phits-segment-runtime/spec.md).
The guided RTDOSE stage now distinguishes Not run, Prepared, and Completed and
guides the user to Run after a successful Prepare without treating a repeated
Prepare as the next action.

The underlying automated CT2PHITS frontend remains complete under pull request
[#3](https://github.com/inata169/dicomxphits/pull/3), squash commit
`f792d0ec7f1e9265ad5df939e2e6b3aeb9f6e4bb`. See the
[CT2PHITS frontend handoff](ct2phits-frontend-handoff.md) for its detailed
completion state and restart procedure.

Pull request [#20](https://github.com/inata169/dicomxphits/pull/20) adds the
[v1.0.x GUI user guide](gui-user-guide.md) and aligns README guidance with the
implemented workflow stages and the bounded companion-repository references.
It does not extend the clinical, physics, DICOM, dose, MU, normalization, or
supported-workflow scope.

The earlier LLM development-loop foundation remains complete under pull
request [#1](https://github.com/inata169/dicomxphits/pull/1), squash commit
`7d2f511a3136da6d35b857b42c8e048e9f1f5c84`.

After the dated Dev Container validation through pull request #9, pull request
[#10](https://github.com/inata169/dicomxphits/pull/10) recorded that evidence,
pull request [#11](https://github.com/inata169/dicomxphits/pull/11) added
Windows synthetic/mock CI, pull request
[#12](https://github.com/inata169/dicomxphits/pull/12) clarified platform and
GUI setup documentation, and pull request
[#13](https://github.com/inata169/dicomxphits/pull/13) simplified the guided GUI
tool profile and CT2PHITS case-path setup. Pull request
[#14](https://github.com/inata169/dicomxphits/pull/14) restricted the supported
interpreter range to Python 3.12 and aligned the public documentation and
OpenSpec project contract. Pull requests #15 and #16 completed the runtime and
RTDOSE GUI work described above. These later changes do not extend the dated
Dev Container evidence beyond pull request #9. At current `main`, the
public-tree audit passes 136 tracked files.

## Validation baseline

The completion state for pull request #8 was validated locally on Windows
with:

- 77 focused Sumtally/RTDOSE dependency tests;
- 508 full synthetic/mock pytest tests;
- Python compilation of the public source;
- a passing public-tree audit of 98 tracked files;
- passing Git diff and status checks; and
- a final Codex review of head commit `1c6d6ea78c` reporting no major issues.

At the pull request #8 completion baseline, OpenSpec CLI `1.6.0` strict
validation passed all three then-current specifications with zero failures.
Each archived change at that baseline was also copied individually to an
isolated temporary OpenSpec root, validated there as an active change in strict
mode, and removed after validation passed.

At current `main`, the repository contains four current specifications, eight
archived changes, and one active change. Strict validation passes all four
current specifications plus the active `support-portable-workspace-recovery`
change, for five passed items and zero failures. The active change remains at
1/21 tasks and is not approved for runtime implementation. The PHITS
runtime-control delta from pull request #15 was promoted into the current
specification and archived
as part of that task. The guided RTDOSE state and explicit reprepare recovery
from pull request #17 are also recorded in the current guided GUI specification
and archived. The previously deferred CT2PHITS workplace Dev Container task is
recorded complete against the dated cross-check evidence.

An explicitly authorized Windows workflow with designated non-patient phantom
data outside the repository completed CT2PHITS, workspace preparation, PHITS
segment execution, Sumtally Generate/Run, and RTDOSE Prepare/Run. The final
coordinate-corrected RTDOSE was located through the execution summary. The
later final PR #8 provenance guards were validated with synthetic DICOM and
fake/mock runners and were not rerun with the licensed tools. This is
integration evidence for that research phantom, not clinical validation or
general dose-accuracy evidence. No real input, distribution, personal path,
or generated result was committed.

Separately, `dicomxphits public CI` run `#42` passed the synthetic/mock compile,
full pytest, and public-tree checks for the earlier frontend baseline on
GitHub's `ubuntu-latest` Linux runner. This is Linux CI evidence for pull
request #3; it does not validate pull request #5 or the real Windows RT-PHITS
runtime.

The human-authorized workplace Dev Container cross-check completed on
2026-08-03 for every squash commit from pull request #1 through pull request
#9. All nine commits passed package installation, Python compilation, the full
synthetic/mock pytest suite, the public-tree audit, and Git diff/status checks.
At pull request #9, the Linux result was 507 passed and one expected
Windows-only process-tree test skipped, with 98 tracked files passing the
public-tree audit. The CT2PHITS-focused pull request #3 check separately passed
64 tests with the same expected Windows-only test skipped. See the
[dated Dev Container validation record](dev-container-validation-2026-08-03.md)
for the per-commit evidence and exact boundary. This is distinct from both the
earlier Ubuntu GitHub Actions run and real Windows RT-PHITS execution.

Pull request #8 changed fail-closed provenance validation, Sumtally/RTDOSE stage
failure behavior, documentation, and the public RTDOSE semantic specification
within its approved scope. It did not change PHITS physics, calculated dose,
MU, normalization, machine-model behavior, DICOM coordinate meaning, the
public fixed-field 3D-CRT scope, version, tag, or release.

At the pull request #17 closeout candidate, the full public validation completes
with 555 tests passed and one expected Windows-only test skipped in the Linux
Dev Container, Python source compilation succeeds, and the public-tree audit
passes 114 tracked files. Pull requests #15 and #16 were squash-merged with
their branches deleted. A delayed review of the final pull request #16 commit
then identified the missing RTDOSE GUI OpenSpec record and reprepare recovery;
pull request #17 records and corrects both findings. These checks use
synthetic/mock fixtures and do not extend the real-tool or clinical validation
boundary described above.

Pull request #18 was squash-merged as `6112fce`; its final Codex review reported
no major issues, GitHub Actions passed, and the public suite completed with 572
tests passed and one expected skip. Its remote feature branch was deleted.

Pull request #19 was squash-merged as `8d690c8`. Its final Codex review
reported no major issues, GitHub Actions passed on Windows and Ubuntu, and its
remote feature branch was deleted. Closeout validation completed with 194
focused tests passed, 588 full public tests passed and one expected skip,
successful source compilation, a 124-file public-tree audit, and strict
OpenSpec validation.

Pull request #20 was squash-merged as `45bd940`. Its final Codex review reported
no major issues, GitHub Actions passed, and its remote feature branch was
deleted. Documentation closeout validation completed with 91 focused tests
passed, 588 full public tests passed and one expected skip, successful source
compilation, a 125-file public-tree audit, and four strict OpenSpec validations.

Pull request #21 was squash-merged as `92260d9`. Its first Codex review found a
digest-binding ambiguity in the proposal; commit `0e228a0` corrected it by
requiring a recorded matching SHA-256 for every active PHITS segment output
before Sumtally recovery. The final Codex review reported no major issues,
GitHub Actions run #172 passed, and the remote feature branch was deleted.
Proposal closeout checks passed five strict OpenSpec validations, source
compilation, a 131-file public-tree audit, and Git diff/status checks. No
runtime implementation was included.

Pull request #23 recorded the bounded v1.0.1 external non-patient manual
evidence without adding paths, DICOM, numerical results, screenshots, result
files, or generated outputs. Pull request #24 prepared version metadata and
release documentation and was merged as `7db473b`. Its Codex review reported
no major issues, GitHub Actions passed on the pull request, main, and tag, and
the remote feature branch was deleted. Release preparation validation completed
with 86 focused tests, 589 full public tests and one expected skip, five strict
OpenSpec validations, successful source compilation, a 133-file public-tree
audit, successful sdist and wheel builds, `twine check`, isolated wheel
installation, and all eleven installed console entry-point help checks.

Pull request #25 recorded the release closeout as `902425d`, and pull request
#26 recorded the 2026-08-05 development handoff as `3aa69ae`. Pull request #27
then corrected the Windows Code **Download ZIP** launcher path after an unsigned
PowerShell script was blocked by host policy. It added the default CMD launcher,
kept the equivalent PowerShell entry point, included both launchers in source
distributions, and added path-metacharacter regression coverage without changing
runtime workflow semantics. Pull request #27 was squash-merged as `857e61b`;
its exact-head Codex review reported no major issues, pull-request CI #197 and
main CI #198 passed on Ubuntu and Windows, and its remote feature branch was
deleted.

## Current development plan

The approved `fix-rtdose-isocenter-translation` change is complete and
merged through pull request #19. The implementation derives RTDOSE placement
from the frozen RT Plan isocenter and PHITS tally mesh using the accepted
bin-centre mapping `I + 10 * (-x, z, y)`, then requires independent
final-DICOM coordinate validation before the GUI reports RTDOSE Completed.
The Sumtally, MU-normalization, and digest-binding corrections from pull request
#18 remain intact.

The authorized coordinate-only manual validation reused the existing designated
non-patient phantom PHITS and Sumtally results. It did not repeat PHITS or
Sumtally, and final coordinate-placement validation passed with the output
present. All workstation paths, DICOM, licensed tools, GPR result files, and
generated results remained outside Git. This is bounded non-patient research
evidence, not clinical validation.

For the v1.0.1 release evidence, an explicitly authorized external non-patient
workflow completed CT2PHITS, workspace preparation, PHITS segment execution,
Sumtally Generate/Run, RTDOSE Prepare/Run, and an external GPR comparison. The
result is recorded only as a human-reported, screenshot-supported completion;
the agent did not inspect the external result file. Exact paths, DICOM, numeric
results, screenshots, GPR result files, and generated outputs remain outside
Git. This is one bounded research workflow, not clinical validation or a
general dose-accuracy claim.

After pull request #27, the human separately reported two successful Windows
manual checks: one used an existing external workspace path and one used a
duplicate path containing spaces, Japanese text, and a copy suffix. The
external GPR handoff was reported complete in both cases. The agent did not
inspect the external directories or results, and exact paths, DICOM, numerical
results, screenshots, GPR files, and generated outputs remain outside Git. See
the [dated Windows GUI launcher validation
record](windows-gui-launcher-validation-2026-08-06.md). This report does not
validate or authorize portable-workspace recovery.

The separate `support-portable-workspace-recovery` work was recorded through
pull request #21 and remains active at 1/21 tasks. Task 1.1, explicit human
approval before runtime work, is unchecked. The change therefore remains
proposal-only, unapproved for implementation, and unimplemented. No portable
workspace recovery implementation is part of the current baseline.

## Human-decision queue

The following facts may inform a future human decision, but they are not
approved work:

- any change to the public fixed-field 3D-CRT scope, physics, geometry, dose,
  MU, machine model, or clinical claims requires a separate human-approved
  decision; and
- no known merge-blocking defect or approved follow-up implementation remains
  from the completed implementation pull requests through #27.

Do not add personal-computer paths, private dataset details, patient or facility
data, credentials, or real-tool output to this document.

## Restart checklist

At the start of a future development session:

1. Read `AGENTS.md` and `AI_AGENT_RULES.md` in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Confirm that `main` contains launcher merge commit `857e61bc0cec` or a later
   descendant, and that the `v1.0.1` tag still resolves to release commit
   `7db473b12d5`.
4. Read this document, the
   [CT2PHITS frontend handoff](ct2phits-frontend-handoff.md), and the
   [workflow stage guide](workflow_stages.md), and verify that their baseline
   still matches `main`.
5. Keep the archived coordinate implementation and the active portable-workspace
   recovery proposal separate; do not implement the latter without approval.
6. For each observed failure, preserve the GUI log and record exact
   reproduction steps before proposing a code change.
7. When a human decision is required, ask a direct yes/no question.
8. Stop after the approved acceptance criteria and required checks pass.
