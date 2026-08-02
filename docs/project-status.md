# Project status

This document records the durable, human-managed development status of the
public repository. It is not an automatically expanding backlog. Update it only
when a human approves a new goal or when a completed pull request materially
changes the status described here.

## Current baseline

- Public release: `v1.0.0`
- Public workflow scope: documented fixed-field 3D-CRT
- Latest completed project: guided CT2PHITS GUI integration
- Completion pull request:
  [#5](https://github.com/inata169/dicomxphits/pull/5)
- Squash merge commit: `bc6296d5f6949f461e7d50b86db6a0b4579e048d`
- Status last reviewed: 2026-08-02

The guided CT2PHITS GUI integration is complete. It made the accepted frontend
the first guided stage, applies only a verified frozen handoff to downstream
preparation, remembers stable local tool paths and independent Browse history,
keeps safety confirmation non-persistent, and presents responsive, separately
gated workflow stages. Review corrections also bound completed handoffs to the
executed workspace, launched CT2PHITS from an existing RT-PHITS directory,
required an explicit manual or verified handoff before preparation, and made
local-settings failure handling fail safely. The accepted GUI contract is in
[`openspec/specs/guided-gui-workflow/spec.md`](../openspec/specs/guided-gui-workflow/spec.md).

The underlying automated CT2PHITS frontend remains complete under pull request
[#3](https://github.com/inata169/dicomxphits/pull/3), squash commit
`f792d0ec7f1e9265ad5df939e2e6b3aeb9f6e4bb`. See the
[CT2PHITS frontend handoff](ct2phits-frontend-handoff.md) for its detailed
completion state and restart procedure.

The earlier LLM development-loop foundation remains complete under pull
request [#1](https://github.com/inata169/dicomxphits/pull/1), squash commit
`7d2f511a3136da6d35b857b42c8e048e9f1f5c84`.

## Validation baseline

The completion state for pull request #5 was validated locally on Windows
with:

- 45 focused GUI tests;
- 470 full pytest tests;
- Python compilation of the public source;
- a passing public-tree audit of 91 tracked files;
- passing Git diff and status checks; and
- a final Codex review of head commit `56bb88f3ec` reporting no major issues.

An explicitly authorized Windows smoke test with designated non-patient phantom
data outside the repository completed CT2PHITS and downstream workspace
preparation. PHITS segment execution started successfully and parsed the
generated inputs without an observed fatal error at the PR handoff. PHITS
completion, Sumtally, RTDOSE preparation and conversion, phits2dicom execution,
and dose validation remained unverified when pull request #5 was merged. No
real input, distribution, personal path, or generated result was committed.

Separately, `dicomxphits public CI` run `#42` passed the synthetic/mock compile,
full pytest, and public-tree checks for the earlier frontend baseline on
GitHub's `ubuntu-latest` Linux runner. This is Linux CI evidence for pull
request #3; it does not validate pull request #5 or the real Windows RT-PHITS
runtime.

The workplace Dev Container cross-check has not run. Validation in that
specific container environment remains unverified synthetic/mock evidence and
is not an automatically scheduled task. This is distinct from the completed
Ubuntu GitHub Actions validation above.

Pull request #5 changed GUI runtime and local-settings behavior, the RT-PHITS
batch adapter's non-interactive process input, documentation, and the public
guided-GUI specification within its approved scope. It did not change PHITS
physics, dose, MU, machine-model behavior, DICOM coordinate meaning, the public
fixed-field 3D-CRT scope, version, tag, or release.

## Current development plan

No next implementation goal is approved or scheduled.

Before starting another development cycle, a human must select one concrete
goal and state its scope, acceptance criteria, and important non-goals. That
approval may authorize one branch and one reviewable pull request. An LLM must
not turn optional improvements, review suggestions, or this status document
into new Issues, OpenSpec changes, branches, pull requests, automations, or
other work items on its own.

## Human-decision queue

The following facts may inform a future human decision, but they are not
approved work:

- a Dev Container build has not yet been verified;
- completion of the PHITS, Sumtally, RTDOSE, phits2dicom, and optional GPR
  real-tool evidence remains outside ordinary public development and requires
  an explicit, exact human request;
- any change to the public fixed-field 3D-CRT scope, physics, geometry, dose,
  MU, machine model, or clinical claims requires a separate human-approved
  decision; and
- no known merge-blocking defect or approved follow-up implementation remains
  from pull request #5.

Do not add personal-computer paths, private dataset details, patient or facility
data, credentials, or real-tool output to this document.

## Restart checklist

At the start of a future development session:

1. Read `AGENTS.md` and `AI_AGENT_RULES.md` in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Confirm that `main` contains squash merge commit `bc6296d5f694` or a later
   descendant.
4. Read this document, the
   [CT2PHITS frontend handoff](ct2phits-frontend-handoff.md), and the
   [workflow stage guide](workflow_stages.md), and verify that their baseline
   still matches `main`.
5. Ask the human for one explicit development goal if none is recorded here.
6. When a human decision is required, ask a direct yes/no question.
7. Stop after the approved acceptance criteria and required checks pass.
