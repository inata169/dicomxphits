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
- Current `main` HEAD: `e1d9943c276db181dedacc70ed13669ed388e5fa`
  (2026-08-03)
- Latest completed work: Windows PHITS runtime controls and guided RTDOSE
  execution after preparation
- Completion pull requests:
  [#15](https://github.com/inata169/dicomxphits/pull/15) and
  [#16](https://github.com/inata169/dicomxphits/pull/16)
- Squash merge commits: `ac18e03db4d3ecd3771faf93f1e936d7aa408ef1` and
  `e1d9943c276db181dedacc70ed13669ed388e5fa`
- Dev Container baseline validated through pull request
  [#9](https://github.com/inata169/dicomxphits/pull/9), squash commit
  `ebcd53529e7ff37e4edc66f4500a73ed8edf7e09`
- Status last reviewed: 2026-08-03

The RTDOSE provenance correction is complete. It binds PLAN-dose acceptance to
the frozen RT Plan, complete treatment delivery, canonical segment manifest,
generated Sumtally inputs and dependencies, produced dose output, and every
file consumed by `phits2dicom`. Sumtally and RTDOSE conversion now require a
new output or changed SHA-256; timestamp-only changes to stale output fail
closed. The accepted contract is in
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

The repository now contains four current specifications, five archived
changes, and zero active change directories. The PHITS runtime-control delta
from pull request #15 was promoted into the current specification and archived
as part of that task. The previously deferred CT2PHITS workplace Dev Container
task is also recorded complete against the dated cross-check evidence.

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

At the current `main` baseline, the full public validation completes with 555
tests passed and one expected Windows-only test skipped in the Linux Dev
Container, Python source compilation succeeds, and the public-tree audit passes
110 tracked files. Pull requests #15 and #16 completed their Codex review/fix
loops without remaining actionable findings and were squash-merged with their
branches deleted. These checks use synthetic/mock fixtures and do not extend
the real-tool or clinical validation boundary described above.

## Current development plan

The next approved goal is a human-operated Windows GUI diagnostic session using
the two designated external test workspaces. Confirm again that the selected
inputs are non-patient phantom data before any real-tool execution. Exercise
the guided stages, record reproducible steps, timestamps, relevant GUI log
messages, expected behavior, and actual behavior, and identify bugs or usability
failures. Keep the absolute workstation paths, DICOM, licensed-tool files, and
generated results outside the repository.

This goal authorizes testing and diagnosis, not an unspecified implementation
branch. Each confirmed defect must be checked against the documented behavior
and safety boundary before deciding whether it is a bug fix or requires an
OpenSpec change and separate human approval. An LLM must not turn optional
improvements or unconfirmed observations into new Issues, branches, pull
requests, automations, or other work items on its own.

## Human-decision queue

The following facts may inform a future human decision, but they are not
approved work:

- an optional external GPR comparison remains outside ordinary public
  development and requires an explicit, exact human request;
- any change to the public fixed-field 3D-CRT scope, physics, geometry, dose,
  MU, machine model, or clinical claims requires a separate human-approved
  decision; and
- no known merge-blocking defect or approved follow-up implementation remains
  from the completed pull requests through #16.

Do not add personal-computer paths, private dataset details, patient or facility
data, credentials, or real-tool output to this document.

## Restart checklist

At the start of a future development session:

1. Read `AGENTS.md` and `AI_AGENT_RULES.md` in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Confirm that `main` contains squash merge commit `e1d9943c276d` or a later
   descendant.
4. Read this document, the
   [CT2PHITS frontend handoff](ct2phits-frontend-handoff.md), and the
   [workflow stage guide](workflow_stages.md), and verify that their baseline
   still matches `main`.
5. Start with the approved Windows GUI diagnostic session described above;
   keep both designated workspaces and all real-tool output outside Git.
6. For each observed failure, preserve the GUI log and record exact
   reproduction steps before proposing a code change.
7. When a human decision is required, ask a direct yes/no question.
8. Stop after the approved acceptance criteria and required checks pass.
