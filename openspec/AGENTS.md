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
change active while its implementation is unmerged. Archive it and promote its
deltas into `openspec/specs/` only after human authorization following merge or
acceptance.

## Conventions

- OpenSpec documents are written in English and encoded as UTF-8.
- Do not include patient data, real DICOM identifiers, external-tool results,
  facility values, credentials, or personal-computer absolute paths.
- Specifications describe observable contracts, not speculative future work.
- Tests are observers of a specification, not substitutes for it.
