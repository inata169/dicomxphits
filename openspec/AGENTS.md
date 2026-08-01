# OpenSpec Instructions

The repository-level `AI_AGENT_RULES.md` remains authoritative. OpenSpec
records approved intent; it never authorizes protected data, real external-tool
execution, physics decisions, destructive actions, or scope expansion by
itself.

## Before Work

1. Read `openspec/project.md`.
2. Read relevant current specifications under `openspec/specs/` when present.
3. Inspect active changes under `openspec/changes/` for overlap.
4. Choose a unique, verb-led, kebab-case change ID.

## Change Workflow

Create a change before implementing a new capability, behavioral or public
contract, architecture change, or planned scope expansion. A change contains:

- `proposal.md` with `Why`, `What Changes`, and `Impact` sections;
- `tasks.md` with an implementation checklist;
- `design.md` when decisions, boundaries, or trade-offs need explanation; and
- delta specifications at `specs/<capability>/spec.md`.

Delta specifications use `## ADDED Requirements`, `## MODIFIED Requirements`,
`## REMOVED Requirements`, or `## RENAMED Requirements`. Each normative
requirement uses SHALL or MUST and has at least one scenario headed exactly
`#### Scenario:`.

Ask a human to approve the proposal before runtime implementation. Questions
to this repository's primary user must be phrased for a `yes/no` answer.

After implementation, update every completed task accurately and run strict
OpenSpec validation when the CLI is available. If it is unavailable, perform a
manual structural review and report that CLI validation was not run. Keep the
change active while implementation, required validation, or a required human
decision remains.

## Completion and Archive

OpenSpec cleanup is part of the current task. Before reporting completion of an
approved change:

1. Confirm that the human-approved acceptance criteria and required checks have
   passed.
2. Update `tasks.md` accurately. Record explicitly deferred non-blocking checks
   without representing them as completed.
3. Promote each accepted delta into the corresponding current specification at
   `openspec/specs/<capability>/spec.md`.
4. Move the complete change directory to
   `openspec/changes/archive/YYYY-MM-DD-<change-id>/`.
5. Run strict OpenSpec validation on the resulting specification tree and
   archive when the CLI is available. Otherwise perform and report a manual
   structural review.
6. Inspect the final diff and repository status before the completion report.

Use the OpenSpec archive command when it is available and compatible with the
repository. A manual in-repository move is acceptable when the CLI is absent,
provided delta promotion and structural validation are performed explicitly.
Do not archive incomplete or blocked work merely to make the active changes
directory empty. Report the remaining active change and its smallest unresolved
condition instead.

## Conventions

- OpenSpec documents are written in English and encoded as UTF-8.
- Do not include patient data, real DICOM identifiers, external-tool results,
  facility values, credentials, or personal-computer absolute paths.
- Specifications describe observable contracts, not speculative future work.
- Tests are observers of a specification, not substitutes for it.
