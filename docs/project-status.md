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

## Current baseline

- Public release: `v1.0.0`
- Public workflow scope: documented fixed-field 3D-CRT
- Current `main` HEAD: `6112fce3e3d6d1700bb171558bf601ca5b0b8234`
  (2026-08-04)
- Latest completed work: active-treatment-MU Sumtally normalization and
  fail-closed downstream digest binding
- Completion pull request:
  [#18](https://github.com/inata169/dicomxphits/pull/18)
- Squash merge commit: `6112fce3e3d6d1700bb171558bf601ca5b0b8234`
- Dev Container baseline validated through pull request
  [#9](https://github.com/inata169/dicomxphits/pull/9), squash commit
  `ebcd53529e7ff37e4edc66f4500a73ed8edf7e09`
- Status last reviewed: 2026-08-04

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
public-tree audit passes 110 tracked files.

## Validation baseline

The completion state for pull request #8 was validated locally on Windows
with:

- 77 focused Sumtally/RTDOSE dependency tests;
- 508 full synthetic/mock pytest tests;
- Python compilation of the public source;
- a passing public-tree audit of 98 tracked files;
- passing Git diff and status checks; and
- a final Codex review of head commit `1c6d6ea78c` reporting no major issues.

OpenSpec CLI `1.6.0` strict validation passed all three current specifications
with zero failures. The accepted CT2PHITS frontend, guided GUI, and RTDOSE
changes are archived, and the repository retains zero active change
directories. Each archived change was also copied individually to an isolated
temporary OpenSpec root, validated there as an active change in strict mode,
and removed after all three validations passed.

The repository contains four current specifications and six archived changes;
new approved work is represented by active change proposals. The PHITS
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

The coordinate feature integration and bounded pull-request review correction
complete with 194 focused tests passed, 588 full public tests passed and one
expected skip, successful source compilation, a 124-file public-tree audit,
and strict OpenSpec validation.

## Current development plan

The Windows GUI diagnostic completed the designated non-patient phantom
workflow through RTDOSE, but external research comparison showed a gross
three-dimensional translation and zero pass rate. Read-only diagnosis found
that the final coordinate correction preserved a volume centre inherited from
the converter CT slice position instead of deriving placement from the frozen
RT Plan isocenter and PHITS tally mesh. Dose/MU normalization remained a separate observation and was corrected by
pull request #18 without changing the coordinate contract.

The approved `fix-rtdose-isocenter-translation` change implements the exact
bin-centre mapping `I + 10 * (-x, z, y)`, binds the mesh and frozen-plan
isocenter, and requires independent final-DICOM coordinate validation before
the GUI reports RTDOSE Completed. Automated validation remains synthetic-only:
nonzero isocenters, asymmetric bounds, unequal dimensions, anisotropic
spacing, and fake converter runners write only under temporary test folders.
No PHITS, Sumtally, phits2dicom, GPR, real DICOM, or calculation result is
executed or added by those tests.

The separately approved coordinate-only manual reprepare then exposed a
fail-closed digest mismatch: historical RTDOSE Prepare had patched the accepted
Sumtally output in place after Sumtally Run recorded its SHA-256. The approved
correction stages private converter copies and proves the upstream Sumtally and
companion PHITS files remain unchanged. A historical in-place IPP title patch
is reusable only when reversing that exact patch, including LF/CRLF newline
normalization, reproduces the recorded Sumtally Run SHA-256; all other changes
remain failures.

The separately approved coordinate-only manual validation completed with the
existing designated non-patient phantom PHITS and Sumtally results. It did not
repeat PHITS or Sumtally, and the final coordinate-placement validation passed
with its output present. All workstation paths, DICOM, licensed tools, and
generated results remained outside Git. This is bounded non-patient research
evidence, not clinical validation.

The accepted coordinate delta is promoted into the current RTDOSE specification
and archived on the feature branch. The remaining step is review through the
feature pull request; the portable-workspace recovery proposal stays active and
unimplemented.

## Human-decision queue

The following facts may inform a future human decision, but they are not
approved work:

- an optional external GPR comparison remains outside ordinary public
  development and requires an explicit, exact human request;
- any change to the public fixed-field 3D-CRT scope, physics, geometry, dose,
  MU, machine model, or clinical claims requires a separate human-approved
  decision; and
- no known merge-blocking defect or approved follow-up implementation remains
  from the completed pull requests through #18.

Do not add personal-computer paths, private dataset details, patient or facility
data, credentials, or real-tool output to this document.

## Restart checklist

At the start of a future development session:

1. Read `AGENTS.md` and `AI_AGENT_RULES.md` in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Confirm that `main` contains squash merge commit `6112fce3e3d6` or a later
   descendant.
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
