# Project status

This document records the durable, human-managed development status of the
public repository. It is not an automatically expanding backlog. Update it only
when a human approves a new goal or when a completed pull request materially
changes the status described here.

## Current baseline

- Public release: `v1.0.0`
- Public workflow scope: documented fixed-field 3D-CRT
- Latest completed project: LLM development-loop foundation
- Completion pull request:
  [#1](https://github.com/inata169/dicomxphits/pull/1)
- Squash merge commit: `7d2f511a3136da6d35b857b42c8e048e9f1f5c84`
- Status last reviewed: 2026-08-01

The development-loop foundation is complete. It added the provider-neutral
agent policy, bounded correction and human-stop loops, pull-request stopping
rules, repository-scoped Codex settings, a non-root Python Dev Container,
development documentation, CI integration, and the public-tree boundary audit.

## Validation baseline

The completion state for pull request #1 was validated with:

- 10 focused public-tree audit tests;
- 397 full pytest tests;
- Python compilation of the public source;
- a passing public-tree audit of 75 tracked files; and
- a successful `dicomxphits public CI` pull-request run.

The Dev Container build was not run because Docker and Dev Container tooling
were unavailable in the validation environment. This is an unverified item,
not an automatically scheduled task.

No runtime code, public physics or model behavior, DICOM meaning, public
specification, version, tag, or release was changed by the foundation work.

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
- no follow-up work remains from pull request #1.

Do not add personal-computer paths, private dataset details, patient or facility
data, credentials, or real-tool output to this document.

## Restart checklist

At the start of a future development session:

1. Read `AGENTS.md` and `AI_AGENT_RULES.md` in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Read this document and verify that its baseline still matches `main`.
4. Ask the human for one explicit development goal if none is recorded here.
5. When a human decision is required, ask a direct yes/no question.
6. Stop after the approved acceptance criteria and required checks pass.
