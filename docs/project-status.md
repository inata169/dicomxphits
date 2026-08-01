# Project status

This document records the durable, human-managed development status of the
public repository. It is not an automatically expanding backlog. Update it only
when a human approves a new goal or when a completed pull request materially
changes the status described here.

## Current baseline

- Public release: `v1.0.0`
- Public workflow scope: documented fixed-field 3D-CRT
- Latest completed project: automated CT2PHITS frontend
- Completion pull request:
  [#3](https://github.com/inata169/dicomxphits/pull/3)
- Squash merge commit: `f792d0ec7f1e9265ad5df939e2e6b3aeb9f6e4bb`
- Status last reviewed: 2026-08-02

The automated CT2PHITS frontend is complete. It added the explicit Windows
batch adapter, isolated and verified CT/RT Plan snapshots, generated-file
inventory and hashes, process and timeout evidence, downstream DATfiles asset
preparation, synthetic/mock tests, and the current OpenSpec contract. See the
[CT2PHITS frontend handoff](ct2phits-frontend-handoff.md) for the detailed
completion state and restart procedure.

The earlier LLM development-loop foundation remains complete under pull
request [#1](https://github.com/inata169/dicomxphits/pull/1), squash commit
`7d2f511a3136da6d35b857b42c8e048e9f1f5c84`.

## Validation baseline

The completion state for pull request #3 was validated locally on Windows
with:

- 65 focused CT2PHITS frontend and DATfiles tests;
- 456 full pytest tests;
- Python compilation of the public source;
- a passing public-tree audit of 85 tracked files; and
- a final Codex review reporting no major issues.

Separately, `dicomxphits public CI` run `#42` passed the synthetic/mock compile,
full pytest, and public-tree checks on GitHub's `ubuntu-latest` Linux runner.
This is Linux CI evidence; it does not validate the real Windows RT-PHITS
runtime.

An explicitly authorized Windows smoke test with a designated non-patient
phantom outside the repository completed successfully. No real input,
distribution, or generated result was committed. PHITS, Sumtally,
phits2dicom, and GPR were not run for this frontend task.

The workplace Dev Container cross-check has not run. Validation in that
specific container environment remains unverified synthetic/mock evidence and
is not an automatically scheduled task. This is distinct from the completed
Ubuntu GitHub Actions validation above.

Pull request #3 changed runtime code, DICOM input validation, documentation,
and the public CT2PHITS frontend specification within its approved scope. It
did not change PHITS physics, dose, MU, machine-model behavior, the public
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
- real DICOM and real external-tool workflows remain outside ordinary public
  development and require an explicit, exact human request;
- any change to the public fixed-field 3D-CRT scope, physics, geometry, dose,
  MU, machine model, or clinical claims requires a separate human-approved
  decision; and
- no known merge-blocking defect or approved follow-up implementation remains
  from pull request #3.

Do not add personal-computer paths, private dataset details, patient or facility
data, credentials, or real-tool output to this document.

## Restart checklist

At the start of a future development session:

1. Read `AGENTS.md` and `AI_AGENT_RULES.md` in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Read this document and the
   [CT2PHITS frontend handoff](ct2phits-frontend-handoff.md), and verify that
   their baseline still matches `main`.
4. Ask the human for one explicit development goal if none is recorded here.
5. When a human decision is required, ask a direct yes/no question.
6. Stop after the approved acceptance criteria and required checks pass.
